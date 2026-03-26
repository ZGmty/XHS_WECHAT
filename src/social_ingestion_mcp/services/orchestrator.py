from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from social_ingestion_mcp.adapters.bitable_adapter import FeishuBitableAdapter
from social_ingestion_mcp.adapters.media_pipeline import MediaPipelineAdapter
from social_ingestion_mcp.adapters.wechat_rpa_adapter import WechatRpaAdapter
from social_ingestion_mcp.adapters.xhs_adapter import XhsDownloaderAdapter
from social_ingestion_mcp.errors import JobNotFoundError, SocialIngestionError
from social_ingestion_mcp.models import (
    BitableWritePayload,
    IngestionJob,
    JobResultPreview,
    JobStage,
    JobState,
    JobStatusResponse,
    Platform,
    ToolSubmission,
    WechatChannelsIngestionRequest,
    XhsIngestionRequest,
    utc_now,
)
from social_ingestion_mcp.services.rpa_queue import SingleFlightRpaQueue


class IngestionOrchestrator:
    def __init__(
        self,
        *,
        xhs_adapter: XhsDownloaderAdapter,
        wechat_adapter: WechatRpaAdapter,
        media_pipeline: MediaPipelineAdapter,
        bitable_adapter: FeishuBitableAdapter,
        rpa_queue: SingleFlightRpaQueue,
    ) -> None:
        self._xhs_adapter = xhs_adapter
        self._wechat_adapter = wechat_adapter
        self._media_pipeline = media_pipeline
        self._bitable_adapter = bitable_adapter
        self._rpa_queue = rpa_queue
        self._jobs: dict[str, IngestionJob] = {}
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()

    async def submit_xhs(self, request: XhsIngestionRequest) -> ToolSubmission:
        job = IngestionJob(
            platform=Platform.XHS,
            source_url=request.source_url,
            source_message_id=request.source_message_id,
            request_id=request.request_id,
        )
        await self._save_job(job)
        task = asyncio.create_task(self._run_xhs(job.job_id, request), name=f"xhs-{job.job_id}")
        self._track(task)
        return ToolSubmission(
            job_id=job.job_id,
            platform=job.platform,
            status=job.state,
            message="XHS ingestion accepted",
        )

    async def submit_wechat(self, request: WechatChannelsIngestionRequest) -> ToolSubmission:
        job = IngestionJob(
            platform=Platform.WECHAT_CHANNELS,
            stage=JobStage.RPA_QUEUED,
            source_url=request.source_url,
            source_message_id=request.source_message_id,
            request_id=request.request_id,
        )
        await self._save_job(job)
        queue_position = await self._rpa_queue.enqueue(
            job.job_id,
            lambda: self._run_wechat(job.job_id, request),
        )
        await self._update_job(
            job.job_id,
            queue_position=queue_position,
            stage=JobStage.RPA_QUEUED,
        )
        return ToolSubmission(
            job_id=job.job_id,
            platform=job.platform,
            status=JobState.QUEUED,
            queue_position=queue_position,
            message="WeChat Channels ingestion queued in single-flight RPA lane",
        )

    async def get_job(self, job_id: str) -> JobStatusResponse:
        async with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(f"Unknown job id: {job_id}")
        return JobStatusResponse(job=job)

    async def _run_xhs(self, job_id: str, request: XhsIngestionRequest) -> None:
        await self._run_pipeline(job_id, request, Platform.XHS, lambda: self._xhs_adapter.fetch(job_id, request))

    async def _run_wechat(self, job_id: str, request: WechatChannelsIngestionRequest) -> None:
        await self._run_pipeline(
            job_id,
            request,
            Platform.WECHAT_CHANNELS,
            lambda: self._wechat_adapter.capture(job_id, request),
        )

    async def _run_pipeline(
        self,
        job_id: str,
        request: XhsIngestionRequest | WechatChannelsIngestionRequest,
        platform: Platform,
        source_loader: Callable[[], Awaitable],
    ) -> None:
        try:
            await self._update_job(job_id, state=JobState.RUNNING, stage=JobStage.FETCHING_SOURCE, queue_position=None)
            source = await source_loader()

            if source.video_path and not source.audio_path:
                await self._update_job(job_id, stage=JobStage.EXTRACTING_AUDIO)
                source = await self._media_pipeline.ensure_audio(job_id, source)

            await self._update_job(job_id, stage=JobStage.TRANSCRIBING_AUDIO)
            transcript = await self._media_pipeline.transcribe(source)

            await self._update_job(job_id, stage=JobStage.CLEANING_TEXT)
            processed = await self._media_pipeline.clean_text(source, transcript)

            await self._update_job(job_id, stage=JobStage.WRITING_BITABLE)
            record_id = await self._bitable_adapter.upsert_record(
                BitableWritePayload(
                    job_id=job_id,
                    platform=platform,
                    source_url=request.source_url,
                    source_title=source.title,
                    cleaned_text=processed.cleaned_text,
                    transcript_text=processed.transcript_text,
                    metadata={
                        **source.metadata,
                        "media_path": source.video_path or source.audio_path,
                        "source_message_id": request.source_message_id,
                        "bitable_table_id": request.bitable_table_id,
                    },
                )
            )

            await self._update_job(
                job_id,
                state=JobState.SUCCEEDED,
                stage=JobStage.FINISHED,
                result_preview=JobResultPreview(
                    bitable_record_id=record_id,
                    media_path=source.video_path or source.audio_path,
                    transcript_chars=len(processed.transcript_text),
                    cleaned_text_chars=len(processed.cleaned_text),
                ),
            )
        except SocialIngestionError as exc:
            await self._update_job(
                job_id,
                state=JobState.FAILED,
                error_code=exc.code,
                error_message=str(exc),
            )
        except NotImplementedError as exc:
            await self._update_job(
                job_id,
                state=JobState.FAILED,
                error_code="not_implemented",
                error_message=str(exc),
            )
        except Exception as exc:
            await self._update_job(
                job_id,
                state=JobState.FAILED,
                error_code="unexpected_error",
                error_message=str(exc),
            )

    async def _save_job(self, job: IngestionJob) -> None:
        async with self._lock:
            self._jobs[job.job_id] = job

    async def _update_job(self, job_id: str, **changes) -> None:
        async with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = current.model_copy(update={**changes, "updated_at": utc_now()})

    def _track(self, task: asyncio.Task[None]) -> None:
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)