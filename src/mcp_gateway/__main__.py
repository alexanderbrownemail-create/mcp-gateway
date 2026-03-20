"""Точка входа: python -m mcp_gateway."""
from __future__ import annotations

from mcp_gateway.app import create_app
from mcp_gateway.config import GatewaySettings
from mcp_gateway.logging_config import configure_logging


def main() -> None:
    """Создаёт и запускает MCP-Gateway."""
    settings = GatewaySettings()
    configure_logging(
        log_level=settings.gateway_log_level,
        log_format=settings.gateway_log_format,
    )
    mcp, _ = create_app(settings)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
