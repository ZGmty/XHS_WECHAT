# Release Notes

## v0.1.0

Initial public repository upload for the social ingestion MCP project.

### Included

- MCP server skeleton and tool entry points
- Feishu Bitable adapter with real write support
- WeChat RPA node service and real-mode preflight
- XHS adapter boundary and media pipeline stubs
- Vendor sync tooling and upstream lockfile tracking
- OpenClaw-facing workflow skill and integration docs
- Cross-agent smoke test and supporting VS Code / Copilot instructions

### Validation

- Unified dry-run smoke test passes
- Real Feishu schema inspection script passes authentication but still depends on table permissions
- Real WeChat preflight currently depends on configured desktop commands