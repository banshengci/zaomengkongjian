"""SQLite 持久化存储：与 MemoryStore 同接口，重启不丢书卷/会话/记忆。

JSON 列存完整对象，标量列用于查询。ORM 简化为单表快照，满足 MVP。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.schemas import (
    BookCreateRequest,
    BookRead,
    ChapterCreateRequest,
    ChapterRead,
    CharacterRead,
    CrossoverCreateRequest,
    CrossoverSpaceRead,
    DistillJobRead,
    EvolveProposalRead,
    HighlightCardRead,
    MemoryCreateRequest,
    MemoryRead,
    RelationEdgeRead,
    SceneCardRead,
    SessionCreateRequest,
    SessionMemberRead,
    SessionRead,
    ShareCreateRequest,
    ShareLinkRead,
    TurnRead,
    WorldFactRead,
    WorldFactRequest,
    utc_now,
)
from app.store.memory import MemoryStore


class SqliteStore(MemoryStore):
    """启动时从 SQLite 回放，写操作同步落库。"""

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._load()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshot (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _flush(self) -> None:
        payload = {
            "books": {k: v.model_dump(mode="json") for k, v in self._books.items()},
            "jobs": {k: v.model_dump(mode="json") for k, v in self._jobs.items()},
            "characters": {
                k: [c.model_dump(mode="json") for c in v]
                for k, v in self._characters.items()
            },
            "relations": {
                k: [r.model_dump(mode="json") for r in v]
                for k, v in self._relations.items()
            },
            "sessions": {
                k: v.model_dump(mode="json") for k, v in self._sessions.items()
            },
            "turns": {
                k: [t.model_dump(mode="json") for t in v]
                for k, v in self._turns.items()
            },
            "chapters": {
                k: v.model_dump(mode="json") for k, v in self._chapters.items()
            },
            "shares": {k: v.model_dump(mode="json") for k, v in self._shares.items()},
            "scene_cards": {
                k: v.model_dump(mode="json") for k, v in self._scene_cards.items()
            },
            "memories": {
                k: [m.model_dump(mode="json") for m in v]
                for k, v in self._memories.items()
            },
            "world_facts": {
                k: [f.model_dump(mode="json") for f in v]
                for k, v in self._world_facts.items()
            },
            "highlights": {
                k: v.model_dump(mode="json") for k, v in self._highlights.items()
            },
            "crossovers": {
                k: v.model_dump(mode="json") for k, v in self._crossovers.items()
            },
            "members": {
                k: [m.model_dump(mode="json") for m in v]
                for k, v in self._members.items()
            },
            "evolves": {k: v.model_dump(mode="json") for k, v in self._evolves.items()},
            "users": self._users,
            "tokens": self._tokens,
            "quota": self._quota,
            "model_settings": self._model_settings,
            "seq": next(self._seq),
        }
        raw = json.dumps(payload, ensure_ascii=False)
        with self._conn:
            self._conn.execute(
                "INSERT INTO snapshot (id, payload, updated_at) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at",
                (raw, datetime.now(UTC).isoformat()),
            )

    def _load(self) -> None:
        row = self._conn.execute("SELECT payload FROM snapshot WHERE id = 1").fetchone()
        if row is None:
            return
        data = json.loads(row["payload"])

        def dt(value: Any) -> datetime:
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            return utc_now()

        self._books = {
            k: BookRead.model_validate(v) for k, v in (data.get("books") or {}).items()
        }
        self._jobs = {
            k: DistillJobRead.model_validate(v)
            for k, v in (data.get("jobs") or {}).items()
        }
        self._characters = {
            k: [CharacterRead.model_validate(x) for x in v]
            for k, v in (data.get("characters") or {}).items()
        }
        self._relations = {
            k: [RelationEdgeRead.model_validate(x) for x in v]
            for k, v in (data.get("relations") or {}).items()
        }
        self._sessions = {
            k: SessionRead.model_validate(v)
            for k, v in (data.get("sessions") or {}).items()
        }
        self._turns = {
            k: [TurnRead.model_validate(x) for x in v]
            for k, v in (data.get("turns") or {}).items()
        }
        self._chapters = {
            k: ChapterRead.model_validate(v)
            for k, v in (data.get("chapters") or {}).items()
        }
        self._shares = {
            k: ShareLinkRead.model_validate(v)
            for k, v in (data.get("shares") or {}).items()
        }
        self._scene_cards = {
            k: SceneCardRead.model_validate(v)
            for k, v in (data.get("scene_cards") or {}).items()
        }
        self._memories = {
            k: [MemoryRead.model_validate(x) for x in v]
            for k, v in (data.get("memories") or {}).items()
        }
        self._world_facts = {
            k: [WorldFactRead.model_validate(x) for x in v]
            for k, v in (data.get("world_facts") or {}).items()
        }
        self._highlights = {
            k: HighlightCardRead.model_validate(v)
            for k, v in (data.get("highlights") or {}).items()
        }
        self._crossovers = {
            k: CrossoverSpaceRead.model_validate(v)
            for k, v in (data.get("crossovers") or {}).items()
        }
        self._members = {
            k: [SessionMemberRead.model_validate(x) for x in v]
            for k, v in (data.get("members") or {}).items()
        }
        self._evolves = {
            k: EvolveProposalRead.model_validate(v)
            for k, v in (data.get("evolves") or {}).items()
        }
        self._users = data.get("users") or {}
        self._tokens = data.get("tokens") or {}
        raw_quota = data.get("quota") or {}
        self._quota = {}
        for uid, q in raw_quota.items():
            self._quota[uid] = {
                "distill_used": int(q.get("distill_used", 0)),
                "turn_used": int(q.get("turn_used", 0)),
                "reset_at": dt(q.get("reset_at")),
            }
        self._model_settings = data.get("model_settings") or self._model_settings
        self._seq = self._seq  # keep counter
        _ = data.get("seq")

    # ---- 重写写路径，统一 flush ----

    def create_anon_user(self, display_name: str) -> tuple[str, str]:
        result = super().create_anon_user(display_name)
        self._flush()
        return result

    def consume_quota(self, user_id: str, kind: str, limit: int) -> bool:
        ok = super().consume_quota(user_id, kind, limit)
        self._flush()
        return ok

    def create_book(
        self, payload: BookCreateRequest, owner_id: str = "anon"
    ) -> BookRead:
        book = super().create_book(payload, owner_id=owner_id)
        self._flush()
        return book

    def update_book_status(self, book_id: str, status: str) -> BookRead | None:
        result = super().update_book_status(book_id, status)
        self._flush()
        return result

    def delete_book(self, book_id: str) -> bool:
        ok = super().delete_book(book_id)
        self._flush()
        return ok

    def create_distill_job(self, book_id: str, characters: list[str]) -> DistillJobRead:
        job = super().create_distill_job(book_id, characters)
        self._flush()
        return job

    def update_distill_job(
        self, job_id: str, **fields: object
    ) -> DistillJobRead | None:
        result = super().update_distill_job(job_id, **fields)
        self._flush()
        return result

    def add_characters(self, book_id: str, items: list[CharacterRead]) -> None:
        super().add_characters(book_id, items)
        self._flush()

    def update_character(
        self, book_id: str, name: str, **fields: Any
    ) -> CharacterRead | None:
        result = super().update_character(book_id, name, **fields)
        self._flush()
        return result

    def set_relations(self, book_id: str, edges: list[RelationEdgeRead]) -> None:
        super().set_relations(book_id, edges)
        self._flush()

    def create_session(self, payload: SessionCreateRequest) -> SessionRead:
        session = super().create_session(payload)
        self._flush()
        return session

    def update_session(self, session_id: str, **fields: object) -> SessionRead | None:
        result = super().update_session(session_id, **fields)
        self._flush()
        return result

    def delete_session(self, session_id: str) -> bool:
        ok = super().delete_session(session_id)
        self._flush()
        return ok

    def append_turn(self, session_id: str, turn: TurnRead) -> TurnRead:
        result = super().append_turn(session_id, turn)
        self._flush()
        return result

    def add_memory(
        self, session_id: str, payload: MemoryCreateRequest, source: str = "manual"
    ) -> MemoryRead:
        item = super().add_memory(session_id, payload, source=source)
        self._flush()
        return item

    def update_memory(
        self, session_id: str, memory_id: str, **fields: Any
    ) -> MemoryRead | None:
        result = super().update_memory(session_id, memory_id, **fields)
        self._flush()
        return result

    def delete_memory(self, session_id: str, memory_id: str) -> bool:
        ok = super().delete_memory(session_id, memory_id)
        self._flush()
        return ok

    def add_world_fact(self, book_id: str, payload: WorldFactRequest) -> WorldFactRead:
        item = super().add_world_fact(book_id, payload)
        self._flush()
        return item

    def update_world_fact(
        self, book_id: str, fact_id: str, **fields: Any
    ) -> WorldFactRead | None:
        result = super().update_world_fact(book_id, fact_id, **fields)
        self._flush()
        return result

    def delete_world_fact(self, book_id: str, fact_id: str) -> bool:
        ok = super().delete_world_fact(book_id, fact_id)
        self._flush()
        return ok

    def create_chapter(
        self, payload: ChapterCreateRequest, book_id: str, content_md: str
    ) -> ChapterRead:
        chapter = super().create_chapter(payload, book_id, content_md)
        self._flush()
        return chapter

    def update_chapter(self, chapter_id: str, **fields: Any) -> ChapterRead | None:
        result = super().update_chapter(chapter_id, **fields)
        self._flush()
        return result

    def create_share(self, payload: ShareCreateRequest) -> ShareLinkRead:
        link = super().create_share(payload)
        self._flush()
        return link

    def revoke_share(self, token: str) -> bool:
        ok = super().revoke_share(token)
        self._flush()
        return ok

    def add_highlight(self, card: HighlightCardRead) -> HighlightCardRead:
        result = super().add_highlight(card)
        self._flush()
        return result

    def create_crossover(
        self, payload: CrossoverCreateRequest, session_id: str
    ) -> CrossoverSpaceRead:
        space = super().create_crossover(payload, session_id)
        self._flush()
        return space

    def claim_seat(
        self, session_id: str, user_id: str, display_name: str, character: str
    ) -> SessionMemberRead:
        member = super().claim_seat(session_id, user_id, display_name, character)
        self._flush()
        return member

    def add_evolve(self, proposal: EvolveProposalRead) -> EvolveProposalRead:
        result = super().add_evolve(proposal)
        self._flush()
        return result

    def update_evolve(
        self, proposal_id: str, **fields: Any
    ) -> EvolveProposalRead | None:
        result = super().update_evolve(proposal_id, **fields)
        self._flush()
        return result

    def set_model_settings(self, **fields: Any) -> dict[str, Any]:
        result = super().set_model_settings(**fields)
        self._flush()
        return result
