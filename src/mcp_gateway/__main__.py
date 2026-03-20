"""Entry point: python -m mcp_gateway"""

import logging

from mcp_gateway.app import create_app
from mcp_gateway.config import GatewaySettings

settings = GatewaySettings()
logging.basicConfig(level=settings.gateway_log_level)

mcp, _ = create_app(settings)
mcp.run(transport="streamable-http")
