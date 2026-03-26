# External Dependency Strategy

## Current State

This repository does not vendor upstream projects by default. Instead, it provides a repeatable sync mechanism so you can:

- pull the latest upstream code when functionality needs to track platform changes;
- keep our integration layer stable through adapters instead of importing upstream internals everywhere;
- record which upstream commit is currently deployed.

## Managed Upstream Repositories

- `XHS-Downloader`
- `WechatVideoSniffer2.0`
- `WechatSphDecrypt`

Note:

- The originally referenced `Hanson/WechatSphDecrypt` repository is currently not publicly reachable.
- The vendor manifest uses a currently reachable public repository result for `WechatSphDecrypt` so the sync process can proceed.

Manifest file:

- `vendor/repositories.json`

Generated lock file after sync:

- `vendor/repositories.lock.json`

## Sync Command

```powershell
c:/python314/python.exe scripts/sync_vendor_repos.py --update
```

## Compatibility Rules

1. Never let business code depend on many scattered upstream modules directly.
2. Only adapters may touch upstream project internals.
3. When upstream breaks, patch the adapter or pin the lock file, not the whole orchestration layer.
4. Before upgrading in production, diff `vendor/repositories.lock.json` and rerun the demo and smoke tests.

## Adapter Boundaries

- Xiaohongshu extraction boundary: `src/social_ingestion_mcp/adapters/xhs_adapter.py`
- WeChat node capture boundary: `src/social_ingestion_mcp/adapters/wechat_rpa_adapter.py`
- Bitable persistence boundary: `src/social_ingestion_mcp/adapters/bitable_adapter.py`

This separation is what keeps the project compatible with upstream iteration.