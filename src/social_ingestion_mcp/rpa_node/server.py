from __future__ import annotations

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
import uvicorn

from social_ingestion_mcp.config import AppConfig
from social_ingestion_mcp.rpa_node.automation import build_automator
from social_ingestion_mcp.rpa_node.models import RpaNodeHealth, WechatChannelsTaskAccepted, WechatChannelsTaskCreateRequest, WechatChannelsTaskStatus
from social_ingestion_mcp.rpa_node.service import WechatRpaNodeService


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = AppConfig()
    config.ensure_directories()
    service = WechatRpaNodeService(config=config, automator=build_automator(config))
    await service.start()
    try:
        app.state.config = config
        app.state.service = service
        yield
    finally:
        await service.stop()


app = FastAPI(title="social-wechat-rpa-node", lifespan=app_lifespan)


@app.get("/health", response_model=RpaNodeHealth)
async def health() -> RpaNodeHealth:
    if not hasattr(app.state, "service"):
        raise HTTPException(status_code=500, detail="RPA node service unavailable")
    service: WechatRpaNodeService = app.state.service
    return await service.health()


@app.post("/tasks/wechat-channels", response_model=WechatChannelsTaskAccepted)
async def create_wechat_channels_task(request: WechatChannelsTaskCreateRequest) -> WechatChannelsTaskAccepted:
    service: WechatRpaNodeService = app.state.service
    return await service.submit(request)


@app.get("/tasks/{task_id}", response_model=WechatChannelsTaskStatus)
async def get_task(task_id: str) -> WechatChannelsTaskStatus:
    service: WechatRpaNodeService = app.state.service
    task = await service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local WeChat RPA node service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()