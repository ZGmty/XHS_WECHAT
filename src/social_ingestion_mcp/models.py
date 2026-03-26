from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Platform(str, Enum):
    XHS = "xiaohongshu"
    WECHAT_CHANNELS = "wechat_channels"


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStage(str, Enum):
    ACCEPTED = "accepted"
    RPA_QUEUED = "rpa_queued"
    FETCHING_SOURCE = "fetching_source"
    DOWNLOADING_MEDIA = "downloading_media"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING_AUDIO = "transcribing_audio"
    CLEANING_TEXT = "cleaning_text"
    WRITING_BITABLE = "writing_bitable"
    FINISHED = "finished"


class IngestionRequest(BaseModel):
    source_url: str
    source_message_id: str | None = None
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    bitable_table_id: str | None = None


class XhsIngestionRequest(IngestionRequest):
    pass


class WechatChannelsIngestionRequest(IngestionRequest):
    desktop_node_id: str = "local-desktop-node"


class SourceMedia(BaseModel):
    title: str | None = None
    source_url: str
    raw_text: str | None = None
    video_path: str | None = None
    audio_path: str | None = None
    cover_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessedContent(BaseModel):
    transcript_text: str = ""
    cleaned_text: str = ""
    language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobResultPreview(BaseModel):
    bitable_record_id: str | None = None
    media_path: str | None = None
    transcript_chars: int = 0
    cleaned_text_chars: int = 0


class IngestionJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    platform: Platform
    state: JobState = JobState.QUEUED
    stage: JobStage = JobStage.ACCEPTED
    source_url: str
    source_message_id: str | None = None
    request_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    queue_position: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    result_preview: JobResultPreview | None = None


class ToolSubmission(BaseModel):
    job_id: str
    platform: Platform
    status: JobState
    queue_position: int | None = None
    message: str


class JobStatusResponse(BaseModel):
    job: IngestionJob


class RpaQueueState(BaseModel):
    is_busy: bool
    current_job_id: str | None = None
    waiting_jobs: int = 0


class BitableWritePayload(BaseModel):
    job_id: str
    platform: Platform
    source_url: str
    source_title: str | None = None
    cleaned_text: str = ""
    transcript_text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)