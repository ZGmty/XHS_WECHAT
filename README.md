# Social Ingestion MCP

This repository contains the MCP server and local automation components for a cross-platform social media ingestion and cleaning pipeline.

It is designed to run in dry-run mode by default, then be switched on module by module once your Feishu, XHS, and WeChat desktop environment are ready.

## What It Includes

- Official Python MCP SDK based tool server
- XHS adapter boundary for local vendor integration
- WeChat Channels single-flight RPA node and queue
- Media extraction, STT, text cleaning, and Feishu Bitable persistence
- Local upstream vendor sync and lockfile tracking
- Windows node network recovery script for proxy, DHCP, and Winsock repair

## Quick Start

```powershell
c:/python314/python.exe -m pip install -e .
c:/python314/python.exe scripts/agent_smoke_test.py --target all
```

## Run Targets

- MCP server: `src/social_ingestion_mcp/server.py`
- WeChat RPA node: `src/social_ingestion_mcp/rpa_node/server.py`
- Vendor sync: `scripts/sync_vendor_repos.py`
- Setup guide: `docs/setup-and-operations.md`
- Node 50 recovery guide: `docs/integration/node-50-network-recovery.md`

## Current Status

- Dry-run pipeline and smoke tests are working.
- Feishu Bitable real write-back is implemented, but the target table still needs edit or manage permission for the app identity.
- WeChat real-mode wiring is implemented, but external sniffer and decrypt commands still need to be provided.

## Repository Notes

The project has been pushed to GitHub at:

https://github.com/ZGmty/XHS_WECHAT.git

For detailed setup and operational steps, see [docs/setup-and-operations.md](docs/setup-and-operations.md).