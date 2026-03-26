# WeChat RPA Node Contract

## Goal

Define a stable async contract between social-ingestion-mcp and the local WeChat desktop RPA node.

## Transport

- Protocol: HTTP JSON
- Base URL: `SOCIAL_WECHAT_RPA_BASE_URL`
- Authentication: reserve header `X-Node-Token` for production
- Timeout policy: MCP submit request uses short request timeout, then polls task status until terminal state

## Endpoints

### 1. Health Check

- Method: `GET`
- Path: `/health`
- Response model: `RpaNodeHealth`

Example response:

```json
{
  "node_id": "local-desktop-node",
  "status": "ok",
  "is_busy": false,
  "waiting_jobs": 0,
  "current_task_id": null,
  "supports_platforms": ["wechat_channels"],
  "updated_at": "2026-03-26T10:00:00Z"
}
```

### 2. Create WeChat Channels Task

- Method: `POST`
- Path: `/tasks/wechat-channels`
- Request model: `WechatChannelsTaskCreateRequest`
- Response model: `WechatChannelsTaskAccepted`

Example request:

```json
{
  "job_id": "8e79d95d-4eb4-4d44-87f1-9f6aa2a74211",
  "source_url": "https://channels.weixin.qq.com/example",
  "desktop_node_id": "local-desktop-node",
  "source_message_id": "om_123456",
  "playback_wait_seconds": 8,
  "focus_retry_limit": 2,
  "metadata": {}
}
```

Example accepted response:

```json
{
  "task_id": "45a3271e-4f4f-4fd1-aaf7-bf6ad0cbcd93",
  "job_id": "8e79d95d-4eb4-4d44-87f1-9f6aa2a74211",
  "status": "accepted",
  "queue_position": 1,
  "accepted_at": "2026-03-26T10:00:03Z",
  "message": "task accepted"
}
```

### 3. Query Task Status

- Method: `GET`
- Path: `/tasks/{task_id}`
- Response model: `WechatChannelsTaskStatus`

Running response example:

```json
{
  "task_id": "45a3271e-4f4f-4fd1-aaf7-bf6ad0cbcd93",
  "job_id": "8e79d95d-4eb4-4d44-87f1-9f6aa2a74211",
  "status": "running",
  "queue_position": null,
  "phase": "decrypting_video",
  "progress": 0.65,
  "error_code": null,
  "error_message": null,
  "result": null,
  "updated_at": "2026-03-26T10:00:20Z"
}
```

Succeeded response example:

```json
{
  "task_id": "45a3271e-4f4f-4fd1-aaf7-bf6ad0cbcd93",
  "job_id": "8e79d95d-4eb4-4d44-87f1-9f6aa2a74211",
  "status": "succeeded",
  "queue_position": null,
  "phase": "completed",
  "progress": 1.0,
  "error_code": null,
  "error_message": null,
  "result": {
    "title": "示例视频号标题",
    "raw_text": "页面可见文案",
    "video_path": "E:/runtime/wechat/45a3271e.mp4",
    "cover_path": "E:/runtime/wechat/45a3271e.jpg",
    "artifact_path": "E:/runtime/wechat/45a3271e",
    "metadata": {
      "decrypt_source": "WechatSphDecrypt",
      "sniffer": "WechatVideoSniffer2.0"
    }
  },
  "updated_at": "2026-03-26T10:01:05Z"
}
```

## Error Codes

- `rpa_focus_lost`: 微信窗口失焦或分辨率不匹配
- `sniffer_timeout`: 抓流超时
- `decrypt_failed`: `.sph` 解密失败
- `wechat_not_logged_in`: PC 端微信未登录
- `desktop_busy_conflict`: 节点被非队列任务占用

## Execution Phases

- `queued`
- `focusing_wechat`
- `sending_link`
- `starting_playback`
- `capturing_stream`
- `decrypting_video`
- `exporting_artifacts`
- `completed`

## Python Models

协议模型已定义在 `src/social_ingestion_mcp/rpa_node/models.py`，MCP 适配器通过这些模型完成请求和轮询解析。