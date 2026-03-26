from __future__ import annotations

import asyncio
from dataclasses import dataclass

from social_ingestion_mcp.config import AppConfig
from social_ingestion_mcp.errors import RpaFocusLostError, SocialIngestionError
from social_ingestion_mcp.rpa_node.automation import WechatAutomator
from social_ingestion_mcp.rpa_node.models import (
    RpaNodeHealth,
    RpaTaskStatus,
    WechatChannelsTaskAccepted,
    WechatChannelsTaskCreateRequest,
    WechatChannelsTaskStatus,
    utc_now,
)


@dataclass(slots=True)
class QueueItem:
    task_id: str
    request: WechatChannelsTaskCreateRequest


class WechatRpaNodeService:
    def __init__(self, config: AppConfig, automator: WechatAutomator) -> None:
        self._config = config
        self._automator = automator
        self._tasks: dict[str, WechatChannelsTaskStatus] = {}
        self._queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self._current_task_id: str | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker(), name="wechat-rpa-node-worker")

    async def stop(self) -> None:
        if self._worker_task is None:
            return
        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass
        self._worker_task = None

    async def submit(self, request: WechatChannelsTaskCreateRequest) -> WechatChannelsTaskAccepted:
        accepted = WechatChannelsTaskAccepted(
            job_id=request.job_id,
            queue_position=self._queue.qsize() + 1,
            message="task accepted",
        )
        status = WechatChannelsTaskStatus(
            task_id=accepted.task_id,
            job_id=request.job_id,
            status=RpaTaskStatus.QUEUED,
            queue_position=accepted.queue_position,
            phase="queued",
            progress=0.0,
        )
        async with self._lock:
            self._tasks[accepted.task_id] = status
        await self._queue.put(QueueItem(task_id=accepted.task_id, request=request))
        return accepted

    async def get_task(self, task_id: str) -> WechatChannelsTaskStatus | None:
        async with self._lock:
            return self._tasks.get(task_id)

    async def health(self) -> RpaNodeHealth:
        return RpaNodeHealth(
            node_id=self._config.wechat_rpa_node_id,
            is_busy=self._current_task_id is not None,
            waiting_jobs=self._queue.qsize(),
            current_task_id=self._current_task_id,
        )

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            self._current_task_id = item.task_id
            try:
                await self._set_status(
                    item.task_id,
                    status=RpaTaskStatus.RUNNING,
                    queue_position=None,
                    phase="focusing_wechat",
                    progress=0.1,
                )
                result = await self._automator.run(item.task_id, item.request)
                await self._set_status(
                    item.task_id,
                    status=RpaTaskStatus.SUCCEEDED,
                    phase="completed",
                    progress=1.0,
                    result=result,
                    error_code=None,
                    error_message=None,
                )
            except RpaFocusLostError as exc:
                await self._set_status(
                    item.task_id,
                    status=RpaTaskStatus.FAILED,
                    phase="focusing_wechat",
                    progress=1.0,
                    error_code="rpa_focus_lost",
                    error_message=str(exc),
                )
            except SocialIngestionError as exc:
                await self._set_status(
                    item.task_id,
                    status=RpaTaskStatus.FAILED,
                    phase="processing_failed",
                    progress=1.0,
                    error_code=exc.code,
                    error_message=str(exc),
                )
            except NotImplementedError as exc:
                await self._set_status(
                    item.task_id,
                    status=RpaTaskStatus.FAILED,
                    phase="not_implemented",
                    progress=1.0,
                    error_code="not_implemented",
                    error_message=str(exc),
                )
            except Exception as exc:
                await self._set_status(
                    item.task_id,
                    status=RpaTaskStatus.FAILED,
                    phase="unexpected_error",
                    progress=1.0,
                    error_code="unexpected_error",
                    error_message=str(exc),
                )
            finally:
                self._current_task_id = None
                self._queue.task_done()

    async def _set_status(self, task_id: str, **changes) -> None:
        async with self._lock:
            current = self._tasks[task_id]
            self._tasks[task_id] = current.model_copy(update={**changes, "updated_at": utc_now()})