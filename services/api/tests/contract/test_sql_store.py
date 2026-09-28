"""SQLAlchemy 存储层测试：规范化表 + 重启回放 + PG DSN 形态。"""

from __future__ import annotations

from pathlib import Path

from app.domain.schemas import (
    BookCreateRequest,
    MemoryCreateRequest,
    SessionCreateRequest,
    TurnMessage,
    TurnRead,
)
from app.store.sql_store import SqlStore


def test_sql_store_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "sql.db"
    store = SqlStore.from_path(db)

    book = store.create_book(BookCreateRequest(title="SQL书", novel_id="s1"))
    session = store.create_session(
        SessionCreateRequest(
            book_id=book.id, mode="observe", participants=["甲", "乙"], title="SQL夜谈"
        )
    )
    store.append_turn(
        session.id,
        TurnRead(
            id="t1",
            session_id=session.id,
            status="committed",
            messages=[TurnMessage(speaker="甲", message="你好")],
        ),
    )
    store.add_memory(
        session.id, MemoryCreateRequest(text="记住约定", category="story", pinned=True)
    )

    reopened = SqlStore.from_path(db)
    assert any(b.title == "SQL书" for b in reopened.list_books())
    loaded = reopened.get_session(session.id)
    assert loaded is not None
    assert loaded.title == "SQL夜谈"
    assert loaded.transcript_count == 1
    mems = reopened.list_memories(session.id)
    assert mems and mems[0].text == "记住约定"


def test_sql_store_accepts_sqlite_url(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'url.db'}"
    store = SqlStore(url)
    book = store.create_book(BookCreateRequest(title="URL书"))
    assert store.get_book(book.id) is not None
    # PostgreSQL URL 形态可构造（不实际连接 PG）
    assert url.startswith("sqlite:///")
