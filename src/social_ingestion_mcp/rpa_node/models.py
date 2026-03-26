from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RpaTaskStatus(str, Enum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WechatChannelsTaskCreateRequest(BaseModel):
    job_id: str
    source_url: str
    desktop_node_id: str
    source_message_id: str | None = None
    playback_wait_seconds: float = 8.0
    focus_retry_limit: int = 2
    metadata: dict[str, Any] = Field(default_factory=dict)


class WechatChannelsTaskAccepted(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    status: RpaTaskStatus = RpaTaskStatus.ACCEPTED
    queue_position: int | None = None
    accepted_at: datetime = Field(default_factory=utc_now)
    message: str = "task accepted"


class WechatChannelsCaptureResult(BaseModel):
    title: str | None = None
    raw_text: str | None = None
    video_path: str | None = None
    cover_path: str | None = None
    artifact_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WechatChannelsTaskStatus(BaseModel):
    task_id: str
    job_id: str
    status: RpaTaskStatus
    queue_position: int | None = None
    phase: str | None = None
    progress: float | None = None
    error_code: str | None = None
    error_message: str | None = None
    result: WechatChannelsCaptureResult | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class RpaNodeHealth(BaseModel):
    node_id: str
    status: str = "ok"
    is_busy: bool = False
    waiting_jobs: int = 0
    current_task_id: str | None = None
    supports_platforms: list[str] = Field(default_factory=lambda: ["wechat_channels"])
    updated_at: datetime = Field(default_factory=utc_now)