"""Фабрика приложения MCP-Gateway."""
from __future__ import annotations

import structlog

from mcp.server.fastmcp import FastMCP

from mcp_gateway.config import GatewaySettings
from mcp_gateway.registry import ModuleRegistry

logger = structlog.get_logger(__name__)


def create_app(settings: GatewaySettings | None = None) -> tuple[FastMCP, ModuleRegistry]:
    """Создаёт и настраивает FastMCP-приложение с реестром модулей.

    Args:
        settings: Конфигурация Gateway. Если None — загружается из env.

    Returns:
        Кортеж (FastMCP instance, ModuleRegistry instance).
    """
    if settings is None:
        settings = GatewaySettings()

    mcp = FastMCP(
        "mcp-gateway",
        host=settings.gateway_host,
        port=settings.gateway_port,
    )

    registry = ModuleRegistry(settings)

    return mcp, registry
