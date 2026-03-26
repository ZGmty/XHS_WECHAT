---
name: social-media-ingestion
description: "Use when handling Xiaohongshu or WeChat Channels links through the local social-ingestion-mcp server, especially for queueing, polling, and reporting compact job results."
---

# Social Media Ingestion

## Use When

- The user sends a Xiaohongshu link and wants automated download, transcription, cleaning, and Bitable write-back.
- The user sends a WeChat Channels link and wants the desktop RPA node and sniffer workflow triggered.
- The user asks for task queue state or job polling status instead of full content.

## Tool Order

1. Detect the platform from the incoming URL.
2. For Xiaohongshu, call `submit_xhs_ingestion`.
3. For WeChat Channels, optionally call `get_wechat_rpa_queue_state`, then call `submit_wechat_channels_ingestion`.
4. Poll with `get_ingestion_job` until the job reaches `succeeded`, `failed`, or `cancelled`.
5. Return a compact summary with job id, state, stage, and record id if available.

## Constraints

- Never paste full transcript text back into the agent context.
- Keep OpenClaw lightweight: scheduling and status confirmation only.
- Treat WeChat Channels as a single-thread desktop queue.

## Expected MCP Tools

- `submit_xhs_ingestion`
- `submit_wechat_channels_ingestion`
- `get_ingestion_job`
- `get_wechat_rpa_queue_state`

## Reference

- OpenClaw-facing YAML template: `openclaw/skills/social_media_ingestion.yaml`