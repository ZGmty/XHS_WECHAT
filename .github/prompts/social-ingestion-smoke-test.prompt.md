---
description: Run the repository smoke tests for the social ingestion MCP and local WeChat RPA node
---

Run the standard repository smoke test and summarize the result.

Required command:

```powershell
c:/python314/python.exe scripts/agent_smoke_test.py --target all
```

After the command completes:

1. Report whether the RPA dry-run smoke test passed.
2. Report whether the MCP stdio smoke test passed.
3. If it failed, point to the failing stage and suggest the smallest next debugging step.