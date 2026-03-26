from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Protocol

import anyio

from social_ingestion_mcp.config import AppConfig
from social_ingestion_mcp.errors import DependencyNotAvailableError, RpaFocusLostError, UpstreamServiceError
from social_ingestion_mcp.rpa_node.models import WechatChannelsCaptureResult, WechatChannelsTaskCreateRequest


class WechatAutomator(Protocol):
    async def run(self, task_id: str, request: WechatChannelsTaskCreateRequest) -> WechatChannelsCaptureResult:
        ...


class DryRunWechatAutomator:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    async def run(self, task_id: str, request: WechatChannelsTaskCreateRequest) -> WechatChannelsCaptureResult:
        artifact_dir = self._config.wechat_rpa_output_root / task_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = artifact_dir / "visible_text.json"
        payload = {
            "source_url": request.source_url,
            "desktop_node_id": request.desktop_node_id,
            "mode": "dry-run",
            "title": "dry-run-wechat-channels-task",
            "raw_text": "这是本地 RPA 节点干跑结果，用于验证 MCP 到桌面节点的协议联通。",
        }
        async with await anyio.open_file(transcript_path, "w", encoding="utf-8") as file_obj:
            await file_obj.write(json.dumps(payload, ensure_ascii=False, indent=2))
        return WechatChannelsCaptureResult(
            title=payload["title"],
            raw_text=payload["raw_text"],
            video_path=None,
            cover_path=None,
            artifact_path=str(artifact_dir),
            metadata={
                "mode": "dry-run",
                "visible_text_path": str(transcript_path),
            },
        )


class RealWechatAutomator:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    async def run(self, task_id: str, request: WechatChannelsTaskCreateRequest) -> WechatChannelsCaptureResult:
        if not self._config.wechat_sniffer_command or not self._config.wechat_decrypt_command:
            raise DependencyNotAvailableError(
                "Real RPA mode requires SOCIAL_WECHAT_SNIFFER_COMMAND and SOCIAL_WECHAT_DECRYPT_COMMAND"
            )

        try:
            import pyautogui  # type: ignore
        except ImportError as exc:
            raise DependencyNotAvailableError("pyautogui is not installed") from exc

        artifact_dir = self._config.wechat_rpa_output_root / task_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        await self._focus_wechat_window()

        sniffer_result_path = artifact_dir / "sniffer_result.json"
        decrypt_result_path = artifact_dir / "decrypt_result.json"
        visible_text_path = artifact_dir / "visible_text.json"

        base_env = self._build_command_env(
            task_id=task_id,
            request=request,
            artifact_dir=artifact_dir,
            sniffer_result_path=sniffer_result_path,
            decrypt_result_path=decrypt_result_path,
            visible_text_path=visible_text_path,
        )

        await self._run_command(self._config.wechat_sniffer_command, base_env, artifact_dir)
        sniffer_payload = self._read_json(sniffer_result_path, required=True)

        if self._config.wechat_visible_text_command:
            await self._run_command(self._config.wechat_visible_text_command, base_env, artifact_dir)

        visible_payload = self._read_json(visible_text_path, required=False)

        sph_path = str(sniffer_payload.get("sph_path") or "").strip()
        video_path = str(sniffer_payload.get("video_path") or "").strip()
        decrypt_payload: dict[str, object] = {}
        if not video_path:
            if not sph_path:
                raise UpstreamServiceError(
                    "Sniffer command did not produce sph_path or video_path in sniffer_result.json"
                )
            decrypt_env = dict(base_env)
            decrypt_env["SOCIAL_SPH_PATH"] = sph_path
            await self._run_command(self._config.wechat_decrypt_command, decrypt_env, artifact_dir)
            decrypt_payload = self._read_json(decrypt_result_path, required=True)
            video_path = str(decrypt_payload.get("video_path") or "").strip()

        if not video_path:
            raise UpstreamServiceError("Decrypt command completed but did not produce video_path")

        metadata = {
            "mode": "real",
            "sniffer": sniffer_payload,
            "decrypt": decrypt_payload,
            "visible_text": visible_payload,
        }
        title = self._pick_first(
            visible_payload.get("title") if visible_payload else None,
            sniffer_payload.get("title"),
            decrypt_payload.get("title"),
        )
        raw_text = self._pick_first(
            visible_payload.get("raw_text") if visible_payload else None,
            sniffer_payload.get("raw_text"),
            decrypt_payload.get("raw_text"),
        )
        cover_path = self._pick_first(
            visible_payload.get("cover_path") if visible_payload else None,
            sniffer_payload.get("cover_path"),
            decrypt_payload.get("cover_path"),
        )
        return WechatChannelsCaptureResult(
            title=title,
            raw_text=raw_text,
            video_path=video_path,
            cover_path=cover_path,
            artifact_path=str(artifact_dir),
            metadata=metadata,
        )

    async def preflight(self) -> dict[str, object]:
        await self._focus_wechat_window()
        repo_state = {
            "sniffer_repo_candidates": [str(path) for path in self._config.candidate_wechat_sniffer_roots()],
            "decrypt_repo_candidates": [str(path) for path in self._config.candidate_wechat_decrypt_roots()],
        }
        checks = {
            "window_title": self._config.wechat_window_title,
            "sniffer_command": bool(self._config.wechat_sniffer_command),
            "decrypt_command": bool(self._config.wechat_decrypt_command),
            "visible_text_command": bool(self._config.wechat_visible_text_command),
            **repo_state,
        }
        if not self._config.wechat_sniffer_command or not self._config.wechat_decrypt_command:
            raise DependencyNotAvailableError(
                "Real mode preflight failed because sniffer or decrypt command is missing"
            )
        return checks

    async def _focus_wechat_window(self) -> None:
        if not self._config.wechat_window_title:
            raise RpaFocusLostError("WeChat window title is not configured")
        try:
            import pygetwindow as gw  # type: ignore
        except ImportError as exc:
            raise DependencyNotAvailableError("pygetwindow is not installed") from exc

        matches = [window for window in gw.getAllWindows() if self._config.wechat_window_title in window.title]
        if not matches:
            raise RpaFocusLostError(
                f"No desktop window matched title fragment: {self._config.wechat_window_title}"
            )
        window = matches[0]
        try:
            if window.isMinimized:
                window.restore()
            window.activate()
        except Exception as exc:
            if "Error code from Windows: 0" not in str(exc):
                raise RpaFocusLostError(f"Failed to activate WeChat window: {exc}") from exc
        await anyio.sleep(1.0)

    def _build_command_env(
        self,
        *,
        task_id: str,
        request: WechatChannelsTaskCreateRequest,
        artifact_dir: Path,
        sniffer_result_path: Path,
        decrypt_result_path: Path,
        visible_text_path: Path,
    ) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "SOCIAL_TASK_ID": task_id,
                "SOCIAL_SOURCE_URL": request.source_url,
                "SOCIAL_SOURCE_MESSAGE_ID": request.source_message_id or "",
                "SOCIAL_DESKTOP_NODE_ID": request.desktop_node_id,
                "SOCIAL_ARTIFACT_DIR": str(artifact_dir),
                "SOCIAL_SNIFFER_RESULT_PATH": str(sniffer_result_path),
                "SOCIAL_DECRYPT_RESULT_PATH": str(decrypt_result_path),
                "SOCIAL_VISIBLE_TEXT_PATH": str(visible_text_path),
            }
        )
        return env

    async def _run_command(self, command: str | None, env: dict[str, str], cwd: Path) -> None:
        if not command:
            raise DependencyNotAvailableError("Command is not configured")
        process = await anyio.open_process(
            command,
            shell=True,
            cwd=str(cwd),
            env=env,
            stderr=subprocess.STDOUT,
        )
        try:
            with anyio.fail_after(self._config.wechat_rpa_command_timeout_seconds):
                stdout, _ = await process.communicate()
        except TimeoutError:
            process.kill()
            raise UpstreamServiceError(f"Command timed out: {command}")
        if process.returncode != 0:
            message = stdout.decode("utf-8", errors="replace") if stdout else ""
            raise UpstreamServiceError(f"Command failed: {command}\n{message}")

    @staticmethod
    def _read_json(path: Path, *, required: bool) -> dict[str, object]:
        if not path.exists():
            if required:
                raise UpstreamServiceError(f"Expected JSON artifact was not created: {path}")
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _pick_first(*values: object) -> str | None:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return None


def build_automator(config: AppConfig) -> WechatAutomator:
    mode = config.wechat_rpa_node_mode.lower().strip()
    if mode == "dry-run":
        return DryRunWechatAutomator(config)
    return RealWechatAutomator(config)