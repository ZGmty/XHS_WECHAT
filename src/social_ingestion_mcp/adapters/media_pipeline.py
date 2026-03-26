from __future__ import annotations

from pathlib import Path

import ffmpeg

from social_ingestion_mcp.config import AppConfig
from social_ingestion_mcp.errors import DependencyNotAvailableError, UpstreamServiceError
from social_ingestion_mcp.models import ProcessedContent, SourceMedia


class MediaPipelineAdapter:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    async def ensure_audio(self, job_id: str, source: SourceMedia) -> SourceMedia:
        audio_path = source.audio_path
        if audio_path or not source.video_path:
            return source
        audio_path = await self._extract_audio(job_id, Path(source.video_path))
        return source.model_copy(update={"audio_path": str(audio_path)})

    async def transcribe(self, source: SourceMedia) -> str:
        return await self._transcribe(source)

    async def clean_text(self, source: SourceMedia, transcript: str) -> ProcessedContent:
        cleaned_text = await self._clean_text(source, transcript)
        return ProcessedContent(
            transcript_text=transcript,
            cleaned_text=cleaned_text,
            metadata={"audio_path": source.audio_path},
        )

    async def _extract_audio(self, job_id: str, video_path: Path) -> Path:
        output_path = self._config.media_root / f"{job_id}.wav"
        try:
            stream = ffmpeg.input(str(video_path))
            stream = ffmpeg.output(stream, str(output_path), ac=1, ar=16000)
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
        except ffmpeg.Error as exc:
            raise UpstreamServiceError(f"ffmpeg extraction failed: {exc}") from exc
        return output_path

    async def _transcribe(self, source: SourceMedia) -> str:
        if source.audio_path and self._config.stt_provider == "whisper-local":
            try:
                import whisper  # type: ignore
            except ImportError as exc:
                raise DependencyNotAvailableError(
                    "openai-whisper is not installed"
                ) from exc

            model = whisper.load_model(self._config.whisper_model)
            result = model.transcribe(source.audio_path)
            return str(result.get("text") or "").strip()

        return (source.raw_text or "").strip()

    async def _clean_text(self, source: SourceMedia, transcript: str) -> str:
        if not transcript:
            return ""

        normalized = " ".join(transcript.split())
        if source.raw_text:
            return "\n".join(part for part in (source.raw_text.strip(), normalized) if part)
        return normalized