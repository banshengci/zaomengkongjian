"""内存存储 v0.3：分支、记忆、世界、协作、导出、配额。业务只依赖 Store 方法。"""

from __future__ import annotations

import itertools
import secrets
import threading
from datetime import datetime, timedelta
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
    SessionTreeNode,
    ShareCreateRequest,
    ShareLinkRead,
    TurnMessage,
    TurnRead,
    WorldFactRead,
    WorldFactRequest,
    utc_now,
)


def _day_reset() -> datetime:
    now = utc_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


class MemoryStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._seq = itertools.count(1)
        self._books: dict[str, BookRead] = {}
        self._jobs: dict[str, DistillJobRead] = {}
        self._characters: dict[str, list[CharacterRead]] = {}
        self._relations: dict[str, list[RelationEdgeRead]] = {}
        self._sessions: dict[str, SessionRead] = {}
        self._turns: dict[str, list[TurnRead]] = {}
        self._chapters: dict[str, ChapterRead] = {}
        self._shares: dict[str, ShareLinkRead] = {}
        self._scene_cards: dict[str, SceneCardRead] = {}
        self._memories: dict[str, list[MemoryRead]] = {}
        self._world_facts: dict[str, list[WorldFactRead]] = {}
        self._highlights: dict[str, HighlightCardRead] = {}
        self._crossovers: dict[str, CrossoverSpaceRead] = {}
        self._members: dict[str, list[SessionMemberRead]] = {}
        self._evolves: dict[str, EvolveProposalRead] = {}
        self._users: dict[str, dict[str, Any]] = {}
        self._tokens: dict[str, str] = {}
        self._quota: dict[str, dict[str, Any]] = {}
        self._model_settings: dict[str, Any] = {
            "provider": "openai-compatible",
            "model": "",
            "base_url": "",
            "api_key": "",
            "max_tokens": 4096,
        }
        self._seed_scene_cards()

    def _id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._seq)}"

    def _seed_scene_cards(self) -> None:
        seeds = [
            (
                "scene-rain",
                "雨夜客栈",
                {"location": "客栈", "mood": "紧张", "time": "夜晚"},
            ),
            (
                "scene-court",
                "庭院对峙",
                {"location": "庭院", "mood": "冲突", "time": "黄昏"},
            ),
            (
                "scene-quiet",
                "书房夜话",
                {"location": "书房", "mood": "平静", "time": "深夜"},
            ),
        ]
        for cid, title, fields in seeds:
            self._scene_cards[cid] = SceneCardRead(
                id=cid,
                title=title,
                fields=fields,
                preview=f"{title}：{fields.get('mood', '')}",
            )

    # ---- users / quota ----
    def create_anon_user(self, display_name: str) -> tuple[str, str]:
        with self._lock:
            uid = self._id("user")
            token = secrets.token_urlsafe(18)
            self._users[uid] = {
                "id": uid,
                "display_name": display_name or "旅人",
                "kind": "anon",
            }
            self._tokens[token] = uid
            self._quota[uid] = {
                "distill_used": 0,
                "turn_used": 0,
                "reset_at": _day_reset(),
            }
            return uid, token

    def resolve_token(self, token: str) -> str | None:
        with self._lock:
            return self._tokens.get(token)

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._users.get(user_id)

    def quota_status(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            q = self._quota.setdefault(
                user_id,
                {"distill_used": 0, "turn_used": 0, "reset_at": _day_reset()},
            )
            if q["reset_at"] < utc_now():
                q["distill_used"] = 0
                q["turn_used"] = 0
                q["reset_at"] = _day_reset()
            return dict(q)

    def consume_quota(self, user_id: str, kind: str, limit: int) -> bool:
        with self._lock:
            q = self.quota_status(user_id)
            key = f"{kind}_used"
            if int(q.get(key, 0)) >= limit:
                return False
            self._quota[user_id][key] = int(q.get(key, 0)) + 1
            return True

    # ---- books ----
    def list_books(self, owner_id: str | None = None) -> list[BookRead]:
        with self._lock:
            items = list(self._books.values())
            if owner_id:
                items = [b for b in items if b.owner_id in {owner_id, "anon", ""}]
            return sorted(items, key=lambda b: b.created_at, reverse=True)

    def create_book(
        self, payload: BookCreateRequest, owner_id: str = "anon"
    ) -> BookRead:
        with self._lock:
            book = BookRead(
                id=self._id("book"),
                title=payload.title,
                source=payload.source,
                novel_id=payload.novel_id or f"novel-{next(self._seq)}",
                status="draft",
                owner_id=owner_id,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            self._books[book.id] = book
            self._characters.setdefault(book.id, [])
            self._relations.setdefault(book.id, [])
            self._world_facts.setdefault(book.id, [])
            return book

    def get_book(self, book_id: str) -> BookRead | None:
        with self._lock:
            return self._books.get(book_id)

    def update_book_status(self, book_id: str, status: str) -> BookRead | None:
        with self._lock:
            book = self._books.get(book_id)
            if book is None:
                return None
            updated = book.model_copy(
                update={"status": status, "updated_at": utc_now()}
            )
            self._books[book_id] = updated
            return updated

    def delete_book(self, book_id: str) -> bool:
        with self._lock:
            self._characters.pop(book_id, None)
            self._relations.pop(book_id, None)
            self._world_facts.pop(book_id, None)
            return self._books.pop(book_id, None) is not None

    # ---- distill ----
    def create_distill_job(self, book_id: str, characters: list[str]) -> DistillJobRead:
        with self._lock:
            job = DistillJobRead(
                id=self._id("job"),
                book_id=book_id,
                characters=list(characters),
                stage="queued",
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            self._jobs[job.id] = job
            return job

    def get_distill_job(self, job_id: str) -> DistillJobRead | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_distill_job(
        self, job_id: str, **fields: object
    ) -> DistillJobRead | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            updated = job.model_copy(update={"updated_at": utc_now(), **fields})
            self._jobs[job_id] = updated
            return updated

    def list_distill_jobs(self, book_id: str) -> list[DistillJobRead]:
        with self._lock:
            return [j for j in self._jobs.values() if j.book_id == book_id]

    # ---- characters / relations ----
    def list_characters(self, book_id: str) -> list[CharacterRead]:
        with self._lock:
            return list(self._characters.get(book_id, []))

    def get_character(self, book_id: str, name: str) -> CharacterRead | None:
        with self._lock:
            for item in self._characters.get(book_id, []):
                if item.name == name:
                    return item
            return None

    def add_characters(self, book_id: str, items: list[CharacterRead]) -> None:
        with self._lock:
            bucket = self._characters.setdefault(book_id, [])
            for item in items:
                bucket = [c for c in bucket if c.name != item.name]
                bucket.append(item)
            self._characters[book_id] = bucket

    def update_character(
        self, book_id: str, name: str, **fields: Any
    ) -> CharacterRead | None:
        with self._lock:
            bucket = self._characters.get(book_id, [])
            for idx, item in enumerate(bucket):
                if item.name == name:
                    updated = item.model_copy(update=fields)
                    bucket[idx] = updated
                    return updated
            return None

    def set_relations(self, book_id: str, edges: list[RelationEdgeRead]) -> None:
        with self._lock:
            self._relations[book_id] = list(edges)

    def list_relations(self, book_id: str) -> list[RelationEdgeRead]:
        with self._lock:
            return list(self._relations.get(book_id, []))

    # ---- scene cards ----
    def list_scene_cards(self) -> list[SceneCardRead]:
        with self._lock:
            return list(self._scene_cards.values())

    def get_scene_card(self, card_id: str) -> SceneCardRead | None:
        with self._lock:
            return self._scene_cards.get(card_id)

    def upsert_scene_card(
        self, card_id: str, title: str, fields: dict[str, Any]
    ) -> SceneCardRead:
        with self._lock:
            card = SceneCardRead(
                id=card_id,
                title=title,
                fields=fields,
                preview=f"{title}：{fields.get('mood', '')}",
            )
            self._scene_cards[card_id] = card
            return card

    # ---- sessions / branches / turns ----
    def create_session(self, payload: SessionCreateRequest) -> SessionRead:
        with self._lock:
            session = SessionRead(
                id=self._id("ses"),
                book_id=payload.book_id,
                title=payload.title or "未命名剧场",
                mode=payload.mode,
                participants=list(payload.participants),
                controlled_character=payload.controlled_character,
                scene_card_id=payload.scene_card_id,
                self_card_id=payload.self_card_id,
                branch_of=payload.branch_of,
                branch_label=payload.branch_label,
                is_mainline=not payload.branch_of,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            self._sessions[session.id] = session
            self._turns[session.id] = []
            self._memories[session.id] = []
            self._members[session.id] = [
                SessionMemberRead(
                    user_id="anon",
                    display_name="导演",
                    role="director",
                    online=True,
                )
            ]
            return session

    def get_session(self, session_id: str) -> SessionRead | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self, book_id: str | None = None) -> list[SessionRead]:
        with self._lock:
            items = list(self._sessions.values())
            if book_id:
                items = [s for s in items if s.book_id == book_id]
            return sorted(items, key=lambda s: s.updated_at, reverse=True)

    def update_session(self, session_id: str, **fields: object) -> SessionRead | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(update={"updated_at": utc_now(), **fields})
            self._sessions[session_id] = updated
            return updated

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            self._turns.pop(session_id, None)
            self._memories.pop(session_id, None)
            self._members.pop(session_id, None)
            return self._sessions.pop(session_id, None) is not None

    def session_tree(self, book_id: str) -> list[SessionTreeNode]:
        with self._lock:
            sessions = [s for s in self._sessions.values() if s.book_id == book_id]
            nodes = {
                s.id: SessionTreeNode(
                    id=s.id,
                    title=s.title,
                    branch_of=s.branch_of,
                    branch_label=s.branch_label,
                    is_mainline=s.is_mainline,
                    transcript_count=s.transcript_count,
                )
                for s in sessions
            }
            roots: list[SessionTreeNode] = []
            for node in nodes.values():
                parent = nodes.get(node.branch_of)
                if parent is not None:
                    parent.children.append(node)
                else:
                    roots.append(node)
            return roots

    def append_turn(self, session_id: str, turn: TurnRead) -> TurnRead:
        with self._lock:
            self._turns.setdefault(session_id, []).append(turn)
            session = self._sessions.get(session_id)
            if session is not None:
                count = sum(len(t.messages) for t in self._turns[session_id])
                self._sessions[session_id] = session.model_copy(
                    update={"transcript_count": count, "updated_at": utc_now()}
                )
            return turn

    def list_turns(self, session_id: str) -> list[TurnRead]:
        with self._lock:
            return list(self._turns.get(session_id, []))

    def get_turn(self, session_id: str, turn_id: str) -> TurnRead | None:
        with self._lock:
            for turn in self._turns.get(session_id, []):
                if turn.id == turn_id:
                    return turn
            return None

    def session_transcript(self, session_id: str) -> list[TurnMessage]:
        with self._lock:
            out: list[TurnMessage] = []
            for turn in self._turns.get(session_id, []):
                out.extend(turn.messages)
            return out

    # ---- memories ----
    def list_memories(self, session_id: str) -> list[MemoryRead]:
        with self._lock:
            return list(self._memories.get(session_id, []))

    def add_memory(
        self, session_id: str, payload: MemoryCreateRequest, source: str = "manual"
    ) -> MemoryRead:
        with self._lock:
            item = MemoryRead(
                id=self._id("mem"),
                session_id=session_id,
                text=payload.text,
                category=payload.category,
                pinned=payload.pinned,
                enabled=payload.enabled,
                source=source,
                created_at=utc_now(),
            )
            self._memories.setdefault(session_id, []).append(item)
            return item

    def update_memory(
        self, session_id: str, memory_id: str, **fields: Any
    ) -> MemoryRead | None:
        with self._lock:
            bucket = self._memories.get(session_id, [])
            for idx, item in enumerate(bucket):
                if item.id == memory_id:
                    updated = item.model_copy(update=fields)
                    bucket[idx] = updated
                    return updated
            return None

    def delete_memory(self, session_id: str, memory_id: str) -> bool:
        with self._lock:
            bucket = self._memories.get(session_id, [])
            for idx, item in enumerate(bucket):
                if item.id == memory_id:
                    del bucket[idx]
                    return True
            return False

    def active_prompt_memories(self, session_id: str) -> list[MemoryRead]:
        return [
            m
            for m in self.list_memories(session_id)
            if m.enabled
            and m.status == "active"
            and (m.pinned or m.category in {"story", "relation", "world"})
        ][:12]

    # ---- world facts ----
    def list_world_facts(self, book_id: str) -> list[WorldFactRead]:
        with self._lock:
            return sorted(
                self._world_facts.get(book_id, []),
                key=lambda f: (f.time_hint, f.created_at),
            )

    def add_world_fact(self, book_id: str, payload: WorldFactRequest) -> WorldFactRead:
        with self._lock:
            item = WorldFactRead(
                id=self._id("fact"),
                book_id=book_id,
                category=payload.category,
                summary=payload.summary,
                characters=list(payload.characters),
                location=payload.location,
                time_hint=payload.time_hint,
                locked=payload.locked,
                active=payload.active,
                created_at=utc_now(),
            )
            self._world_facts.setdefault(book_id, []).append(item)
            return item

    def update_world_fact(
        self, book_id: str, fact_id: str, **fields: Any
    ) -> WorldFactRead | None:
        with self._lock:
            bucket = self._world_facts.get(book_id, [])
            for idx, item in enumerate(bucket):
                if item.id == fact_id:
                    if item.locked and not fields.get("force"):
                        fields.pop("summary", None)
                    fields.pop("force", None)
                    updated = item.model_copy(update=fields)
                    bucket[idx] = updated
                    return updated
            return None

    def delete_world_fact(self, book_id: str, fact_id: str) -> bool:
        with self._lock:
            bucket = self._world_facts.get(book_id, [])
            for idx, item in enumerate(bucket):
                if item.id == fact_id:
                    if item.locked:
                        return False
                    del bucket[idx]
                    return True
            return False

    def locked_facts(self, book_id: str) -> list[WorldFactRead]:
        return [f for f in self.list_world_facts(book_id) if f.locked and f.active]

    # ---- chapters ----
    def create_chapter(
        self, payload: ChapterCreateRequest, book_id: str, content_md: str
    ) -> ChapterRead:
        with self._lock:
            chapter = ChapterRead(
                id=self._id("chap"),
                book_id=book_id,
                session_id=payload.session_id,
                title=payload.title or "章节",
                content_md=content_md,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            self._chapters[chapter.id] = chapter
            return chapter

    def get_chapter(self, chapter_id: str) -> ChapterRead | None:
        with self._lock:
            return self._chapters.get(chapter_id)

    def list_chapters(self, book_id: str | None = None) -> list[ChapterRead]:
        with self._lock:
            items = list(self._chapters.values())
            if book_id:
                items = [c for c in items if c.book_id == book_id]
            return sorted(items, key=lambda c: c.created_at, reverse=True)

    def update_chapter(self, chapter_id: str, **fields: Any) -> ChapterRead | None:
        with self._lock:
            chapter = self._chapters.get(chapter_id)
            if chapter is None:
                return None
            updated = chapter.model_copy(update={"updated_at": utc_now(), **fields})
            self._chapters[chapter_id] = updated
            return updated

    # ---- share / highlight ----
    def create_share(self, payload: ShareCreateRequest) -> ShareLinkRead:
        with self._lock:
            token = secrets.token_urlsafe(16)
            link = ShareLinkRead(
                token=token,
                url_path=f"/share/{token}",
                resource_type=payload.resource_type,
                resource_id=payload.resource_id,
                expires_at=utc_now() + timedelta(hours=payload.expires_hours),
                created_at=utc_now(),
            )
            self._shares[token] = link
            return link

    def get_share(self, token: str) -> ShareLinkRead | None:
        with self._lock:
            link = self._shares.get(token)
            if link is None or link.expires_at < utc_now():
                return None
            return link

    def revoke_share(self, token: str) -> bool:
        with self._lock:
            return self._shares.pop(token, None) is not None

    def add_highlight(self, card: HighlightCardRead) -> HighlightCardRead:
        with self._lock:
            self._highlights[card.id] = card
            return card

    def get_highlight(self, card_id: str) -> HighlightCardRead | None:
        with self._lock:
            return self._highlights.get(card_id)

    # ---- crossover / members / evolve ----
    def create_crossover(
        self, payload: CrossoverCreateRequest, session_id: str
    ) -> CrossoverSpaceRead:
        with self._lock:
            space = CrossoverSpaceRead(
                id=self._id("cross"),
                title=payload.title,
                world_setting=payload.world_setting,
                participants=list(payload.participants),
                session_id=session_id,
                created_at=utc_now(),
            )
            self._crossovers[space.id] = space
            return space

    def get_crossover(self, space_id: str) -> CrossoverSpaceRead | None:
        with self._lock:
            return self._crossovers.get(space_id)

    def list_members(self, session_id: str) -> list[SessionMemberRead]:
        with self._lock:
            return list(self._members.get(session_id, []))

    def claim_seat(
        self, session_id: str, user_id: str, display_name: str, character: str
    ) -> SessionMemberRead:
        with self._lock:
            bucket = self._members.setdefault(session_id, [])
            for m in bucket:
                if m.character == character and m.role == "actor":
                    raise ValueError("seat already claimed")
            member = SessionMemberRead(
                user_id=user_id,
                display_name=display_name,
                character=character,
                role="actor",
                online=True,
            )
            bucket = [
                m for m in bucket if not (m.user_id == user_id and m.role == "actor")
            ]
            bucket.append(member)
            self._members[session_id] = bucket
            return member

    def add_evolve(self, proposal: EvolveProposalRead) -> EvolveProposalRead:
        with self._lock:
            self._evolves[proposal.id] = proposal
            return proposal

    def get_evolve(self, proposal_id: str) -> EvolveProposalRead | None:
        with self._lock:
            return self._evolves.get(proposal_id)

    def update_evolve(
        self, proposal_id: str, **fields: Any
    ) -> EvolveProposalRead | None:
        with self._lock:
            item = self._evolves.get(proposal_id)
            if item is None:
                return None
            updated = item.model_copy(update=fields)
            self._evolves[proposal_id] = updated
            return updated

    def list_evolves(self, book_id: str) -> list[EvolveProposalRead]:
        with self._lock:
            return [e for e in self._evolves.values() if e.book_id == book_id]

    # ---- model settings ----
    def get_model_settings(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._model_settings)

    def set_model_settings(self, **fields: Any) -> dict[str, Any]:
        with self._lock:
            self._model_settings.update(fields)
            return dict(self._model_settings)


_store: MemoryStore | None = None
_store_lock = threading.Lock()


def get_store() -> MemoryStore:
    """兼容入口：转发到 bootstrap 工厂（默认 SQLite）。"""
    from app.store.bootstrap import get_store as _get

    return _get()


def reset_store() -> MemoryStore:
    """测试用：重置为内存存储。"""
    from app.store.bootstrap import reset_store as _reset

    return _reset()
