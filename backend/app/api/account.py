from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User, UserItem
from app.services import auth

router = APIRouter(prefix="/api/v1", tags=["account"])
KINDS = ("watchlist", "portfolio", "screen", "alert", "research")
MAX_ITEMS_PER_KIND = 100
MAX_PAYLOAD_CHARS = 50_000
Sess = Annotated[Session, Depends(get_session)]


def bearer(authorization: Annotated[str | None, Header()] = None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def current_user(session: Sess, token: Annotated[str | None, Depends(bearer)]) -> User:
    u = auth.user_for_token(session, token)
    if u is None:
        raise HTTPException(401, "sign in required", headers={"WWW-Authenticate": "Bearer"})
    return u


CurrentUser = Annotated[User, Depends(current_user)]


def _wrap(fn, *a):
    try:
        return fn(*a)
    except auth.AuthError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


@router.post("/auth/register", status_code=201)
def register(body: dict[str, Any], session: Sess) -> dict[str, Any]:
    u, tok = _wrap(auth.register, session, str(body.get("email", "")), str(body.get("password", "")))
    return {"token": tok, "user": {"id": u.id, "email": u.email}}


@router.post("/auth/login")
def login(body: dict[str, Any], session: Sess) -> dict[str, Any]:
    u, tok = _wrap(auth.login, session, str(body.get("email", "")), str(body.get("password", "")))
    return {"token": tok, "user": {"id": u.id, "email": u.email}}


@router.post("/auth/logout", status_code=204)
def logout(session: Sess, token: Annotated[str | None, Depends(bearer)], _u: CurrentUser) -> None:
    if token:
        auth.logout(session, token)


@router.get("/auth/me")
def me(u: CurrentUser) -> dict[str, Any]:
    return {"id": u.id, "email": u.email}


def _row(i: UserItem) -> dict[str, Any]:
    return {"id": i.id, "kind": i.kind, "name": i.name, "payload": i.payload, "updated_at": i.updated_at.isoformat() if i.updated_at else None}


@router.get("/me/items")
def list_items(session: Sess, u: CurrentUser, kind: str | None = None) -> list[dict[str, Any]]:
    if kind is not None and kind not in KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")
    q = select(UserItem).where(UserItem.user_id == u.id).order_by(UserItem.updated_at.desc())
    if kind:
        q = q.where(UserItem.kind == kind)
    return [_row(i) for i in session.scalars(q)]


@router.put("/me/items/{kind}/{name}")
def save_item(kind: str, name: str, payload: dict[str, Any], session: Sess, u: CurrentUser) -> dict[str, Any]:
    if kind not in KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")
    name = name.strip()
    if not 1 <= len(name) <= 120:
        raise HTTPException(422, "name must be 1 to 120 characters")
    if len(str(payload)) > MAX_PAYLOAD_CHARS:
        raise HTTPException(413, "item is too large")
    item = session.scalar(select(UserItem).where(UserItem.user_id == u.id, UserItem.kind == kind, UserItem.name == name))
    if item is None:
        n = len(session.scalars(select(UserItem.id).where(UserItem.user_id == u.id, UserItem.kind == kind)).all())
        if n >= MAX_ITEMS_PER_KIND:
            raise HTTPException(422, f"at most {MAX_ITEMS_PER_KIND} saved {kind} items")
        item = UserItem(user_id=u.id, kind=kind, name=name, payload=payload)
        session.add(item)
    else:
        item.payload = payload
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "could not save, try again") from exc
    session.refresh(item)
    return _row(item)


@router.delete("/me/items/{item_id}", status_code=204)
def delete_item(item_id: int, session: Sess, u: CurrentUser) -> None:
    item = session.scalar(select(UserItem).where(UserItem.id == item_id, UserItem.user_id == u.id))  # ownership in the query
    if item is None:
        raise HTTPException(404, "not found")
    session.delete(item)
    session.commit()
