from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import anyio
import httpx

from social_ingestion_mcp.config import AppConfig
from social_ingestion_mcp.errors import (
    AntiScrapingBlockedError,
    DependencyNotAvailableError,
    NetworkTimeoutError,
)
from social_ingestion_mcp.models import SourceMedia, XhsIngestionRequest


class XhsDownloaderAdapter:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    async def fetch(self, job_id: str, request: XhsIngestionRequest) -> SourceMedia:
        if self._config.dry_run:
            return SourceMedia(
                title="dry-run-xhs-post",
                source_url=request.source_url,
                raw_text="这是一个用于联调 MCP Server 的小红书干跑样例。",
                metadata={"mode": "dry-run", "job_id": job_id},
            )

        xhs_cls = self._load_xhs_cls()
        try:
            async with xhs_cls(
                work_path=str(self._config.xhs_workdir),
                cookie=self._config.xhs_cookie,
                proxy=self._config.xhs_proxy,
                timeout=self._config.xhs_timeout_seconds,
                download_record=False,
                image_download=False,
                video_download=False,
                live_download=False,
            ) as xhs:
                results = await xhs.extract(request.source_url, download=False, data=True)
        except TimeoutError as exc:
            raise NetworkTimeoutError("XHS request timed out") from exc
        except Exception as exc:
            raise AntiScrapingBlockedError(f"XHS extraction failed: {exc}") from exc

        if not results:
            raise AntiScrapingBlockedError("XHS returned no extractable data")

        primary = results[0]
        raw_text = "\n".join(
            part for part in (primary.get("作品标题"), primary.get("作品描述")) if part
        )
        video_url = self._get_primary_video_url(primary)
        video_path = None
        if video_url:
            video_path = await self._download_media(job_id, video_url)

        return SourceMedia(
            title=primary.get("作品标题"),
            source_url=request.source_url,
            raw_text=raw_text,
            video_path=str(video_path) if video_path else None,
            metadata={"xhs_raw": primary},
        )

    @staticmethod
    def _load_xhs_cls_from_module(module_name: str, attribute: str) -> Any:
        module = importlib.import_module(module_name)
        return getattr(module, attribute)

    def _load_xhs_cls(self) -> Any:
        for root in self._config.candidate_xhs_repo_roots():
            if root.exists():
                root_str = str(root)
                if root_str not in sys.path:
                    sys.path.insert(0, root_str)
        candidates = (
            ("source", "XHS"),
            ("xhs_downloader", "XHS"),
        )
        for module_name, attribute in candidates:
            try:
                return self._load_xhs_cls_from_module(module_name, attribute)
            except (ImportError, AttributeError):
                continue
        raise DependencyNotAvailableError(
            "XHS-Downloader is not available. Sync or configure a local repository path first"
        )

    @staticmethod
    def _get_primary_video_url(payload: dict[str, Any]) -> str | None:
        candidates = payload.get("下载地址") or []
        if isinstance(candidates, list) and candidates:
            return str(candidates[0])
        return None

    async def _download_media(self, job_id: str, media_url: str) -> Path:
        target = self._config.media_root / f"{job_id}.mp4"
        try:
            async with httpx.AsyncClient(timeout=self._config.xhs_timeout_seconds) as client:
                async with client.stream("GET", media_url) as response:
                    response.raise_for_status()
                    async with await anyio.open_file(target, "wb") as file_obj:
                        async for chunk in response.aiter_bytes():
                            await file_obj.write(chunk)
        except httpx.TimeoutException as exc:
            raise NetworkTimeoutError("Timed out downloading XHS media") from exc
        except httpx.HTTPError as exc:
            raise AntiScrapingBlockedError(f"Failed to download XHS media: {exc}") from exc
        return target