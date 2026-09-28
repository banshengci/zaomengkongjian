"""蒸馏链路：调用造梦 skill 初始化 run manifest。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.distill import DistillError, run_distill_job
from app.domain.schemas import BookCreateRequest
from app.integrate.skill_paths import resolve_skill_paths
from app.integrate.skill_runner import init_host_run
from app.store.memory import get_store


def test_init_host_run_writes_manifest(tmp_path: Path) -> None:
    skill = resolve_skill_paths()
    novel = tmp_path / "novel.txt"
    novel.write_text("林黛玉进了园子。贾宝玉跟在后面。\n", encoding="utf-8")
    manifest = tmp_path / "run_manifest.json"

    result = init_host_run(
        novel_path=novel,
        characters=["林黛玉", "贾宝玉"],
        output_manifest=manifest,
        novel_id="test_novel",
        skill=skill,
    )
    assert manifest.exists()
    assert result.payload.get("locked_characters") or result.payload.get("novel_id")


async def test_run_distill_job_updates_state() -> None:
    store = get_store()
    book = store.create_book(
        BookCreateRequest(title="测试书卷", source="upload", novel_id="job_novel")
    )
    job = store.create_distill_job(book.id, ["林黛玉"])
    out = await run_distill_job(job.id)
    assert out["job_id"] == job.id
    updated_job = store.get_distill_job(job.id)
    assert updated_job is not None
    assert updated_job.stage == "done"
    updated_book = store.get_book(book.id)
    assert updated_book is not None
    assert updated_book.status == "ready"
    assert store.list_characters(book.id)
    assert store.list_relations(book.id)


async def test_run_distill_job_missing_raises() -> None:
    with pytest.raises(DistillError):
        await run_distill_job("job-missing")
