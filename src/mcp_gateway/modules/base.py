"""Base interface for all MCP-Gateway modules."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mcp.server.fastmcp import FastMCP


class BaseModule(ABC):
    """Every module must implement this interface."""

    name: str  # unique module name, e.g. "telegram_user"

    @abstractmethod
    async def startup(self) -> None:
        """Initialize connections, sessions, background tasks."""

    @abstractmethod
    def register_tools(self, mcp: FastMCP) -> None:
        """Register @mcp.tool() decorators. Called once at startup."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Graceful shutdown: close connections, stop background tasks."""
