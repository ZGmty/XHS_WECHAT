# Social Ingestion MCP

This repository contains the MCP server skeleton for a cross-platform social media ingestion and cleaning pipeline.

Current scope:

- Official Python MCP SDK based tool server
- XHS API-driven pipeline adapter boundary
- WeChat Channels single-thread RPA queue boundary
- Media extraction, STT, text cleaning, and Feishu Bitable adapter interfaces
- Local WeChat RPA node service skeleton
- Vendor sync mechanism for upstream open-source projects
- Windows node network recovery script for proxy/DHCP/Winsock repair

The current implementation defaults to dry-run mode so the server can start before external credentials and desktop nodes are wired.

Key entry points:

- MCP server: `src/social_ingestion_mcp/server.py`
- WeChat RPA node: `src/social_ingestion_mcp/rpa_node/server.py`
- Vendor sync: `scripts/sync_vendor_repos.py`
- Setup guide: `docs/setup-and-operations.md`
- Node 50 recovery guide: `docs/integration/node-50-network-recovery.md`