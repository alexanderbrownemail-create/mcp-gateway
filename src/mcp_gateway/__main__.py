"""Точка входа: python -m mcp_gateway."""
from __future__ import annotations

import asyncio

import structlog

from mcp_gateway.app import create_app
from mcp_gateway.config import GatewaySettings
from mcp_gateway.logging_config import configure_logging

logger = structlog.get_logger(__name__)


async def _run() -> None:
    settings = GatewaySettings()
    configure_logging(
        log_level=settings.gateway_log_level,
        log_format=settings.gateway_log_format,
    )
    mcp, registry = create_app(settings)

    await registry.startup(mcp)
    logger.info(
        "gateway_ready",
        host=settings.gateway_host,
        port=settings.gateway_port,
    )

    try:
        await mcp.run_streamable_http_async()
    finally:
        await registry.shutdown()
        logger.info("gateway_stopped")


def main() -> None:
    """Создаёт и запускает MCP-Gateway."""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
