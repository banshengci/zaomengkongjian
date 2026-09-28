"""蒸馏编排：payload → LLM → materialize → 关系图。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.domain.schemas import CharacterRead, RelationEdgeRead
from app.integrate.contracts import parse_profile_markdown, parse_relation_markdown
from app.integrate.skill_runner import (
    build_prompt_payload,
    export_relation_graph,
    init_host_run,
    materialize_profile,
)
from app.llm.client import LlmClient, LlmMessage
from app.observability import safe_text, timed
from app.store.memory import get_store


class DistillError(RuntimeError):
    pass


def _book_workdir(book_id: str) -> Path:
    settings = get_settings()
    path = settings.resolved_artifacts_dir / book_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_distill_job_sync(job_id: str) -> dict[str, Any]:
    return asyncio.run(run_distill_job(job_id))


def _edge_from_fields(pair_key: str, fields: dict[str, str]) -> RelationEdgeRead:
    def _int(key: str) -> int:
        raw = fields.get(key, "0").strip()
        try:
            return max(0, min(10, int(raw)))
        except ValueError:
            return 0

    return RelationEdgeRead(
        pair_key=pair_key,
        trust=_int("trust"),
        affection=_int("affection"),
        power_gap=_int("power_gap"),
        hostility=_int("hostility"),
        ambiguity=_int("ambiguity"),
        relationship_type=fields.get("relationship_type", ""),
        conflict_point=fields.get("conflict_point", ""),
        typical_interaction=fields.get("typical_interaction", ""),
        relation_change=fields.get("relation_change", ""),
        fields=fields,
    )


async def run_distill_job(job_id: str) -> dict[str, Any]:
    """完整蒸馏链路：manifest → payload → LLM profiles/relations → 物化。"""
    store = get_store()
    job = store.get_distill_job(job_id)
    if job is None:
        raise DistillError(f"job not found: {job_id}")
    book = store.get_book(job.book_id)
    if book is None:
        raise DistillError(f"book not found: {job.book_id}")

    store.update_distill_job(
        job_id, stage="running", progress={"step": "init_manifest"}
    )
    store.update_book_status(job.book_id, "distilling")

    workdir = _book_workdir(job.book_id)
    novel_path = workdir / "novel.txt"
    if not novel_path.exists():
        novel_path.write_text(book.title + "\n", encoding="utf-8")

    manifest_path = workdir / "run_manifest.json"
    characters_dir = workdir / "characters"
    characters_dir.mkdir(parents=True, exist_ok=True)

    try:
        with timed("distill.init_manifest", job_id=job_id, book_id=book.id):
            init_host_run(
                novel_path=novel_path,
                characters=job.characters,
                output_manifest=manifest_path,
                novel_id=book.novel_id or book.id,
            )
        store.update_distill_job(job_id, progress={"step": "manifest_ready"})

        payload_path = workdir / "distill_payload.json"
        with timed("distill.payload", job_id=job_id):
            build_prompt_payload(
                novel_path=novel_path,
                characters=job.characters,
                output_payload=payload_path,
                run_manifest=manifest_path,
            )
        store.update_distill_job(
            job_id, stage="merge", progress={"step": "payload_ready"}
        )

        client = LlmClient()
        novel_excerpt = novel_path.read_text(encoding="utf-8")[:8000]
        for name in job.characters:
            store.update_distill_job(
                job_id,
                stage="running",
                progress={"step": "llm_profile", "character": name},
            )
            prompt = (
                "请为下列中文小说角色生成造梦 PROFILE markdown，遵循 # PROFILE 结构。\n"
                f"角色名：{name}\n"
                f"小说片段：\n{novel_excerpt}\n"
                "只输出 PROFILE markdown 正文。"
            )
            with timed("distill.llm_profile", character=safe_text(name)):
                text = await client.complete_text(
                    [LlmMessage(role="user", content=prompt)]
                )
            body = (
                text
                if "# PROFILE" in text
                else f"# PROFILE\n\n## Meta\n- name: {name}\n\n{text}"
            )
            parsed = parse_profile_markdown(body)
            char_dir = characters_dir / name
            char_dir.mkdir(parents=True, exist_ok=True)
            profile_path = char_dir / "PROFILE.generated.md"
            profile_path.write_text(parsed.raw, encoding="utf-8")
            try:
                materialize_profile(profile_file=profile_path, output_dir=char_dir)
            except Exception:  # noqa: BLE001, S110 — 物化失败不阻断已生成的 PROFILE
                pass
            store.add_characters(
                book.id,
                [
                    CharacterRead(
                        id=f"{book.id}:{name}",
                        book_id=book.id,
                        name=name,
                        profile_ref=str(profile_path),
                        role_tags=parsed.meta.role_tags,
                        profile={
                            "meta": parsed.meta.model_dump(),
                            "sections": parsed.sections,
                        },
                    )
                ],
            )

        store.update_distill_job(
            job_id, stage="materialize", progress={"step": "materialized"}
        )

        rel_prompt = (
            "请为下列角色生成造梦 RELATION_GRAPH markdown。\n"
            f"角色：{'；'.join(job.characters)}\n"
            f"小说片段：\n{novel_excerpt[:6000]}\n"
            "只输出 RELATION_GRAPH markdown。"
        )
        rel_text = await client.complete_text(
            [LlmMessage(role="user", content=rel_prompt)]
        )
        if "# RELATION_GRAPH" not in rel_text:
            rel_text = "# RELATION_GRAPH\n\n" + rel_text
        edges_raw = parse_relation_markdown(rel_text)
        edges = [_edge_from_fields(e.pair_key, e.fields) for e in edges_raw]
        rel_path = workdir / "relations.md"
        rel_path.write_text(rel_text, encoding="utf-8")
        store.set_relations(book.id, edges)

        store.update_distill_job(
            job_id,
            stage="graph",
            progress={"step": "relation_parsed", "edges": len(edges)},
        )
        try:
            export_relation_graph(rel_file=rel_path, novel_id=book.novel_id or book.id)
        except Exception:  # noqa: BLE001, S110 — 图导出失败不阻断关系数据
            pass

        store.update_distill_job(
            job_id,
            stage="done",
            progress={"step": "complete", "profiles": len(job.characters)},
        )
        store.update_book_status(book.id, "ready")
        return {
            "job_id": job_id,
            "manifest_path": str(manifest_path),
            "relations_path": str(rel_path),
            "relation_count": len(edges),
            "characters": job.characters,
        }
    except Exception as exc:
        store.update_distill_job(job_id, stage="failed", error=str(exc))
        store.update_book_status(book.id, "failed")
        raise
