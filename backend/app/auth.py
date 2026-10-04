"""FastAPI auth dependencies."""
from __future__ import annotations

from fastapi import Header, HTTPException

from .layer6_persistence.users import verify_token, get_user_by_id, User


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


async def get_optional_user(authorization: str | None = Header(None)) -> User | None:
    token = _extract_token(authorization)
    if not token:
        return None
    uid = verify_token(token)
    if not uid:
        return None
    return get_user_by_id(uid)


async def get_current_user(authorization: str | None = Header(None)) -> User:
    user = await get_optional_user(authorization)
    if not user:
        raise HTTPException(401, "未登录或登录已过期")
    return user
