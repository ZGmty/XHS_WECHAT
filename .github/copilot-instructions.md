# Copilot Instructions

Use the repository-provided smoke test before or after meaningful changes to ingestion, MCP, RPA node, or adapter code.

Primary command:

```powershell
c:/python314/python.exe scripts/agent_smoke_test.py --target all
```

Testing guidance:

- Default to dry-run validation.
- Keep OpenClaw and other agents lightweight by inspecting job ids, queue state, and result previews instead of long transcripts.
- If the user asks whether upstream dependencies are present locally, check `vendor/` and `vendor/repositories.lock.json`.
- If upstream compatibility is in question, run `scripts/sync_vendor_repos.py --update` and compare the new lock file.