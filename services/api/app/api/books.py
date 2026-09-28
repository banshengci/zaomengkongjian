"""书卷包完整导出 / 导入、名场面、配额感知的书卷 API。"""

from __future__ import annotations

import base64
import io
import json
import os
import zipfile
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.distill import run_distill_job
from app.domain.schemas import (
    BookCreateRequest,
    BookRead,
    DistillJobRead,
    DistillRequest,
)
from app.integrate.contracts import normalize_package_manifest
from app.store.memory import get_store

router = APIRouter()

_DISTILL_LIMIT = 20


def _user_from_header(authorization: str = "") -> str:
    store = get_store()
    if authorization.startswith("Bearer "):
        uid = store.resolve_token(authorization[7:].strip())
        if uid:
            return uid
    return "anon"


@router.get("", response_model=list[BookRead])
async def list_books(authorization: str = Header(default="")) -> list[BookRead]:
    user_id = _user_from_header(authorization)
    return get_store().list_books(user_id if user_id != "anon" else None)


@router.post("", response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def create_book(
    payload: BookCreateRequest, authorization: str = Header(default="")
) -> BookRead:
    store = get_store()
    user_id = _user_from_header(authorization)
    book = store.create_book(payload, owner_id=user_id)
    if payload.content:
        settings = get_settings()
        novel_path = settings.resolved_artifacts_dir / book.id / "novel.txt"
        novel_path.parent.mkdir(parents=True, exist_ok=True)
        novel_path.write_text(payload.content, encoding="utf-8")
    return book


@router.post("/import", response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def import_package(payload: dict[str, Any]) -> BookRead:
    filename = str(payload.get("filename") or "book.zaomeng.zip")
    content_b64 = payload.get("content_base64") or ""
    if not content_b64:
        raise HTTPException(
            status_code=400, detail={"error": "content_base64 required"}
        )
    try:
        raw = base64.b64decode(content_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=400, detail={"error": "invalid base64"}
        ) from exc

    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = zf.namelist()
            if "package_manifest.json" not in names:
                raise HTTPException(
                    status_code=400, detail={"error": "package_manifest.json missing"}
                )
            manifest_raw = json.loads(zf.read("package_manifest.json").decode("utf-8"))
            manifest = normalize_package_manifest(manifest_raw)
            # 契约 C-K-04 / C-S-01：禁止绝对路径与密钥
            blob = json.dumps(manifest_raw, ensure_ascii=False)
            if "api_key" in blob or "API_KEY" in blob:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "package must not contain api_key"},
                )
            if ":\\" in blob or blob.find("/home/") >= 0:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "package must not contain absolute paths"},
                )
    except HTTPException:
        raise
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=400, detail={"error": "not a zip package"}
        ) from None
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail={"error": f"import failed: {exc}"}
        ) from exc

    store = get_store()
    book = store.create_book(
        BookCreateRequest(
            title=manifest.title or filename,
            source="import",
            novel_id=manifest.novel_id,
        )
    )
    settings = get_settings()
    dest = settings.resolved_artifacts_dir / book.id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "package_manifest.json").write_text(
        json.dumps(manifest_raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return book


@router.get("/{book_id}", response_model=BookRead)
async def get_book(book_id: str) -> BookRead:
    book = get_store().get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail={"error": "book not found"})
    return book


@router.delete("/{book_id}")
async def delete_book(book_id: str) -> dict[str, str]:
    if not get_store().delete_book(book_id):
        raise HTTPException(status_code=404, detail={"error": "book not found"})
    return {"status": "deleted"}


@router.post(
    "/{book_id}/distill",
    response_model=DistillJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_distill(
    book_id: str, payload: DistillRequest, authorization: str = Header(default="")
) -> DistillJobRead:
    store = get_store()
    user_id = _user_from_header(authorization)
    if store.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail={"error": "book not found"})
    if not store.consume_quota(user_id, "distill", _DISTILL_LIMIT):
        raise HTTPException(status_code=429, detail={"error": "distill quota exceeded"})
    job = store.create_distill_job(book_id, payload.characters)
    # 入队异步执行；测试可设 DREAMSPACE_SYNC_DISTILL=1 同步等待
    from app.queue import get_queue

    queue = get_queue()

    async def _run() -> None:
        await run_distill_job(job.id)

    if os.environ.get("DREAMSPACE_SYNC_DISTILL", "") == "1":
        await _run()
    else:
        try:
            queue.submit("distill", _run)
        except RuntimeError:
            await _run()
    return get_store().get_distill_job(job.id) or job


@router.get("/{book_id}/distill-jobs", response_model=list[DistillJobRead])
async def list_distill_jobs(book_id: str) -> list[DistillJobRead]:
    return get_store().list_distill_jobs(book_id)


@router.get("/{book_id}/distill-jobs/{job_id}", response_model=DistillJobRead)
async def get_distill_job(book_id: str, job_id: str) -> DistillJobRead:
    job = get_store().get_distill_job(job_id)
    if job is None or job.book_id != book_id:
        raise HTTPException(status_code=404, detail={"error": "distill job not found"})
    return job


@router.get("/{book_id}/characters")
async def list_characters(book_id: str) -> dict[str, Any]:
    store = get_store()
    if store.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail={"error": "book not found"})
    return {"items": store.list_characters(book_id)}


@router.get("/{book_id}/relations")
async def list_relations(book_id: str) -> dict[str, Any]:
    store = get_store()
    if store.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail={"error": "book not found"})
    edges = store.list_relations(book_id)
    return {"items": edges, "total": len(edges)}


# ---------- world memory facts（挂在 books 前缀下） ----------


@router.post("/{book_id}/world-memory/facts", status_code=201)
async def create_fact(book_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app.domain.schemas import WorldFactRequest

    if get_store().get_book(book_id) is None:
        raise HTTPException(status_code=404, detail={"error": "book not found"})
    fact = get_store().add_world_fact(book_id, WorldFactRequest.model_validate(payload))
    return fact.model_dump(mode="json")


@router.get("/{book_id}/world-memory/facts")
async def list_facts(book_id: str) -> list[dict[str, Any]]:
    return [f.model_dump(mode="json") for f in get_store().list_world_facts(book_id)]


@router.put("/{book_id}/world-memory/facts/{fact_id}")
async def update_fact(
    book_id: str, fact_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    allowed = {
        k: v
        for k, v in payload.items()
        if k
        in {
            "category",
            "summary",
            "characters",
            "location",
            "time_hint",
            "locked",
            "active",
        }
    }
    updated = get_store().update_world_fact(book_id, fact_id, **allowed)
    if updated is None:
        raise HTTPException(status_code=404, detail={"error": "fact not found"})
    return updated.model_dump(mode="json")


@router.delete("/{book_id}/world-memory/facts/{fact_id}")
async def delete_fact(book_id: str, fact_id: str) -> dict[str, str]:
    if not get_store().delete_world_fact(book_id, fact_id):
        raise HTTPException(
            status_code=404, detail={"error": "fact not found or locked"}
        )
    return {"status": "deleted"}


@router.get("/{book_id}/export")
async def export_book(
    book_id: str,
    include_dialogue: int = 0,
    include_chapters: int = 0,
) -> StreamingResponse:
    """导出 .zaomeng.zip 书卷包（schema_version=1）。"""
    store = get_store()
    book = store.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail={"error": "book not found"})

    characters = store.list_characters(book_id)
    relations = store.list_relations(book_id)
    sessions = store.list_sessions(book_id)
    chapters = store.list_chapters(book_id)

    manifest = {
        "kind": "zaomeng_web_run_package",
        "schema_version": 1,
        "package_id": f"pkg-{book_id}",
        "title": book.title,
        "novel_id": book.novel_id,
        "original_run_id": book_id,
        "status": book.status,
        "character_count": len(characters),
        "has_relation_graph": bool(relations),
        "includes_dialogue": bool(include_dialogue),
        "includes_chapters": bool(include_chapters),
        "summary": {
            "status_text": book.status,
            "graph_status": "complete" if relations else "pending",
        },
        "builtin": False,
        "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "package_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
        )
        for ch in characters:
            payload = {
                "name": ch.name,
                "role_tags": ch.role_tags,
                "profile": ch.profile,
                "evolution_log": ch.evolution_log,
            }
            # 契约：不含密钥、不含绝对路径
            zf.writestr(
                f"characters/{ch.name}/persona.json",
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
        zf.writestr(
            "relations/RELATION_GRAPH.json",
            json.dumps(
                [r.model_dump() for r in relations], ensure_ascii=False, indent=2
            ),
        )
        if include_dialogue:
            for ses in sessions:
                transcript = [m.model_dump() for m in store.session_transcript(ses.id)]
                zf.writestr(
                    f"dialogue/{ses.id}.json",
                    json.dumps(
                        {
                            "session": ses.model_dump(mode="json"),
                            "transcript": transcript,
                        },
                        ensure_ascii=False,
                    ),
                )
        if include_chapters:
            for chap in chapters:
                zf.writestr(
                    f"chapters/{chap.id}.md", f"# {chap.title}\n\n{chap.content_md}"
                )

    buf.seek(0)
    # HTTP 头只能 latin-1，文件名用 ASCII
    safe_name = f"{book_id}.zaomeng.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
