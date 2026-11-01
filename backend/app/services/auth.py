"""Email + password accounts with opaque bearer sessions. Standard library only (scrypt, secrets, hashlib)."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AuthSession, User

SESSION_DAYS = 14
MIN_PASSWORD = 10
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
_N, _R, _P = 2**14, 8, 1
_fails: dict[str, list[float]] = {}
MAX_FAILS, WINDOW = 5, 300.0


class AuthError(ValueError):
    def __init__(self, msg: str, status: int = 422):
        super().__init__(msg)
        self.status = status


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got.hex(), dk)
    except (ValueError, TypeError):
        return False


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _norm(email: str) -> str:
    e = (email or "").strip().lower()
    if not EMAIL.match(e) or len(e) > 254:
        raise AuthError("enter a valid email address")
    return e


def _throttle(key: str) -> None:
    now = time.monotonic()
    recent = [t for t in _fails.get(key, []) if now - t < WINDOW]
    _fails[key] = recent
    if len(recent) >= MAX_FAILS:
        raise AuthError("too many failed attempts; try again in a few minutes", 429)


def issue(session: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    session.add(AuthSession(token_hash=_digest(token), user_id=user.id, expires_at=datetime.now(UTC) + timedelta(days=SESSION_DAYS)))
    session.commit()
    return token


def register(session: Session, email: str, password: str) -> tuple[User, str]:
    e = _norm(email)
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"password must be at least {MIN_PASSWORD} characters")
    if len(password) > 200:
        raise AuthError("password is too long")
    if session.scalar(select(User).where(User.email == e)):
        raise AuthError("an account with this email already exists", 409)
    u = User(email=e, password_hash=hash_password(password))
    session.add(u)
    session.commit()
    return u, issue(session, u)


def login(session: Session, email: str, password: str) -> tuple[User, str]:
    e = _norm(email)
    _throttle(e)
    u = session.scalar(select(User).where(User.email == e))
    ok = verify_password(password or "", u.password_hash) if u else verify_password(password or "", hash_password("x"))  # constant-ish time
    if not u or not ok:
        _fails.setdefault(e, []).append(time.monotonic())
        raise AuthError("incorrect email or password", 401)
    _fails.pop(e, None)
    return u, issue(session, u)


def user_for_token(session: Session, token: str | None) -> User | None:
    if not token:
        return None
    s = session.get(AuthSession, _digest(token))
    if s is None:
        return None
    exp = s.expires_at if s.expires_at.tzinfo else s.expires_at.replace(tzinfo=UTC)
    if exp < datetime.now(UTC):
        session.execute(delete(AuthSession).where(AuthSession.token_hash == s.token_hash))
        session.commit()
        return None
    return session.get(User, s.user_id)


def logout(session: Session, token: str) -> None:
    session.execute(delete(AuthSession).where(AuthSession.token_hash == _digest(token)))
    session.commit()
