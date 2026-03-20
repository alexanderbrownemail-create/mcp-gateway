"""Модуль browser — управление браузером через CDP (Playwright)."""
from __future__ import annotations

import json
from pathlib import Path

import structlog
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_gateway.modules.base import BaseModule
from mcp_gateway.modules.browser.models import (
    ClickRequest,
    ClickResult,
    EvaluateRequest,
    EvaluateResult,
    NavigateRequest,
    NavigateResult,
    ScreenshotRequest,
    ScreenshotResult,
    SnapshotResult,
    TypeRequest,
    TypeResult,
    UrlResult,
)

logger = structlog.get_logger(__name__)


class BrowserSettings(BaseSettings):
    """Конфигурация browser модуля.

    Attributes:
        browser_cdp_url: WebSocket URL CDP-эндпоинта браузера.
    """

    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    browser_cdp_url: str = Field(
        "ws://127.0.0.1:18800",
        description="Chrome DevTools Protocol WebSocket URL",
    )


class BrowserModule(BaseModule):
    """Модуль управления браузером через CDP.

    Подключается к уже запущенному Chrome/Chromium через CDP.
    Предоставляет навигацию, клики, ввод текста, скриншоты, JS-исполнение.

    Attributes:
        name: Уникальное имя модуля.
        _settings: Настройки модуля.
        _playwright: Playwright instance.
        _browser: Playwright Browser объект.
        _page: Активная страница.
    """

    name = "browser"

    def __init__(self) -> None:
        self._settings = BrowserSettings()
        self._playwright: object | None = None
        self._browser: object | None = None

    async def startup(self) -> None:
        """Подключается к Chrome через CDP."""
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        self._playwright = pw
        self._browser = await pw.chromium.connect_over_cdp(self._settings.browser_cdp_url)
        logger.info("browser_connected", cdp_url=self._settings.browser_cdp_url)

    def _page(self) -> object:
        """Возвращает активную страницу (первый контекст, первая страница)."""
        assert self._browser is not None
        contexts = self._browser.contexts  # type: ignore[attr-defined]
        if not contexts:
            raise RuntimeError("No browser contexts available")
        pages = contexts[0].pages
        if not pages:
            raise RuntimeError("No pages in browser context")
        return pages[0]

    def register_tools(self, mcp: FastMCP) -> None:
        """Регистрирует browser_* инструменты.

        Args:
            mcp: Экземпляр FastMCP.
        """

        @mcp.tool()
        async def browser_navigate(
            url: str,
            wait_until: str = "domcontentloaded",
            timeout_ms: int = 30_000,
        ) -> dict[str, object]:
            """Открыть URL в браузере.

            Args:
                url: URL для открытия (http/https).
                wait_until: Событие ожидания: 'load', 'domcontentloaded', 'networkidle'.
                timeout_ms: Таймаут в миллисекундах (1 000–120 000).

            Returns:
                Словарь {ok, url, title, status}.
            """
            req = NavigateRequest(url=url, wait_until=wait_until, timeout_ms=timeout_ms)
            try:
                page = self._page()
                response = await page.goto(  # type: ignore[attr-defined]
                    req.url,
                    wait_until=req.wait_until,
                    timeout=req.timeout_ms,
                )
                result = NavigateResult(
                    ok=True,
                    url=page.url,  # type: ignore[attr-defined]
                    title=await page.title(),  # type: ignore[attr-defined]
                    status=response.status if response else None,
                )
            except Exception as exc:
                logger.warning("browser_navigate_error", url=req.url, error=str(exc))
                return {"ok": False, "error": str(exc)}

            logger.info("browser_navigate", url=result.url)
            return result.model_dump()

        @mcp.tool()
        async def browser_snapshot() -> dict[str, object]:
            """Получить текстовое представление DOM активной страницы.

            Возвращает accessibility tree — структурированное текстовое представление
            интерактивных элементов страницы.

            Returns:
                Словарь {url, title, snapshot}.
            """
            try:
                page = self._page()
                snapshot = await page.accessibility.snapshot()  # type: ignore[attr-defined]
                result = SnapshotResult(
                    url=page.url,  # type: ignore[attr-defined]
                    title=await page.title(),  # type: ignore[attr-defined]
                    snapshot=json.dumps(snapshot, ensure_ascii=False, indent=2),
                )
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            return result.model_dump()

        @mcp.tool()
        async def browser_screenshot(
            path: str,
            full_page: bool = False,
        ) -> dict[str, object]:
            """Сохранить скриншот активной страницы в PNG-файл.

            Args:
                path: Абсолютный путь для сохранения (например, '/tmp/screen.png').
                full_page: True — захватить всю страницу, False — только viewport.

            Returns:
                Словарь {ok, path}.
            """
            req = ScreenshotRequest(path=path, full_page=full_page)
            try:
                page = self._page()
                p = Path(req.path)
                p.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(p), full_page=req.full_page)  # type: ignore[attr-defined]
                result = ScreenshotResult(ok=True, path=str(p.resolve()))
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            logger.info("browser_screenshot", path=result.path)
            return result.model_dump()

        @mcp.tool()
        async def browser_click(
            selector: str,
            timeout_ms: int = 10_000,
        ) -> dict[str, object]:
            """Кликнуть по элементу страницы.

            Args:
                selector: CSS-селектор элемента (например, 'button.submit', '#login-btn').
                timeout_ms: Таймаут ожидания элемента в мс (500–60 000).

            Returns:
                Словарь {ok, selector}.
            """
            req = ClickRequest(selector=selector, timeout_ms=timeout_ms)
            try:
                page = self._page()
                await page.click(req.selector, timeout=req.timeout_ms)  # type: ignore[attr-defined]
                result = ClickResult(ok=True, selector=req.selector)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            logger.info("browser_click", selector=req.selector)
            return result.model_dump()

        @mcp.tool()
        async def browser_type(
            selector: str,
            text: str,
            clear_first: bool = True,
        ) -> dict[str, object]:
            """Ввести текст в поле ввода.

            Args:
                selector: CSS-селектор поля ввода.
                text: Текст для ввода.
                clear_first: Очистить поле перед вводом (по умолчанию True).

            Returns:
                Словарь {ok, selector}.
            """
            req = TypeRequest(selector=selector, text=text, clear_first=clear_first)
            try:
                page = self._page()
                if req.clear_first:
                    await page.fill(req.selector, "")  # type: ignore[attr-defined]
                await page.type(req.selector, req.text)  # type: ignore[attr-defined]
                result = TypeResult(ok=True, selector=req.selector)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            return result.model_dump()

        @mcp.tool()
        async def browser_evaluate(
            expression: str,
        ) -> dict[str, object]:
            """Выполнить JavaScript в контексте страницы.

            Args:
                expression: JavaScript-выражение (например, 'document.title',
                            'window.location.href', 'document.querySelectorAll("a").length').

            Returns:
                Словарь {ok, result} где result — строковое представление значения.
            """
            req = EvaluateRequest(expression=expression)
            try:
                page = self._page()
                value = await page.evaluate(req.expression)  # type: ignore[attr-defined]
                result = EvaluateResult(ok=True, result=json.dumps(value, ensure_ascii=False))
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            return result.model_dump()

        @mcp.tool()
        async def browser_get_url() -> dict[str, object]:
            """Получить текущий URL активной страницы.

            Returns:
                Словарь {url, title}.
            """
            try:
                page = self._page()
                result = UrlResult(
                    url=page.url,  # type: ignore[attr-defined]
                    title=await page.title(),  # type: ignore[attr-defined]
                )
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            return result.model_dump()

        @mcp.tool()
        async def browser_close() -> dict[str, object]:
            """Закрыть активную вкладку браузера.

            Returns:
                Словарь {ok}.
            """
            try:
                page = self._page()
                await page.close()  # type: ignore[attr-defined]
                logger.info("browser_close")
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            return {"ok": True}

    async def shutdown(self) -> None:
        """Отключается от CDP (браузер не закрывается)."""
        if self._browser:
            try:
                await self._browser.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()  # type: ignore[attr-defined]
            except Exception:
                pass
