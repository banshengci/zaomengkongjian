"""设置与模型配置 API。"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter

from app.domain.schemas import (
    ModelConnectionTest,
    ModelSettingsRead,
    ModelSettingsWrite,
)
from app.store.memory import get_store

router = APIRouter()


@router.get("/model", response_model=ModelSettingsRead)
async def get_model_settings() -> ModelSettingsRead:
    data = get_store().get_model_settings()
    return ModelSettingsRead(
        provider=str(data.get("provider") or "openai-compatible"),
        model=str(data.get("model") or ""),
        base_url=str(data.get("base_url") or ""),
        api_key_configured=bool(data.get("api_key")),
        max_tokens=int(data.get("max_tokens") or 4096),
    )


@router.put("/model", response_model=ModelSettingsRead)
async def put_model_settings(payload: ModelSettingsWrite) -> ModelSettingsRead:
    store = get_store()
    current = store.get_model_settings()
    fields: dict[str, Any] = {
        "provider": payload.provider,
        "model": payload.model,
        "base_url": payload.base_url,
        "max_tokens": payload.max_tokens,
    }
    if payload.api_key:
        fields["api_key"] = payload.api_key
    else:
        fields["api_key"] = current.get("api_key") or ""
    store.set_model_settings(**fields)
    return await get_model_settings()


@router.post("/model/test", response_model=ModelConnectionTest)
async def test_model(payload: ModelSettingsWrite | None = None) -> ModelConnectionTest:
    import time

    data = get_store().get_model_settings()
    base_url = (payload.base_url if payload else data.get("base_url") or "").rstrip("/")
    api_key = (
        payload.api_key if payload and payload.api_key else data.get("api_key") or ""
    )
    model = payload.model if payload else data.get("model") or ""
    if not (base_url and api_key and model):
        return ModelConnectionTest(
            ok=False, latency_ms=0, message="model settings incomplete"
        )
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 4,
                },
            )
        latency = int((time.perf_counter() - started) * 1000)
        if resp.status_code >= 400:
            return ModelConnectionTest(
                ok=False, latency_ms=latency, message=f"http {resp.status_code}"
            )
        return ModelConnectionTest(ok=True, latency_ms=latency, message="ok")
    except (httpx.HTTPError, OSError, ValueError) as exc:
        latency = int((time.perf_counter() - started) * 1000)
        return ModelConnectionTest(ok=False, latency_ms=latency, message=str(exc))
