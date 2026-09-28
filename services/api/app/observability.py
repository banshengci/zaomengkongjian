"""轻量观测：阶段耗时与安全截断日志。禁止记录完整原文/密钥。"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger("dreamspace")

_MAX_LOG_CHARS = 200


def safe_text(value: str, limit: int = _MAX_LOG_CHARS) -> str:
    text = value.replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


@contextmanager
def timed(stage: str, **fields: object) -> Iterator[dict[str, object]]:
    started = time.perf_counter()
    payload: dict[str, object] = {"stage": stage, **fields}
    try:
        yield payload
    finally:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        payload["elapsed_ms"] = elapsed_ms
        logger.info(
            "stage=%s elapsed_ms=%s fields=%s",
            stage,
            elapsed_ms,
            {k: v for k, v in fields.items()},
        )
