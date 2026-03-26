from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit and poll a WeChat Channels RPA node task")
    parser.add_argument("--base-url", default="http://127.0.0.1:8091")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--job-id", default="demo-job-001")
    parser.add_argument("--desktop-node-id", default="local-desktop-node")
    parser.add_argument("--source-message-id", default="")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    return parser.parse_args()


def get_json(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object response")
    return data


def main() -> int:
    args = parse_args()
    deadline = time.monotonic() + args.timeout_seconds

    payload = {
        "job_id": args.job_id,
        "source_url": args.source_url,
        "desktop_node_id": args.desktop_node_id,
        "source_message_id": args.source_message_id or None,
        "playback_wait_seconds": 8,
        "focus_retry_limit": 2,
        "metadata": {"caller": "demo_wechat_rpa_node_test"},
    }

    with httpx.Client(timeout=args.timeout_seconds) as client:
        health = get_json(client.get(f"{args.base_url}/health"))
        print("[health]", health)

        accepted = get_json(client.post(f"{args.base_url}/tasks/wechat-channels", json=payload))
        print("[accepted]", accepted)
        task_id = accepted["task_id"]

        while True:
            status = get_json(client.get(f"{args.base_url}/tasks/{task_id}"))
            print("[status]", status)
            state = status.get("status")
            if state in {"succeeded", "failed", "cancelled"}:
                break
            if time.monotonic() >= deadline:
                print("[error] polling timed out", file=sys.stderr)
                return 2
            time.sleep(args.poll_interval)

        if state != "succeeded":
            print(f"[error] terminal state = {state}", file=sys.stderr)
            return 1

        result = status.get("result") or {}
        print("[result]", result)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())