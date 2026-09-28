"""SQLAlchemy 存储层：SQLite 默认，PostgreSQL 只需换 DSN。

与 MemoryStore 同接口；实体落正规表，便于后续 PG 迁移与查询。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.domain.schemas import (
    BookCreateRequest,
    BookRead,
    CharacterRead,
    DistillJobRead,
    MemoryCreateRequest,
    MemoryRead,
    RelationEdgeRead,
    SessionCreateRequest,
    SessionRead,
    TurnRead,
    WorldFactRead,
    WorldFactRequest,
    utc_now,
)
from app.store.memory import MemoryStore


class Base(DeclarativeBase):
    pass


class BookRow(Base):
    __tablename__ = "books"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    title: Mapped[str] = mapped_column(String(200), default="")
    novel_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    owner_id: Mapped[str] = mapped_column(String(64), default="anon")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    book_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    title: Mapped[str] = mapped_column(String(200), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class TurnRow(Base):
    __tablename__ = "turns"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MemoryRow(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class WorldFactRow(Base):
    __tablename__ = "world_facts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    book_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    seq: Mapped[int] = mapped_column(Integer, default=0)


class JsonStateRow(Base):
    __tablename__ = "json_state"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")


class SqlStore(MemoryStore):
    """关键表规范化；其余对象暂存 json_state，接口不变。"""

    def __init__(self, db_url: str) -> None:
        super().__init__()
        self._engine = create_engine(db_url, future=True)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)
        self._load()

    @staticmethod
    def from_path(db_path: Path) -> SqlStore:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return SqlStore(f"sqlite:///{db_path}")

    def _load(self) -> None:
        with self._session_factory() as db:
            for row in db.execute(select(BookRow)).scalars():
                self._books[row.id] = BookRead.model_validate(json.loads(row.payload))
            for row in db.execute(select(SessionRow)).scalars():
                self._sessions[row.id] = SessionRead.model_validate(
                    json.loads(row.payload)
                )
            for row in db.execute(select(TurnRow)).scalars():
                turn = TurnRead.model_validate(json.loads(row.payload))
                self._turns.setdefault(row.session_id, []).append(turn)
            for row in db.execute(select(MemoryRow)).scalars():
                item = MemoryRead.model_validate(json.loads(row.payload))
                self._memories.setdefault(row.session_id, []).append(item)
            for row in db.execute(select(WorldFactRow)).scalars():
                fact = WorldFactRead.model_validate(json.loads(row.payload))
                self._world_facts.setdefault(row.book_id, []).append(fact)
            for row in db.execute(select(JsonStateRow)).scalars():
                data = json.loads(row.payload)
                if row.key == "jobs":
                    self._jobs = {
                        k: DistillJobRead.model_validate(v) for k, v in data.items()
                    }
                elif row.key == "characters":
                    self._characters = {
                        k: [CharacterRead.model_validate(x) for x in v]
                        for k, v in data.items()
                    }
                elif row.key == "relations":
                    self._relations = {
                        k: [RelationEdgeRead.model_validate(x) for x in v]
                        for k, v in data.items()
                    }
                elif row.key == "meta":
                    self._users = data.get("users", {})
                    self._tokens = data.get("tokens", {})
                    self._quota = data.get("quota", {})
                    self._model_settings = data.get(
                        "model_settings", self._model_settings
                    )

    def _upsert(self, db: Session, model: type, key: str, **fields: Any) -> None:
        row = db.get(model, key)
        if row is None:
            pk = next(iter(model.__table__.primary_key.columns.keys()))
            row = model(**{pk: key}, **fields)
            db.add(row)
        else:
            for name, value in fields.items():
                setattr(row, name, value)

    def _flush_state(self, db: Session) -> None:
        self._upsert(
            db,
            JsonStateRow,
            "jobs",
            payload=json.dumps(
                {k: v.model_dump(mode="json") for k, v in self._jobs.items()},
                ensure_ascii=False,
            ),
        )
        self._upsert(
            db,
            JsonStateRow,
            "characters",
            payload=json.dumps(
                {
                    k: [c.model_dump(mode="json") for c in v]
                    for k, v in self._characters.items()
                },
                ensure_ascii=False,
            ),
        )
        self._upsert(
            db,
            JsonStateRow,
            "relations",
            payload=json.dumps(
                {
                    k: [r.model_dump(mode="json") for r in v]
                    for k, v in self._relations.items()
                },
                ensure_ascii=False,
            ),
        )
        self._upsert(
            db,
            JsonStateRow,
            "meta",
            payload=json.dumps(
                {
                    "users": self._users,
                    "tokens": self._tokens,
                    "quota": {
                        uid: {
                            **q,
                            "reset_at": q["reset_at"].isoformat()
                            if isinstance(q.get("reset_at"), datetime)
                            else q.get("reset_at"),
                        }
                        for uid, q in self._quota.items()
                    },
                    "model_settings": self._model_settings,
                },
                ensure_ascii=False,
                default=str,
            ),
        )

    def create_book(
        self, payload: BookCreateRequest, owner_id: str = "anon"
    ) -> BookRead:
        book = super().create_book(payload, owner_id=owner_id)
        with self._session_factory() as db:
            self._upsert(
                db,
                BookRow,
                book.id,
                payload=json.dumps(
                    book.model_dump(mode="json"), ensure_ascii=False, default=str
                ),
                title=book.title,
                novel_id=book.novel_id,
                status=book.status,
                owner_id=book.owner_id,
            )
            db.commit()
        return book

    def update_book_status(self, book_id: str, status: str) -> BookRead | None:
        result = super().update_book_status(book_id, status)
        if result is not None:
            with self._session_factory() as db:
                self._upsert(
                    db,
                    BookRow,
                    book_id,
                    payload=json.dumps(
                        result.model_dump(mode="json"), ensure_ascii=False, default=str
                    ),
                    status=result.status,
                )
                db.commit()
        return result

    def create_session(self, payload: SessionCreateRequest) -> SessionRead:
        session = super().create_session(payload)
        with self._session_factory() as db:
            self._upsert(
                db,
                SessionRow,
                session.id,
                book_id=session.book_id,
                title=session.title,
                payload=json.dumps(
                    session.model_dump(mode="json"), ensure_ascii=False, default=str
                ),
            )
            self._flush_state(db)
            db.commit()
        return session

    def append_turn(self, session_id: str, turn: TurnRead) -> TurnRead:
        result = super().append_turn(session_id, turn)
        with self._session_factory() as db:
            self._upsert(
                db,
                TurnRow,
                turn.id,
                session_id=session_id,
                payload=json.dumps(
                    turn.model_dump(mode="json"), ensure_ascii=False, default=str
                ),
            )
            ses = self.get_session(session_id)
            if ses is not None:
                self._upsert(
                    db,
                    SessionRow,
                    session_id,
                    payload=json.dumps(
                        ses.model_dump(mode="json"), ensure_ascii=False, default=str
                    ),
                    title=ses.title,
                    book_id=ses.book_id,
                )
            db.commit()
        return result

    def add_memory(
        self, session_id: str, payload: MemoryCreateRequest, source: str = "manual"
    ) -> MemoryRead:
        item = super().add_memory(session_id, payload, source=source)
        with self._session_factory() as db:
            self._upsert(
                db,
                MemoryRow,
                item.id,
                session_id=session_id,
                payload=json.dumps(
                    item.model_dump(mode="json"), ensure_ascii=False, default=str
                ),
                pinned=item.pinned,
                enabled=item.enabled,
            )
            db.commit()
        return item

    def add_world_fact(self, book_id: str, payload: WorldFactRequest) -> WorldFactRead:
        item = super().add_world_fact(book_id, payload)
        with self._session_factory() as db:
            self._upsert(
                db,
                WorldFactRow,
                item.id,
                book_id=book_id,
                payload=json.dumps(
                    item.model_dump(mode="json"), ensure_ascii=False, default=str
                ),
                locked=item.locked,
            )
            db.commit()
        return item

    def update_distill_job(
        self, job_id: str, **fields: object
    ) -> DistillJobRead | None:
        result = super().update_distill_job(job_id, **fields)
        with self._session_factory() as db:
            self._flush_state(db)
            db.commit()
        return result

    def add_characters(self, book_id: str, items: list[CharacterRead]) -> None:
        super().add_characters(book_id, items)
        with self._session_factory() as db:
            self._flush_state(db)
            db.commit()

    def set_relations(self, book_id: str, edges: list[RelationEdgeRead]) -> None:
        super().set_relations(book_id, edges)
        with self._session_factory() as db:
            self._flush_state(db)
            db.commit()

    def create_anon_user(self, display_name: str) -> tuple[str, str]:
        result = super().create_anon_user(display_name)
        with self._session_factory() as db:
            self._flush_state(db)
            db.commit()
        return result

    def consume_quota(self, user_id: str, kind: str, limit: int) -> bool:
        ok = super().consume_quota(user_id, kind, limit)
        with self._session_factory() as db:
            self._flush_state(db)
            db.commit()
        return ok

    def set_model_settings(self, **fields: Any) -> dict[str, Any]:
        result = super().set_model_settings(**fields)
        with self._session_factory() as db:
            self._flush_state(db)
            db.commit()
        return result
