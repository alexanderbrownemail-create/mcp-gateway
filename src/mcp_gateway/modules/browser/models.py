"""Pydantic-модели для модуля browser."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ---------- Входные модели ----------

class NavigateRequest(BaseModel):
    """Запрос навигации браузера.

    Attributes:
        url: URL для открытия.
        wait_until: Событие ожидания ('load', 'domcontentloaded', 'networkidle').
        timeout_ms: Таймаут в миллисекундах.
    """

    url: str = Field(..., min_length=4)
    wait_until: str = "domcontentloaded"
    timeout_ms: int = Field(30_000, ge=1000, le=120_000)


class ClickRequest(BaseModel):
    """Запрос клика по элементу.

    Attributes:
        selector: CSS-селектор элемента.
        timeout_ms: Таймаут ожидания элемента.
    """

    selector: str = Field(..., min_length=1)
    timeout_ms: int = Field(10_000, ge=500, le=60_000)


class TypeRequest(BaseModel):
    """Запрос ввода текста в поле.

    Attributes:
        selector: CSS-селектор поля ввода.
        text: Текст для ввода.
        clear_first: Очистить поле перед вводом.
    """

    selector: str = Field(..., min_length=1)
    text: str
    clear_first: bool = True


class EvaluateRequest(BaseModel):
    """Запрос выполнения JavaScript.

    Attributes:
        expression: JavaScript-выражение для выполнения.
    """

    expression: str = Field(..., min_length=1)


class ScreenshotRequest(BaseModel):
    """Запрос скриншота страницы.

    Attributes:
        path: Абсолютный путь для сохранения PNG.
        full_page: Захватить всю страницу (не только viewport).
    """

    path: str
    full_page: bool = False


# ---------- Выходные модели ----------

class NavigateResult(BaseModel):
    """Результат навигации.

    Attributes:
        ok: Успех.
        url: Финальный URL после редиректов.
        title: Заголовок страницы.
        status: HTTP-статус.
    """

    ok: bool
    url: str
    title: str
    status: int | None = None


class SnapshotResult(BaseModel):
    """Результат snapshot страницы.

    Attributes:
        url: Текущий URL.
        title: Заголовок страницы.
        snapshot: Accessibility tree / текстовое представление DOM.
    """

    url: str
    title: str
    snapshot: str


class ScreenshotResult(BaseModel):
    """Результат скриншота.

    Attributes:
        ok: Успех.
        path: Путь к сохранённому PNG-файлу.
    """

    ok: bool
    path: str


class ClickResult(BaseModel):
    """Результат клика.

    Attributes:
        ok: Успех.
        selector: Использованный селектор.
    """

    ok: bool
    selector: str


class TypeResult(BaseModel):
    """Результат ввода текста.

    Attributes:
        ok: Успех.
        selector: Использованный селектор.
    """

    ok: bool
    selector: str


class EvaluateResult(BaseModel):
    """Результат выполнения JavaScript.

    Attributes:
        ok: Успех.
        result: Возвращённое значение (сериализованное в строку).
    """

    ok: bool
    result: str


class UrlResult(BaseModel):
    """Текущий URL браузера.

    Attributes:
        url: Текущий URL активной вкладки.
        title: Заголовок страницы.
    """

    url: str
    title: str
