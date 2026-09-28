"""桥接本机造梦：健康探测 + 书卷/会话镜像同步（只读）。"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.store.memory import get_store

router = APIRouter()


class BridgeConfig(BaseModel):
    base_url: str = Field(default="http://127.0.0.1:0", max_length=200)
    token: str = Field(default="", max_length=200)


class BridgeClient:
    def __init__(self, base_url: str, token: str) -> None:
        if not base_url.startswith("http://127.0.0.1") and not base_url.startswith(
            "http://localhost"
        ):
            raise ValueError("bridge only allows localhost")
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _get(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{self.base_url}{path}", headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else {"items": data}

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/api/web/health")
            resp.raise_for_status()
            return resp.json()

    async def list_runs(self) -> dict[str, Any]:
        return await self._get("/api/web/runs")

    async def list_sessions(self) -> dict[str, Any]:
        return await self._get("/api/web/sessions")

    async def get_run(self, run_id: str) -> dict[str, Any]:
        return await self._get(f"/api/web/runs/{run_id}")


@router.post("/bridge/health")
async def bridge_health(config: BridgeConfig) -> dict[str, Any]:
    try:
        return await BridgeClient(config.base_url, config.token).health()
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc


@router.post("/bridge/runs")
async def bridge_runs(config: BridgeConfig) -> dict[str, Any]:
    try:
        return await BridgeClient(config.base_url, config.token).list_runs()
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc


@router.post("/bridge/sessions")
async def bridge_sessions(config: BridgeConfig) -> dict[str, Any]:
    try:
        return await BridgeClient(config.base_url, config.token).list_sessions()
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc


@router.post("/bridge/sync")
async def bridge_sync(config: BridgeConfig) -> dict[str, Any]:
    """把本机造梦书卷镜像为 Web 只读书卷（幂等，按 novel_id 去重）。"""
    try:
        client = BridgeClient(config.base_url, config.token)
        runs = await client.list_runs()
        items = list(runs.get("items") or runs.get("runs") or [])
        store = get_store()
        imported: list[str] = []
        skipped = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            novel_id = str(item.get("novel_id") or item.get("run_id") or "")
            title = str(
                item.get("title") or item.get("novel_name") or novel_id or "本机书卷"
            )
            if not novel_id:
                skipped += 1
                continue
            existing = [b for b in store.list_books() if b.novel_id == novel_id]
            if existing:
                skipped += 1
                continue
            book = store.create_book(
                __import__(
                    "app.domain.schemas", fromlist=["BookCreateRequest"]
                ).BookCreateRequest(
                    title=title,
                    source="import",
                    novel_id=novel_id,
                ),
                owner_id="bridge",
            )
            store.update_book_status(book.id, "ready")
            imported.append(book.id)
        return {
            "imported": imported,
            "imported_count": len(imported),
            "skipped": skipped,
            "remote_count": len(items),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc
