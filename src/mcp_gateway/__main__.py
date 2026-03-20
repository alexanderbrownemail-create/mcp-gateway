"""Точка входа: python -m mcp_gateway."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from mcp_gateway.app import create_app
from mcp_gateway.config import GatewaySettings
from mcp_gateway.logging_config import configure_logging

logger = structlog.get_logger(__name__)

_MAX_ARG_LEN = 200
_MAX_RESULT_LEN = 300


def _truncate(value: Any, limit: int) -> str:
    s = str(value)
    return s if len(s) <= limit else s[:limit] + "…"


def _patch_call_tool(mcp: Any) -> None:
    """Wrap mcp.call_tool to log every tool invocation with args and result."""
    original = mcp.call_tool

    async def _logged_call_tool(name: str, arguments: dict[str, Any] | None = None, **kwargs: Any) -> Any:  # noqa: ANN401
        args_repr = _truncate(arguments or {}, _MAX_ARG_LEN)
        t0 = time.monotonic()
        try:
            result = await original(name, arguments, **kwargs)
            elapsed = time.monotonic() - t0
            # Extract text from first content item if possible
            result_repr = _truncate(result, _MAX_RESULT_LEN)
            try:
                content = result.content if hasattr(result, "content") else result
                if content and hasattr(content[0], "text"):
                    result_repr = _truncate(content[0].text, _MAX_RESULT_LEN)
            except Exception:
                pass
            logger.info(
                "tool_call",
                tool=name,
                args=args_repr,
                result=result_repr,
                elapsed_ms=round(elapsed * 1000),
            )
            return result
        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.error(
                "tool_call_error",
                tool=name,
                args=args_repr,
                error=str(exc),
                elapsed_ms=round(elapsed * 1000),
            )
            raise

    mcp.call_tool = _logged_call_tool


async def _run() -> None:
    settings = GatewaySettings()
    configure_logging(
        log_level=settings.gateway_log_level,
        log_format=settings.gateway_log_format,
    )
    mcp, registry = create_app(settings)

    await registry.startup(mcp)
    _patch_call_tool(mcp)
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
