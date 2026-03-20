"""Module registry — loads and manages MCP-Gateway modules."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from mcp_gateway.config import GatewaySettings, load_module_config
from mcp_gateway.modules.base import BaseModule

logger = logging.getLogger(__name__)


class ModuleRegistry:
    def __init__(self, settings: GatewaySettings) -> None:
        self._settings = settings
        self._modules: list[BaseModule] = []

    def _load_modules(self) -> list[BaseModule]:
        module_cfg = load_module_config(self._settings.gateway_config_file)
        modules: list[BaseModule] = []

        if module_cfg.get("telegram_user", {}).get("enabled", False):
            from mcp_gateway.modules.telegram_user import TelegramUserModule
            modules.append(TelegramUserModule())
            logger.info("Module loaded: telegram_user")

        if module_cfg.get("telegram_bot", {}).get("enabled", False):
            from mcp_gateway.modules.telegram_bot import TelegramBotModule
            modules.append(TelegramBotModule())
            logger.info("Module loaded: telegram_bot")

        if module_cfg.get("openclaw", {}).get("enabled", False):
            from mcp_gateway.modules.openclaw import OpenClawModule
            modules.append(OpenClawModule())
            logger.info("Module loaded: openclaw")

        return modules

    async def startup(self, mcp: FastMCP) -> None:
        self._modules = self._load_modules()
        for module in self._modules:
            await module.startup()
            module.register_tools(mcp)
            logger.info("Module started: %s", module.name)

    async def shutdown(self) -> None:
        for module in reversed(self._modules):
            try:
                await module.shutdown()
                logger.info("Module stopped: %s", module.name)
            except Exception:
                logger.exception("Error shutting down module: %s", module.name)
