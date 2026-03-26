from __future__ import annotations

import asyncio
import json

from social_ingestion_mcp.config import AppConfig
from social_ingestion_mcp.errors import SocialIngestionError
from social_ingestion_mcp.rpa_node.automation import RealWechatAutomator


async def amain() -> int:
    config = AppConfig()
    automator = RealWechatAutomator(config)
    try:
        result = await automator.preflight()
    except SocialIngestionError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": exc.code,
                    "error_message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))