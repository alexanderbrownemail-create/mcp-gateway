"""MCP-Gateway application factory."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from mcp_gateway.config import GatewaySettings
from mcp_gateway.registry import ModuleRegistry

logger = logging.getLogger(__name__)


def create_app(settings: GatewaySettings | None = None) -> tuple[FastMCP, ModuleRegistry]:
    if settings is None:
        settings = GatewaySettings()

    mcp = FastMCP(
        "mcp-gateway",
        host=settings.gateway_host,
        port=settings.gateway_port,
    )

    registry = ModuleRegistry(settings)

    @mcp.on_event("startup")
    async def on_startup() -> None:
        await registry.startup(mcp)
        logger.info("MCP-Gateway ready on %s:%d", settings.gateway_host, settings.gateway_port)

    @mcp.on_event("shutdown")
    async def on_shutdown() -> None:
        await registry.shutdown()

    return mcp, registry
