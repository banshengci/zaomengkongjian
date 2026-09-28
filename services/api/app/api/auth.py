"""账号与配额 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from app.domain.schemas import AuthAnonRequest, AuthAnonResponse, QuotaStatus, utc_now
from app.store.memory import get_store

router = APIRouter()

_DISTILL_LIMIT = 20
_TURN_LIMIT = 200


def _user_id(authorization: str) -> str | None:
    if not authorization.startswith("Bearer "):
        return None
    return get_store().resolve_token(authorization[7:].strip())


@router.post("/auth/anon", response_model=AuthAnonResponse)
async def auth_anon(payload: AuthAnonRequest) -> AuthAnonResponse:
    uid, token = get_store().create_anon_user(payload.display_name)
    return AuthAnonResponse(
        user_id=uid, token=token, display_name=payload.display_name or "旅人"
    )


@router.get("/auth/me")
async def auth_me(authorization: str = Header(default="")) -> dict[str, Any]:
    uid = _user_id(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})
    user = get_store().get_user(uid) or {}
    return {
        "user_id": uid,
        "display_name": user.get("display_name", "旅人"),
        "kind": user.get("kind", "anon"),
    }


@router.get("/quota", response_model=QuotaStatus)
async def quota(authorization: str = Header(default="")) -> QuotaStatus:
    uid = _user_id(authorization) or "anon"
    q = get_store().quota_status(uid)
    return QuotaStatus(
        user_id=uid,
        distill_used=int(q.get("distill_used", 0)),
        distill_limit=_DISTILL_LIMIT,
        turn_used=int(q.get("turn_used", 0)),
        turn_limit=_TURN_LIMIT,
        reset_at=q.get("reset_at") or utc_now(),
    )
