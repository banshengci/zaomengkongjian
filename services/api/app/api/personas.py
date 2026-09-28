"""人物档案与关系 API。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.schemas import RelationEdgeRead
from app.integrate.contracts import parse_profile_markdown
from app.store.memory import get_store

router = APIRouter()


class PersonaPatch(BaseModel):
    fields: dict[str, str]


class RelationPatch(BaseModel):
    trust: int = 0
    affection: int = 0
    hostility: int = 0
    ambiguity: int = 0
    power_gap: int = 0
    relationship_type: str = ""
    relation_change: str = ""
    conflict_point: str = ""
    typical_interaction: str = ""


@router.get("/{book_id}/personas/{name}")
async def get_persona(book_id: str, name: str) -> dict[str, Any]:
    store = get_store()
    character = store.get_character(book_id, name)
    if character is None:
        raise HTTPException(status_code=404, detail={"error": "character not found"})
    profile: dict[str, Any] = {}
    if character.profile_ref:
        path = Path(character.profile_ref)
        if path.exists():
            try:
                parsed = parse_profile_markdown(path.read_text(encoding="utf-8"))
                profile = {
                    "meta": parsed.meta.model_dump(),
                    "sections": parsed.sections,
                }
            except (OSError, ValueError):
                profile = {}
    return {
        "name": character.name,
        "book_id": book_id,
        "role_tags": character.role_tags,
        "profile": profile,
    }


@router.put("/{book_id}/personas/{name}")
async def patch_persona(
    book_id: str, name: str, payload: PersonaPatch
) -> dict[str, Any]:
    store = get_store()
    character = store.get_character(book_id, name)
    if character is None:
        raise HTTPException(status_code=404, detail={"error": "character not found"})
    # M1：仅合并进 profile_ref 旁路 JSON，保持 canonical md 不动
    side = (
        Path(character.profile_ref).with_name("PROFILE.overrides.json")
        if character.profile_ref
        else None
    )
    if side is not None:
        existing: dict[str, str] = {}
        if side.exists():
            existing = json.loads(side.read_text(encoding="utf-8"))
        existing.update(payload.fields)
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return {"status": "updated", "name": name, "fields": payload.fields}


@router.patch("/{book_id}/relations/{pair_key}", response_model=RelationEdgeRead)
async def patch_relation(
    book_id: str, pair_key: str, payload: RelationPatch
) -> RelationEdgeRead:
    store = get_store()
    edges = store.list_relations(book_id)
    updated_list: list[RelationEdgeRead] = []
    found: RelationEdgeRead | None = None
    for edge in edges:
        if edge.pair_key == pair_key:
            found = edge.model_copy(update=payload.model_dump())
        else:
            updated_list.append(edge)
    if found is None:
        found = RelationEdgeRead(pair_key=pair_key, **payload.model_dump())
    updated_list.append(found)
    store.set_relations(book_id, updated_list)
    return found


# ---------- 人物演进 ----------


class EvolveProposalBody(BaseModel):
    session_id: str = ""
    focus: str = ""


class EvolveApplyBody(BaseModel):
    proposal_id: str = ""
    fields: dict[str, str] = {}
    note: str = ""


@router.post("/{book_id}/personas/{name}/evolve/proposal")
async def evolve_proposal(
    book_id: str, name: str, payload: EvolveProposalBody
) -> dict[str, Any]:
    store = get_store()
    if store.get_character(book_id, name) is None:
        raise HTTPException(status_code=404, detail={"error": "character not found"})
    import uuid

    from app.domain.schemas import EvolveProposalRead, utc_now

    transcript = (
        store.session_transcript(payload.session_id) if payload.session_id else []
    )
    hint = (
        "冲突加剧"
        if any("争" in m.message or "怒" in m.message for m in transcript[-20:])
        else "关系缓和"
    )
    fields = {
        "relation_change": hint,
        "arc_mid": f"trigger_event={payload.focus or hint}",
    }
    proposal = EvolveProposalRead(
        id=f"evo-{uuid.uuid4().hex[:8]}",
        book_id=book_id,
        character=name,
        fields=fields,
        rationale=f"依据近期会话观察：{hint}",
        status="proposed",
        created_at=utc_now(),
    )
    store.add_evolve(proposal)
    return proposal.model_dump(mode="json")


@router.post("/{book_id}/personas/{name}/evolve/apply")
async def evolve_apply(
    book_id: str, name: str, payload: EvolveApplyBody
) -> dict[str, Any]:
    store = get_store()
    character = store.get_character(book_id, name)
    if character is None:
        raise HTTPException(status_code=404, detail={"error": "character not found"})
    from app.domain.schemas import utc_now

    fields = dict(payload.fields or {})
    proposal = store.get_evolve(payload.proposal_id) if payload.proposal_id else None
    if proposal is not None:
        fields = {**proposal.fields, **fields}
        store.update_evolve(payload.proposal_id, status="applied")
    log = list(character.evolution_log)
    log.append({"fields": fields, "note": payload.note, "at": utc_now().isoformat()})
    store.update_character(book_id, name, evolution_log=log)
    return {"status": "applied", "character": name, "fields": fields}
