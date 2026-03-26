from __future__ import annotations

import anyio
import httpx

from social_ingestion_mcp.config import AppConfig
from social_ingestion_mcp.errors import NetworkTimeoutError, RpaFocusLostError, UpstreamServiceError
from social_ingestion_mcp.models import SourceMedia, WechatChannelsIngestionRequest
from social_ingestion_mcp.rpa_node.models import (
    RpaTaskStatus,
    WechatChannelsTaskAccepted,
    WechatChannelsTaskCreateRequest,
    WechatChannelsTaskStatus,
)


class WechatRpaAdapter:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    async def capture(self, job_id: str, request: WechatChannelsIngestionRequest) -> SourceMedia:
        if self._config.dry_run:
            return SourceMedia(
                title="dry-run-wechat-video",
                source_url=request.source_url,
                raw_text="这是一个用于联调 RPA 队列的微信视频号干跑样例。",
                metadata={"mode": "dry-run", "job_id": job_id, "desktop_node_id": request.desktop_node_id},
            )

        payload = WechatChannelsTaskCreateRequest(
            job_id=job_id,
            source_url=request.source_url,
            desktop_node_id=request.desktop_node_id,
            source_message_id=request.source_message_id,
        )
        try:
            async with httpx.AsyncClient(timeout=self._config.wechat_rpa_timeout_seconds) as client:
                response = await client.post(
                    f"{self._config.wechat_rpa_base_url}/tasks/wechat-channels",
                    json=payload.model_dump(mode="json"),
                )
                if response.status_code == 409:
                    raise RpaFocusLostError("RPA desktop focus lost")
                response.raise_for_status()
                accepted = WechatChannelsTaskAccepted.model_validate(response.json())

                deadline = anyio.current_time() + self._config.wechat_rpa_timeout_seconds
                while True:
                    status_response = await client.get(
                        f"{self._config.wechat_rpa_base_url}/tasks/{accepted.task_id}"
                    )
                    status_response.raise_for_status()
                    status = WechatChannelsTaskStatus.model_validate(status_response.json())

                    if status.status == RpaTaskStatus.SUCCEEDED:
                        if status.result is None:
                            raise UpstreamServiceError("RPA node returned success without result payload")
                        return SourceMedia(
                            title=status.result.title,
                            source_url=request.source_url,
                            raw_text=status.result.raw_text,
                            video_path=status.result.video_path,
                            cover_path=status.result.cover_path,
                            metadata=status.result.metadata,
                        )

                    if status.status == RpaTaskStatus.FAILED:
                        if status.error_code == "rpa_focus_lost":
                            raise RpaFocusLostError(status.error_message or "RPA desktop focus lost")
                        raise UpstreamServiceError(status.error_message or "RPA node task failed")

                    if status.status == RpaTaskStatus.CANCELLED:
                        raise UpstreamServiceError("RPA node task was cancelled")

                    if anyio.current_time() >= deadline:
                        raise NetworkTimeoutError("Timed out while polling RPA node task")

                    await anyio.sleep(self._config.wechat_rpa_poll_interval_seconds)
        except httpx.TimeoutException as exc:
            raise NetworkTimeoutError("Timed out while waiting for RPA node") from exc
        except httpx.HTTPStatusError as exc:
            raise UpstreamServiceError(
                f"RPA node returned unexpected status: {exc.response.status_code}"
            ) from exc