"""FastAPI auth dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Path

from .layer6_persistence.users import (
    User,
    bind_member_player_id,
    find_member_by_player_id,
    get_member_player_id,
    get_user_by_id,
    is_session_member,
    verify_token,
)
from .session import Session, get_session


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


def user_from_token(token: str | None) -> User | None:
    """Resolve a bearer/query token to a User (R0-2 WS + shared helpers)."""
    raw = (token or "").strip()
    if not raw:
        return None
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    uid = verify_token(raw)
    if not uid:
        return None
    return get_user_by_id(uid)


async def get_optional_user(authorization: str | None = Header(None)) -> User | None:
    return user_from_token(_extract_token(authorization))


async def get_current_user(authorization: str | None = Header(None)) -> User:
    user = await get_optional_user(authorization)
    if not user:
        raise HTTPException(401, "未登录或登录已过期")
    return user


async def require_session_member(
    sid: Annotated[str, Path(description="session id")],
    user: User = Depends(get_current_user),
) -> tuple[Session, User]:
    """Live session must exist and the caller must be a room member (R0-1)."""
    sess = get_session(sid)
    if not sess:
        raise HTTPException(404, "session not found")
    if not is_session_member(sid, user.id):
        raise HTTPException(403, "你不是该世界的成员")
    return sess, user


def resolve_acting_player_id(
    sid: str,
    user: User,
    sess: Session,
    player_id: str | None,
) -> str | None:
    """Ensure player_id belongs to this user; claim empty host binding if needed."""
    pid = (player_id or "").strip() or None
    bound = get_member_player_id(sid, user.id)

    if not pid:
        return bound

    if pid not in (sess.player_ids or []):
        raise HTTPException(400, "player_id 无效")

    claimed = find_member_by_player_id(sid, pid)
    if claimed and claimed["user_id"] != user.id:
        raise HTTPException(403, "不可操作其他玩家角色")

    if bound and bound != pid:
        raise HTTPException(403, "player_id 与当前用户绑定不符")

    if not bound:
        bind_member_player_id(sid, user.id, pid)

    return pid
