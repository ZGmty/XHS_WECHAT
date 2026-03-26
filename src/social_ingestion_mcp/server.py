from __future__ import annotations

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from social_ingestion_mcp.adapters.bitable_adapter import FeishuBitableAdapter
from social_ingestion_mcp.adapters.media_pipeline import MediaPipelineAdapter
from social_ingestion_mcp.adapters.wechat_rpa_adapter import WechatRpaAdapter
from social_ingestion_mcp.adapters.xhs_adapter import XhsDownloaderAdapter
from social_ingestion_mcp.config import AppConfig
from social_ingestion_mcp.models import JobStatusResponse, RpaQueueState, ToolSubmission, WechatChannelsIngestionRequest, XhsIngestionRequest
from social_ingestion_mcp.services.orchestrator import IngestionOrchestrator
from social_ingestion_mcp.services.rpa_queue import SingleFlightRpaQueue


@dataclass(slots=True)
class AppContext:
    config: AppConfig
    orchestrator: IngestionOrchestrator
    rpa_queue: SingleFlightRpaQueue


@asynccontextmanager
async def app_lifespan(_: FastMCP) -> AsyncIterator[AppContext]:
    config = AppConfig()
    config.ensure_directories()

    rpa_queue = SingleFlightRpaQueue()
    await rpa_queue.start()

    orchestrator = IngestionOrchestrator(
        xhs_adapter=XhsDownloaderAdapter(config),
        wechat_adapter=WechatRpaAdapter(config),
        media_pipeline=MediaPipelineAdapter(config),
        bitable_adapter=FeishuBitableAdapter(config),
        rpa_queue=rpa_queue,
    )

    try:
        yield AppContext(config=config, orchestrator=orchestrator, rpa_queue=rpa_queue)
    finally:
        await rpa_queue.stop()


mcp = FastMCP(
    name="social-ingestion-mcp",
    instructions=(
        "Expose lightweight ingestion tools for OpenClaw. "
        "Accept links, return job ids, and keep heavy media processing inside the MCP server."
    ),
    lifespan=app_lifespan,
)


@mcp.tool(name="submit_xhs_ingestion", description="Queue the Xiaohongshu API-driven ingestion workflow")
async def submit_xhs_ingestion(
    source_url: str,
    source_message_id: str | None = None,
    bitable_table_id: str | None = None,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> ToolSubmission:
    if ctx is None:
        raise RuntimeError("MCP context is required")
    request = XhsIngestionRequest(
        source_url=source_url,
        source_message_id=source_message_id,
        bitable_table_id=bitable_table_id,
    )
    return await ctx.request_context.lifespan_context.orchestrator.submit_xhs(request)


@mcp.tool(name="submit_wechat_channels_ingestion", description="Queue the WeChat Channels RPA plus sniffer workflow")
async def submit_wechat_channels_ingestion(
    source_url: str,
    source_message_id: str | None = None,
    desktop_node_id: str = "local-desktop-node",
    bitable_table_id: str | None = None,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> ToolSubmission:
    if ctx is None:
        raise RuntimeError("MCP context is required")
    request = WechatChannelsIngestionRequest(
        source_url=source_url,
        source_message_id=source_message_id,
        desktop_node_id=desktop_node_id,
        bitable_table_id=bitable_table_id,
    )
    return await ctx.request_context.lifespan_context.orchestrator.submit_wechat(request)


@mcp.tool(name="get_ingestion_job", description="Get ingestion job state without returning heavy content")
async def get_ingestion_job(
    job_id: str,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> JobStatusResponse:
    if ctx is None:
        raise RuntimeError("MCP context is required")
    return await ctx.request_context.lifespan_context.orchestrator.get_job(job_id)


@mcp.tool(name="get_wechat_rpa_queue_state", description="Inspect the single-thread WeChat RPA queue")
async def get_wechat_rpa_queue_state(
    ctx: Context[ServerSession, AppContext] | None = None,
) -> RpaQueueState:
    if ctx is None:
        raise RuntimeError("MCP context is required")
    return ctx.request_context.lifespan_context.rpa_queue.snapshot()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the social ingestion MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    transport = args.transport
    if transport == "streamable-http":
        mcp.run(
            transport=cast_transport(transport),
            host=args.host,
            port=args.port,
            stateless_http=True,
            json_response=True,
        )
        return
    mcp.run(transport=cast_transport(transport))


def cast_transport(value: str) -> Literal["stdio", "streamable-http"]:
    return value  # type: ignore[return-value]


if __name__ == "__main__":
    main()