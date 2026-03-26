from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from social_ingestion_mcp.models import RpaQueueState

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class QueueItem:
    job_id: str
    handler: Callable[[], Awaitable[None]]


class SingleFlightRpaQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._current_job_id: str | None = None

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker(), name="wechat-rpa-queue")

    async def stop(self) -> None:
        if self._worker_task is None:
            return
        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass
        self._worker_task = None

    async def enqueue(self, job_id: str, handler: Callable[[], Awaitable[None]]) -> int:
        queue_position = self._queue.qsize() + 1
        await self._queue.put(QueueItem(job_id=job_id, handler=handler))
        return queue_position

    def snapshot(self) -> RpaQueueState:
        return RpaQueueState(
            is_busy=self._current_job_id is not None,
            current_job_id=self._current_job_id,
            waiting_jobs=self._queue.qsize(),
        )

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            self._current_job_id = item.job_id
            try:
                await item.handler()
            except Exception:
                logger.exception("Unhandled exception while processing RPA job %s", item.job_id)
            finally:
                self._current_job_id = None
                self._queue.task_done()