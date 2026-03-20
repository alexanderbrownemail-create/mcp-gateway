"""Pydantic-модели для модуля sessions."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Статус под-агентской сессии."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------- Входные модели ----------

class SpawnRequest(BaseModel):
    """Запрос запуска под-агента.

    Attributes:
        prompt: Промпт для под-агента.
        model: Модель Claude для использования.
        chat_id: ID чата для уведомления о результате (опционально).
        notify_on_complete: Отправить результат в Telegram при завершении.
    """

    prompt: str = Field(..., min_length=1)
    model: str = "claude-haiku-4-5-20251001"
    chat_id: int | str | None = None
    notify_on_complete: bool = True


class SendMessageRequest(BaseModel):
    """Запрос отправки сообщения в активную сессию.

    Attributes:
        session_id: ID сессии.
        message: Сообщение для под-агента.
    """

    session_id: str
    message: str = Field(..., min_length=1)


# ---------- Выходные модели ----------

class SessionInfo(BaseModel):
    """Информация о сессии.

    Attributes:
        session_id: Уникальный ID сессии.
        status: Текущий статус.
        model: Используемая модель.
        created_at: Время создания (ISO).
        prompt_preview: Первые 100 символов промпта.
    """

    session_id: str
    status: SessionStatus
    model: str
    created_at: str
    prompt_preview: str


class SpawnResult(BaseModel):
    """Результат запуска под-агента.

    Attributes:
        ok: Успех.
        session_id: ID созданной сессии.
        status: Статус сессии.
    """

    ok: bool
    session_id: str
    status: SessionStatus


class HistoryEntry(BaseModel):
    """Запись транскрипта сессии.

    Attributes:
        role: 'user' или 'assistant'.
        content: Текст сообщения.
        timestamp: Время записи (ISO).
    """

    role: str
    content: str
    timestamp: str


class HistoryResult(BaseModel):
    """Транскрипт сессии.

    Attributes:
        session_id: ID сессии.
        entries: Список записей.
    """

    session_id: str
    entries: list[HistoryEntry]
