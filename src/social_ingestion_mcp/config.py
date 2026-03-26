from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SOCIAL_",
        extra="ignore",
    )

    server_name: str = "social-ingestion-mcp"
    server_version: str = "0.1.0"
    dry_run: bool = True

    storage_root: Path = Field(default=Path("./runtime"))
    media_root: Path = Field(default=Path("./runtime/media"))
    xhs_workdir: Path = Field(default=Path("./runtime/xhs"))
    vendor_root: Path = Field(default=Path("./vendor"))

    xhs_cookie: str = ""
    xhs_proxy: str | None = None
    xhs_timeout_seconds: float = 20.0
    xhs_repo_path: Path | None = None

    wechat_rpa_base_url: str = "http://127.0.0.1:8091"
    wechat_rpa_timeout_seconds: float = 180.0
    wechat_rpa_poll_interval_seconds: float = 2.0
    wechat_rpa_command_timeout_seconds: float = 120.0
    wechat_rpa_node_id: str = "local-desktop-node"
    wechat_rpa_node_mode: str = "dry-run"
    wechat_rpa_output_root: Path = Field(default=Path("./runtime/wechat"))
    wechat_window_title: str = "微信"
    wechat_sniffer_repo_path: Path | None = None
    wechat_decrypt_repo_path: Path | None = None
    wechat_sniffer_command: str | None = None
    wechat_decrypt_command: str | None = None
    wechat_visible_text_command: str | None = None

    stt_provider: str = "whisper-local"
    whisper_model: str = "base"
    llm_cleaning_model: str = "gpt-4.1-mini"
    llm_api_base: str | None = None
    llm_api_key: str | None = None

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_bitable_app_token: str = ""
    feishu_bitable_table_id: str = ""
    feishu_bitable_force_write: bool = False
    feishu_bitable_user_id_type: str = "user_id"
    feishu_bitable_unique_field: str = "Job ID"
    feishu_bitable_job_id_field: str = "Job ID"
    feishu_bitable_platform_field: str = "Platform"
    feishu_bitable_source_url_field: str = "Source URL"
    feishu_bitable_source_title_field: str = "Source Title"
    feishu_bitable_cleaned_text_field: str = "Cleaned Text"
    feishu_bitable_transcript_field: str = "Transcript Text"
    feishu_bitable_status_field: str = "Status"
    feishu_bitable_media_path_field: str = "Media Path"
    feishu_bitable_source_message_id_field: str = "Source Message ID"
    feishu_bitable_metadata_field: str = "Metadata"
    feishu_bitable_extra_field_map_json: str = "{}"

    def ensure_directories(self) -> None:
        for path in (
            self.storage_root,
            self.media_root,
            self.xhs_workdir,
            self.vendor_root,
            self.wechat_rpa_output_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def extra_bitable_field_map(self) -> dict[str, str]:
        raw = self.feishu_bitable_extra_field_map_json.strip() or "{}"
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("SOCIAL_FEISHU_BITABLE_EXTRA_FIELD_MAP_JSON must be a JSON object")
        result: dict[str, str] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                result[key] = value
        return result

    def candidate_xhs_repo_roots(self) -> list[Path]:
        candidates = [
            self.xhs_repo_path,
            self.vendor_root / "XHS-Downloader",
            self.vendor_root / "xhs-downloader",
        ]
        return [path for path in candidates if path is not None]

    def candidate_wechat_sniffer_roots(self) -> list[Path]:
        candidates = [
            self.wechat_sniffer_repo_path,
            self.vendor_root / "WechatVideoSniffer2.0",
            self.vendor_root / "wx_channels_download",
        ]
        return [path for path in candidates if path is not None]

    def candidate_wechat_decrypt_roots(self) -> list[Path]:
        candidates = [
            self.wechat_decrypt_repo_path,
            self.vendor_root / "WechatSphDecrypt",
        ]
        return [path for path in candidates if path is not None]