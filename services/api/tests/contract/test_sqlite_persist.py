"""SQLite 持久化：重启后书卷/会话/记忆仍在。"""

from __future__ import annotations

from pathlib import Path

from app.domain.schemas import (
    BookCreateRequest,
    MemoryCreateRequest,
    SessionCreateRequest,
    TurnMessage,
    TurnRead,
    utc_now,
)
from app.store.sqlite_store import SqliteStore


def test_sqlite_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "test.db"

    store = SqliteStore(db)
    book = store.create_book(BookCreateRequest(title="持久书", novel_id="p1"))
    session = store.create_session(
        SessionCreateRequest(
            book_id=book.id, mode="observe", participants=["甲", "乙"], title="夜谈"
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
        session.id,
        MemoryCreateRequest(text="约定三日后再会", category="story", pinned=True),
    )

    reopened = SqliteStore(db)
    books = reopened.list_books()
    assert any(b.title == "持久书" for b in books)
    loaded = reopened.get_session(session.id)
    assert loaded is not None
    assert loaded.title == "夜谈"
    assert loaded.transcript_count == 1
    mems = reopened.list_memories(session.id)
    assert mems and mems[0].text == "约定三日后再会"
    assert reopened.get_book(book.id) is not None
    _ = utc_now()
