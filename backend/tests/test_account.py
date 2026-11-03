import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.models import AuthSession
from app.services import auth
from fastapi.testclient import TestClient
from sqlalchemy import select, update


@pytest.fixture()
def client(migrated):
    from app.main import app

    auth._fails.clear()
    return TestClient(app)


def signup(c, pw="correct-horse-1"):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    r = c.post("/api/v1/auth/register", json={"email": email, "password": pw})
    assert r.status_code == 201, r.text
    return email, {"Authorization": f"Bearer {r.json()['token']}"}


def test_register_login_me_logout(client, migrated):
    email, h = signup(client)
    assert client.get("/api/v1/auth/me", headers=h).json()["email"] == email
    assert client.post("/api/v1/auth/login", json={"email": email.upper(), "password": "correct-horse-1"}).status_code == 200  # case-insensitive
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 204
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401  # token is dead


def test_passwords_and_tokens_are_not_stored_in_clear(client, migrated):
    from app.db import session_factory

    email, h = signup(client, "a-very-secret-pass")
    tok = h["Authorization"].split()[1]
    with session_factory()() as s:
        hashes = [u.password_hash for u in s.scalars(select(auth.User))]
        assert all("a-very-secret-pass" not in x and x.startswith("scrypt$") for x in hashes)
        assert s.get(AuthSession, tok) is None and s.get(AuthSession, auth._digest(tok)) is not None


def test_validation_duplicates_and_bad_credentials(client):
    email, _ = signup(client)
    bad = [({"email": "nope", "password": "long-enough-pw"}, 422), ({"email": "a@b.co", "password": "short"}, 422), ({"email": email, "password": "long-enough-pw"}, 409)]
    for body, code in bad:
        assert client.post("/api/v1/auth/register", json=body).status_code == code, body
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "x" * 12}).status_code == 401  # same answer for unknown accounts


def test_login_is_throttled_after_repeated_failures(client):
    email, _ = signup(client)
    for _ in range(auth.MAX_FAILS):
        assert client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"}).status_code == 401
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "correct-horse-1"})
    assert r.status_code == 429  # even the right password waits


def test_private_endpoints_require_a_valid_session(client):
    for method, path in [("get", "/api/v1/me/items"), ("get", "/api/v1/auth/me"), ("put", "/api/v1/me/items/watchlist/x"), ("delete", "/api/v1/me/items/1"), ("post", "/api/v1/auth/logout")]:
        r = getattr(client, method)(path, **({"json": {}} if method == "put" else {}))
        assert r.status_code == 401, path
    assert client.get("/api/v1/me/items", headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.get("/api/v1/me/items", headers={"Authorization": "Basic abc"}).status_code == 401


def test_expired_sessions_are_rejected(client, migrated):
    from app.db import session_factory

    _, h = signup(client)
    with session_factory()() as s:
        s.execute(update(AuthSession).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
        s.commit()
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_items_crud_and_per_user_isolation(client, migrated):
    _, a = signup(client)
    _, b = signup(client)
    r = client.put("/api/v1/me/items/watchlist/Core", json={"scheme_ids": [1, 2, 3]}, headers=a)
    assert r.status_code == 200 and r.json()["payload"] == {"scheme_ids": [1, 2, 3]}
    client.put("/api/v1/me/items/watchlist/Core", json={"scheme_ids": [9]}, headers=a)  # update in place, no duplicate
    mine = client.get("/api/v1/me/items", params={"kind": "watchlist"}, headers=a).json()
    assert len(mine) == 1 and mine[0]["payload"] == {"scheme_ids": [9]}
    assert client.get("/api/v1/me/items", headers=b).json() == []  # b sees nothing of a's
    assert client.delete(f"/api/v1/me/items/{mine[0]['id']}", headers=b).status_code == 404  # and cannot delete it
    assert client.get("/api/v1/me/items", headers=a).json()  # still there
    assert client.delete(f"/api/v1/me/items/{mine[0]['id']}", headers=a).status_code == 204
    assert client.get("/api/v1/me/items", headers=a).json() == []


def test_item_validation(client):
    _, h = signup(client)
    assert client.put("/api/v1/me/items/bogus/x", json={}, headers=h).status_code == 422
    assert client.put("/api/v1/me/items/screen/%20", json={}, headers=h).status_code == 422
    assert client.put("/api/v1/me/items/screen/big", json={"x": "y" * 60_000}, headers=h).status_code == 413
    assert client.get("/api/v1/me/items", params={"kind": "bogus"}, headers=h).status_code == 422


def test_production_refuses_development_credentials():
    from app.core.config import Settings
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(environment="production", _env_file=None)
    ok = Settings(environment="production", database_url="postgresql+psycopg://u:p@db/x", cors_origins=["https://app.example.com"], _env_file=None)
    assert ok.environment == "production"


def test_hosted_postgres_urls_are_normalised_for_the_psycopg_driver():
    from app.core.config import Settings

    for raw in ("postgres://u:p@h:5432/d", "postgresql://u:p@h:5432/d"):
        assert Settings(database_url=raw, _env_file=None).database_url == "postgresql+psycopg://u:p@h:5432/d"
    assert Settings(database_url="postgresql+psycopg://u:p@h/d", _env_file=None).database_url == "postgresql+psycopg://u:p@h/d"


def test_cors_origin_regex_allows_vercel_deployments_only(client):
    from app.core.config import Settings
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.testclient import TestClient

    st = Settings(environment="production", database_url="postgresql+psycopg://u:p@db/x", cors_origins=[], cors_origin_regex=r"^https://[a-z0-9-]+\.vercel\.app$", _env_file=None)
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=st.cors_origins, allow_origin_regex=st.cors_origin_regex, allow_methods=["GET"])
    app.get("/x")(lambda: {})
    c = TestClient(app)
    ok = c.get("/x", headers={"Origin": "https://qsmf-abc-123.vercel.app"})
    bad = c.get("/x", headers={"Origin": "https://evil.example.com"})
    assert ok.headers.get("access-control-allow-origin") == "https://qsmf-abc-123.vercel.app"
    assert "access-control-allow-origin" not in bad.headers
