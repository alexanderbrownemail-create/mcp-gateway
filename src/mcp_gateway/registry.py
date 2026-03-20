"""Реестр модулей — загружает и управляет модулями MCP-Gateway."""
from __future__ import annotations

import structlog

from mcp.server.fastmcp import FastMCP

from mcp_gateway.config import GatewaySettings, load_module_config
from mcp_gateway.modules.base import BaseModule

logger = structlog.get_logger(__name__)


class ModuleRegistry:
    """Управляет жизненным циклом модулей Gateway.

    Attributes:
        _settings: Конфигурация Gateway.
        _modules: Список активных модулей.
    """

    def __init__(self, settings: GatewaySettings) -> None:
        self._settings = settings
        self._modules: list[BaseModule] = []

    def _load_modules(self) -> list[BaseModule]:
        """Импортирует и создаёт экземпляры включённых модулей.

        Returns:
            Список экземпляров модулей в порядке загрузки.
        """
        module_cfg = load_module_config(self._settings.gateway_config_file)
        modules: list[BaseModule] = []

        _LOADERS: list[tuple[str, str, str]] = [
            ("telegram_user", "mcp_gateway.modules.telegram_user", "TelegramUserModule"),
            ("telegram_bot", "mcp_gateway.modules.telegram_bot", "TelegramBotModule"),
            ("core", "mcp_gateway.modules.core", "CoreModule"),
            ("browser", "mcp_gateway.modules.browser", "BrowserModule"),
            ("sessions", "mcp_gateway.modules.sessions", "SessionsModule"),
            ("memory", "mcp_gateway.modules.memory", "MemoryModule"),
            ("tasks", "mcp_gateway.modules.tasks", "TasksModule"),
            ("cron", "mcp_gateway.modules.cron", "CronModule"),
            ("media", "mcp_gateway.modules.media", "MediaModule"),
        ]

        for module_name, import_path, class_name in _LOADERS:
            cfg = module_cfg.get(module_name, {})
            if not (isinstance(cfg, dict) and cfg.get("enabled", False)):
                continue
            try:
                import importlib
                mod = importlib.import_module(import_path)
                cls = getattr(mod, class_name)
                modules.append(cls())
                logger.info("module_loaded", module=module_name)
            except (ImportError, AttributeError) as e:
                logger.error("module_import_failed", module=module_name, error=str(e))

        return modules

    async def startup(self, mcp: FastMCP) -> None:
        """Инициализирует все модули и регистрирует их инструменты.

        Args:
            mcp: Экземпляр FastMCP для регистрации инструментов.
        """
        self._modules = self._load_modules()
        for module in self._modules:
            await module.startup()
            module.register_tools(mcp)
            logger.info("module_started", module=module.name)

    async def shutdown(self) -> None:
        """Останавливает все модули в обратном порядке."""
        for module in reversed(self._modules):
            try:
                await module.shutdown()
                logger.info("module_stopped", module=module.name)
            except Exception:
                logger.exception("module_shutdown_error", module=module.name)
