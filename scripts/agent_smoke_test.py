from __future__ import annotations

import argparse
import asyncio
import os
import socket
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run agent-friendly smoke tests for the social ingestion project")
    parser.add_argument("--target", choices=("all", "rpa", "mcp"), default="all")
    parser.add_argument("--xhs-url", default="https://www.xiaohongshu.com/explore/demo")
    parser.add_argument("--wechat-url", default="https://channels.weixin.qq.com/example")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args()


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_env(*, dry_run: bool, rpa_base_url: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    src = str(SRC_ROOT)
    env["PYTHONPATH"] = src if not python_path else src + os.pathsep + python_path
    env["SOCIAL_DRY_RUN"] = "true" if dry_run else "false"
    env["SOCIAL_WECHAT_RPA_NODE_MODE"] = "dry-run"
    env["SOCIAL_WECHAT_RPA_NODE_ID"] = "local-desktop-node"
    if rpa_base_url:
        env["SOCIAL_WECHAT_RPA_BASE_URL"] = rpa_base_url
    return env


def wait_for_http_ready(url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    with httpx.Client(timeout=3.0) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(url)
                if response.is_success:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(1.0)
    raise TimeoutError(f"Timed out waiting for {url}")


def start_rpa_node(timeout_seconds: float) -> tuple[subprocess.Popen[str], str]:
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    command = [
        sys.executable,
        "-m",
        "social_ingestion_mcp.rpa_node.server",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    process = subprocess.Popen(
        command,
        cwd=str(REPO_ROOT),
        env=build_env(dry_run=True),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    wait_for_http_ready(f"{base_url}/health", timeout_seconds)
    return process, base_url


def terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def run_rpa_smoke_test(base_url: str, wechat_url: str, timeout_seconds: float) -> dict[str, Any]:
    payload = {
        "job_id": "agent-rpa-smoke-test",
        "source_url": wechat_url,
        "desktop_node_id": "local-desktop-node",
        "source_message_id": "agent-smoke-message",
        "playback_wait_seconds": 2,
        "focus_retry_limit": 1,
        "metadata": {"caller": "agent_smoke_test"},
    }
    deadline = time.monotonic() + timeout_seconds
    with httpx.Client(timeout=10.0) as client:
        health = client.get(f"{base_url}/health")
        health.raise_for_status()
        accepted = client.post(f"{base_url}/tasks/wechat-channels", json=payload)
        accepted.raise_for_status()
        accepted_data = accepted.json()
        task_id = accepted_data["task_id"]
        while time.monotonic() < deadline:
            status = client.get(f"{base_url}/tasks/{task_id}")
            status.raise_for_status()
            status_data = status.json()
            if status_data.get("status") in {"succeeded", "failed", "cancelled"}:
                if status_data.get("status") != "succeeded":
                    raise RuntimeError(f"RPA smoke test failed: {status_data}")
                return {
                    "health": health.json(),
                    "accepted": accepted_data,
                    "status": status_data,
                }
            time.sleep(1.0)
    raise TimeoutError("RPA smoke test timed out")


async def run_mcp_stdio_smoke_test(xhs_url: str, timeout_seconds: float) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "social_ingestion_mcp.server", "--transport", "stdio"],
        env=build_env(dry_run=True),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=timeout_seconds)
            tools_response = await asyncio.wait_for(session.list_tools(), timeout=timeout_seconds)
            submission = await asyncio.wait_for(
                session.call_tool(
                    "submit_xhs_ingestion",
                    {"source_url": xhs_url, "source_message_id": "agent-smoke-message"},
                ),
                timeout=timeout_seconds,
            )
            structured = getattr(submission, "structuredContent", None) or {}
            job_id = structured.get("job_id")
            if not job_id:
                raise RuntimeError(f"submit_xhs_ingestion returned unexpected payload: {submission}")

            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                job_result = await asyncio.wait_for(
                    session.call_tool("get_ingestion_job", {"job_id": job_id}),
                    timeout=timeout_seconds,
                )
                job_structured = getattr(job_result, "structuredContent", None) or {}
                job = job_structured.get("job") or {}
                if job.get("state") in {"succeeded", "failed", "cancelled"}:
                    if job.get("state") != "succeeded":
                        raise RuntimeError(f"MCP smoke test failed: {job_structured}")
                    return {
                        "tools": [getattr(tool, "name", "") for tool in getattr(tools_response, "tools", [])],
                        "submission": structured,
                        "job": job_structured,
                    }
                await asyncio.sleep(1.0)
    raise TimeoutError("MCP smoke test timed out")


def main() -> int:
    args = parse_args()
    results: dict[str, Any] = {}
    with ExitStack() as stack:
        if args.target in {"all", "rpa"}:
            process, base_url = start_rpa_node(args.timeout_seconds)
            stack.callback(terminate_process, process)
            results["rpa"] = run_rpa_smoke_test(base_url, args.wechat_url, args.timeout_seconds)

        if args.target in {"all", "mcp"}:
            results["mcp"] = asyncio.run(run_mcp_stdio_smoke_test(args.xhs_url, args.timeout_seconds))

    print(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())