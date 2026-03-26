# Setup And Operations

## What You Need To Provide

### 1. Feishu / Bitable

- `SOCIAL_FEISHU_APP_ID`
- `SOCIAL_FEISHU_APP_SECRET`
- `SOCIAL_FEISHU_BITABLE_APP_TOKEN`
- `SOCIAL_FEISHU_BITABLE_TABLE_ID`
- `SOCIAL_FEISHU_BITABLE_FORCE_WRITE` if you want real Feishu writes while the rest of the pipeline remains in dry-run mode

Optional but recommended:

- `SOCIAL_FEISHU_BITABLE_UNIQUE_FIELD`
- `SOCIAL_FEISHU_BITABLE_JOB_ID_FIELD`
- `SOCIAL_FEISHU_BITABLE_PLATFORM_FIELD`
- `SOCIAL_FEISHU_BITABLE_SOURCE_URL_FIELD`
- `SOCIAL_FEISHU_BITABLE_SOURCE_TITLE_FIELD`
- `SOCIAL_FEISHU_BITABLE_CLEANED_TEXT_FIELD`
- `SOCIAL_FEISHU_BITABLE_TRANSCRIPT_FIELD`
- `SOCIAL_FEISHU_BITABLE_STATUS_FIELD`
- `SOCIAL_FEISHU_BITABLE_MEDIA_PATH_FIELD`
- `SOCIAL_FEISHU_BITABLE_SOURCE_MESSAGE_ID_FIELD`
- `SOCIAL_FEISHU_BITABLE_METADATA_FIELD`
- `SOCIAL_FEISHU_BITABLE_EXTRA_FIELD_MAP_JSON`

### 2. Xiaohongshu

- `SOCIAL_XHS_COOKIE`
- `SOCIAL_XHS_PROXY` if your network needs it
- optional local repo path: `SOCIAL_XHS_REPO_PATH`

### 3. WeChat RPA Node

- `SOCIAL_WECHAT_RPA_NODE_ID`
- `SOCIAL_WECHAT_RPA_NODE_MODE`: `dry-run` or `real`
- `SOCIAL_WECHAT_WINDOW_TITLE`
- optional local repo path: `SOCIAL_WECHAT_SNIFFER_REPO_PATH`
- optional local repo path: `SOCIAL_WECHAT_DECRYPT_REPO_PATH`
- real mode command: `SOCIAL_WECHAT_SNIFFER_COMMAND`
- real mode command: `SOCIAL_WECHAT_DECRYPT_COMMAND`

### 4. Media Processing

- local `ffmpeg` executable available in PATH
- if using Whisper local: install the optional dependency group `stt`

## Recommended Bitable Fields

- Job ID
- Platform
- Source URL
- Source Title
- Cleaned Text
- Transcript Text
- Status
- Media Path
- Source Message ID
- Metadata

## Easy Operation Steps

### Step 1. Install Python dependencies

```powershell
c:/python314/python.exe -m pip install -e .
c:/python314/python.exe -m pip install -e .[stt]
```

### Step 2. Prepare your environment file

```powershell
Copy-Item .env.example .env
```

Then fill the required values from the list above.

### Step 3. Sync upstream projects locally

```powershell
c:/python314/python.exe scripts/sync_vendor_repos.py --update
```

After this step, upstream repositories will be cloned into `vendor/` and a lock file will be written.

### Step 4. Start the local WeChat RPA node

```powershell
c:/python314/python.exe -m social_ingestion_mcp.rpa_node.server --host 127.0.0.1 --port 8091
```

If you only want to test the protocol first, keep `SOCIAL_WECHAT_RPA_NODE_MODE=dry-run`.

### Step 5. Test the RPA node

```powershell
c:/python314/python.exe scripts/demo_wechat_rpa_node_test.py --source-url https://channels.weixin.qq.com/example
```

### Step 6. Start the MCP server for OpenClaw

```powershell
c:/python314/python.exe -m social_ingestion_mcp.server --transport stdio
```

If you want to expose it over HTTP:

```powershell
c:/python314/python.exe -m social_ingestion_mcp.server --transport streamable-http --host 127.0.0.1 --port 8765
```

### Step 7. Load the OpenClaw skill

Use:

- `openclaw/skills/social_media_ingestion.yaml`

If your OpenClaw instance expects a different skill schema, keep the workflow logic and remap only the YAML keys.

### Step 8. Run the standard agent smoke test any time

Claude Code, GitHub Copilot, or any terminal-capable agent should use this command first:

```powershell
c:/python314/python.exe scripts/agent_smoke_test.py --target all
```

Supporting files:

- Claude Code / generic agent entry: `AGENTS.md`
- GitHub Copilot repo instructions: `.github/copilot-instructions.md`
- GitHub Copilot prompt: `.github/prompts/social-ingestion-smoke-test.prompt.md`
- VS Code task: `.vscode/tasks.json`

### Step 9. Check your real Feishu table before enabling production write-back

```powershell
c:/python314/python.exe scripts/check_bitable_schema.py
```

What success means:

- `ok: true`
- all expected field names already exist in your Feishu Bitable table

If it returns `missing`, either rename your Bitable columns or update the `SOCIAL_FEISHU_BITABLE_*_FIELD` variables in `.env`.

If field creation or record writing returns `403` or `91403 Forbidden`, the current Feishu app can read this Bitable but does not yet have enough edit or manage permission on the table.

In that case, add the app or calling identity to the Bitable with edit or manage permission first, then rerun the schema bootstrap or write test.

If you want the system to create the missing text fields for you:

```powershell
c:/python314/python.exe scripts/bootstrap_bitable_schema.py --apply
```

After that, rerun:

```powershell
c:/python314/python.exe scripts/check_bitable_schema.py
```

If you want to validate a real Feishu write while the source side still stays in dry-run mode:

```powershell
c:/python314/python.exe scripts/test_bitable_write.py
```

That script temporarily forces real Bitable write through the adapter and writes or updates a validation record keyed by `Job ID`.

### Step 10. Check your real WeChat desktop mode before using it

```powershell
c:/python314/python.exe scripts/check_wechat_real_mode.py
```

What this checks:

- whether a WeChat desktop window matching `SOCIAL_WECHAT_WINDOW_TITLE` is currently open
- whether `SOCIAL_WECHAT_SNIFFER_COMMAND` is configured
- whether `SOCIAL_WECHAT_DECRYPT_COMMAND` is configured

## Real WeChat Command Contract

When `SOCIAL_WECHAT_RPA_NODE_MODE=real`, the node will run your external commands and pass these environment variables:

- `SOCIAL_TASK_ID`
- `SOCIAL_SOURCE_URL`
- `SOCIAL_SOURCE_MESSAGE_ID`
- `SOCIAL_DESKTOP_NODE_ID`
- `SOCIAL_ARTIFACT_DIR`
- `SOCIAL_SNIFFER_RESULT_PATH`
- `SOCIAL_DECRYPT_RESULT_PATH`
- `SOCIAL_VISIBLE_TEXT_PATH`
- `SOCIAL_SPH_PATH` for the decrypt command

Expected outputs:

- the sniffer command writes JSON to `SOCIAL_SNIFFER_RESULT_PATH`
- the decrypt command writes JSON to `SOCIAL_DECRYPT_RESULT_PATH`
- optional visible text extractor writes JSON to `SOCIAL_VISIBLE_TEXT_PATH`

Minimal sniffer JSON example:

```json
{
	"sph_path": "E:/runtime/wechat/task-001/source.sph",
	"title": "视频号标题",
	"raw_text": "页面抓取到的简短文案",
	"cover_path": "E:/runtime/wechat/task-001/cover.jpg"
}
```

Minimal decrypt JSON example:

```json
{
	"video_path": "E:/runtime/wechat/task-001/video.mp4"
}
```

## Recommended Rollout Path

1. Run everything with `SOCIAL_DRY_RUN=true`.
2. Turn on real Feishu Bitable write-back first.
3. Turn on real Xiaohongshu extraction next.
4. Turn on real WeChat desktop automation last.

## Notes On Upstream Iteration

- No, the upstream repositories were not already downloaded in this workspace when I checked it.
- This project now includes a local sync mechanism so you can keep them inside `vendor/`.
- Our code stays compatible by routing all external calls through adapter layers, not by coupling orchestration to upstream internals.