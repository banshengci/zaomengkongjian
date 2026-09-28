"""存储工厂：默认 SQLite 持久化，测试可用内存。"""

from __future__ import annotations

import os
import threading

from app.store.memory import MemoryStore

_store: MemoryStore | None = None
_store_lock = threading.Lock()


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                mode = os.environ.get("DREAMSPACE_STORE", "sql")
                if mode == "memory":
                    from app.store.memory import MemoryStore as _MS

                    _store = _MS()
                elif mode == "sqlite":
                    from pathlib import Path

                    from app.config import get_settings
                    from app.store.sqlite_store import SqliteStore

                    db_path = Path(
                        os.environ.get("DREAMSPACE_DB_PATH")
                        or (get_settings().data_dir / "dreamspace.db")
                    )
                    _store = SqliteStore(db_path)
                else:
                    # sql / postgres：SQLAlchemy 层（默认 SQLite 文件，PG 换 DSN）
                    from pathlib import Path

                    from app.config import get_settings
                    from app.store.sql_store import SqlStore

                    dsn = os.environ.get("DREAMSPACE_DATABASE_URL") or ""
                    if dsn:
                        _store = SqlStore(dsn)
                    else:
                        db_path = Path(
                            os.environ.get("DREAMSPACE_DB_PATH")
                            or (get_settings().data_dir / "dreamspace.db")
                        )
                        _store = SqlStore.from_path(db_path)
    return _store


def reset_store() -> MemoryStore:
    """测试用：重置为内存存储。"""
    global _store
    with _store_lock:
        from app.store.memory import MemoryStore as _MS

        _store = _MS()
    return _store
