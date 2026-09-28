"""后台任务队列：蒸馏/改写进入 asyncio 队列，API 立即返回 job。

F10 目标：不阻塞 HTTP、重启可观察进度。MVP 用进程内队列；
换 Redis/arq 时保持相同 Job 协议。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("dreamspace.queue")

TaskFn = Callable[[], Awaitable[Any]]


@dataclass
class JobHandle:
    id: str
    name: str
    status: str = "queued"
    result: Any = None
    error: str = ""
    waiters: list[asyncio.Future[Any]] = field(default_factory=list)


class TaskQueue:
    def __init__(self, workers: int = 2) -> None:
        self._queue: asyncio.Queue[tuple[str, TaskFn]] = asyncio.Queue()
        self._jobs: dict[str, JobHandle] = {}
        self._workers = workers
        self._tasks: list[asyncio.Task[None]] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        for i in range(self._workers):
            self._tasks.append(asyncio.create_task(self._worker(i)))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        self._started = False

    async def _worker(self, index: int) -> None:
        while True:
            job_id, fn = await self._queue.get()
            handle = self._jobs.get(job_id)
            if handle is None:
                self._queue.task_done()
                continue
            handle.status = "running"
            try:
                result = await fn()
                handle.result = result
                handle.status = "done"
                for fut in handle.waiters:
                    if not fut.done():
                        fut.set_result(result)
            except Exception as exc:
                handle.status = "failed"
                handle.error = str(exc)
                logger.exception("job %s failed", job_id)
                for fut in handle.waiters:
                    if not fut.done():
                        fut.set_exception(exc)
            finally:
                self._queue.task_done()

    def submit(self, name: str, fn: TaskFn) -> JobHandle:
        job_id = f"task-{len(self._jobs) + 1}"
        handle = JobHandle(id=job_id, name=name)
        self._jobs[job_id] = handle
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 无事件循环：同步退化执行
            handle.status = "running"
            try:
                # 不能在无 loop 时跑 async；标记失败并提示
                handle.status = "failed"
                handle.error = "no running event loop"
            except Exception as exc:  # noqa: BLE001
                handle.error = str(exc)
            return handle
        self._queue.put_nowait((job_id, fn))
        _ = loop
        return handle

    def get(self, job_id: str) -> JobHandle | None:
        return self._jobs.get(job_id)

    async def wait(self, job_id: str) -> Any:
        handle = self._jobs[job_id]
        if handle.status == "done":
            return handle.result
        if handle.status == "failed":
            raise RuntimeError(handle.error or "job failed")
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        handle.waiters.append(fut)
        return await fut


_queue: TaskQueue | None = None


def get_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue
