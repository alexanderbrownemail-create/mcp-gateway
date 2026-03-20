"""Базовый интерфейс для всех модулей MCP-Gateway."""
from __future__ import annotations

from abc import ABC, abstractmethod

from mcp.server.fastmcp import FastMCP


class BaseModule(ABC):
    """Интерфейс, который обязан реализовать каждый модуль.

    Attributes:
        name: Уникальное имя модуля (например, "telegram_bot").
    """

    name: str

    @abstractmethod
    async def startup(self) -> None:
        """Инициализация: подключения, сессии, фоновые задачи."""

    @abstractmethod
    def register_tools(self, mcp: FastMCP) -> None:
        """Регистрация инструментов через @mcp.tool().

        Вызывается один раз при старте после startup().

        Args:
            mcp: Экземпляр FastMCP для регистрации инструментов.
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Graceful shutdown: закрыть соединения, остановить задачи."""
