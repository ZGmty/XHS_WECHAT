# Agent Entry Points

This repository supports agent-driven testing.

## Quick Start

When you need a safe regression check, run:

```powershell
c:/python314/python.exe scripts/agent_smoke_test.py --target all
```

What it covers:

- starts the local WeChat RPA node in dry-run mode;
- submits and polls a WeChat RPA task;
- starts the MCP server over stdio;
- calls MCP tools and polls a dry-run Xiaohongshu ingestion job.

## Rules

- Prefer `scripts/agent_smoke_test.py` before ad hoc manual checks.
- Use dry-run mode for default validation unless the user explicitly asks for real desktop automation.
- Do not place long transcripts into agent context; inspect compact job results only.

## Other Useful Commands

Sync upstream repositories:

```powershell
c:/python314/python.exe scripts/sync_vendor_repos.py --update
```

Run only the RPA node smoke test:

```powershell
c:/python314/python.exe scripts/agent_smoke_test.py --target rpa
```

Run only the MCP smoke test:

```powershell
c:/python314/python.exe scripts/agent_smoke_test.py --target mcp
```