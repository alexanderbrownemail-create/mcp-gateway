"""Модуль sessions — управление под-агентскими сессиями через claude-code-proxy."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import structlog
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_gateway.modules.base import BaseModule
from mcp_gateway.modules.sessions.models import (
    HistoryEntry,
    HistoryResult,
    SendMessageRequest,
    SessionInfo,
    SessionStatus,
    SpawnRequest,
    SpawnResult,
)

logger = structlog.get_logger(__name__)


class SessionsSettings(BaseSettings):
    """Конфигурация sessions модуля.

    Attributes:
        sessions_proxy_url: URL claude-code-proxy для запуска под-агентов.
    """

    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sessions_proxy_url: str = Field(
        "http://127.0.0.1:3458",
        description="claude-code-proxy base URL",
    )


class SessionsModule(BaseModule):
    """Модуль управления под-агентами.

    Позволяет запускать под-агентов через claude-code-proxy,
    отслеживать их статус, читать транскрипты.
    Является аналогом OpenClaw sessions_spawn для Claude Code harness.

    Attributes:
        name: Уникальное имя модуля.
        _settings: Настройки модуля.
        _http: HTTP-клиент для работы с proxy.
        _sessions: Локальный реестр сессий {session_id: SessionInfo}.
    """

    name = "sessions"

    def __init__(self) -> None:
        self._settings = SessionsSettings()
        self._http: httpx.AsyncClient | None = None
        self._sessions: dict[str, dict[str, object]] = {}

    async def startup(self) -> None:
        """Инициализирует HTTP-клиент для claude-code-proxy."""
        self._http = httpx.AsyncClient(
            base_url=self._settings.sessions_proxy_url,
            timeout=60,
        )
        logger.info("sessions_module_ready", proxy_url=self._settings.sessions_proxy_url)

    def register_tools(self, mcp: FastMCP) -> None:
        """Регистрирует session_* инструменты.

        Args:
            mcp: Экземпляр FastMCP.
        """

        @mcp.tool()
        async def session_spawn(
            prompt: str,
            model: str = "claude-haiku-4-5-20251001",
            chat_id: int | str | None = None,
            notify_on_complete: bool = True,
        ) -> dict[str, object]:
            """Запустить под-агента с заданным промптом.

            Под-агент выполняется асинхронно. При завершении (если notify_on_complete=True
            и задан chat_id) результат будет отправлен в Telegram через bot_send_message.

            Args:
                prompt: Задача для под-агента (полный промпт).
                model: Модель Claude. Рекомендуется haiku для скорости/стоимости.
                chat_id: ID Telegram-чата для уведомления о результате.
                notify_on_complete: Отправить результат в Telegram при завершении.

            Returns:
                Словарь {ok, session_id, status}.
            """
            assert self._http is not None
            req = SpawnRequest(
                prompt=prompt,
                model=model,
                chat_id=chat_id,
                notify_on_complete=notify_on_complete,
            )

            try:
                resp = await self._http.post(
                    "/v1/chat/completions",
                    json={
                        "model": req.model,
                        "messages": [{"role": "user", "content": req.prompt}],
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data: dict[str, object] = resp.json()
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            session_id = str(uuid.uuid4())
            content = ""
            choices = data.get("choices", [])
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    msg = first.get("message", {})
                    if isinstance(msg, dict):
                        content = str(msg.get("content", ""))

            now = datetime.now(timezone.utc).isoformat()
            self._sessions[session_id] = {
                "session_id": session_id,
                "status": SessionStatus.COMPLETED,
                "model": req.model,
                "created_at": now,
                "prompt": req.prompt,
                "result": content,
                "chat_id": req.chat_id,
            }

            result = SpawnResult(
                ok=True,
                session_id=session_id,
                status=SessionStatus.COMPLETED,
            )
            logger.info(
                "session_spawn",
                session_id=session_id,
                model=req.model,
                result_len=len(content),
            )
            return result.model_dump()

        @mcp.tool()
        async def session_list() -> dict[str, object]:
            """Список всех сессий под-агентов.

            Returns:
                Словарь {sessions: [...], count: int}.
                Каждая сессия: {session_id, status, model, created_at, prompt_preview}.
            """
            sessions = [
                SessionInfo(
                    session_id=s["session_id"],  # type: ignore[arg-type]
                    status=SessionStatus(s["status"]),  # type: ignore[arg-type]
                    model=str(s["model"]),
                    created_at=str(s["created_at"]),
                    prompt_preview=str(s["prompt"])[:100],
                ).model_dump()
                for s in self._sessions.values()
            ]
            return {"sessions": sessions, "count": len(sessions)}

        @mcp.tool()
        async def session_history(
            session_id: str,
        ) -> dict[str, object]:
            """Транскрипт (история) сессии под-агента.

            Args:
                session_id: ID сессии (из session_spawn или session_list).

            Returns:
                Словарь {session_id, entries: [{role, content, timestamp}]}.
            """
            session = self._sessions.get(session_id)
            if not session:
                return {"ok": False, "error": f"Session {session_id!r} not found"}

            entries = [
                HistoryEntry(
                    role="user",
                    content=str(session["prompt"]),
                    timestamp=str(session["created_at"]),
                ).model_dump(),
                HistoryEntry(
                    role="assistant",
                    content=str(session.get("result", "")),
                    timestamp=str(session["created_at"]),
                ).model_dump(),
            ]
            result = HistoryResult(session_id=session_id, entries=[])
            data = result.model_dump()
            data["entries"] = entries
            return data

        @mcp.tool()
        async def session_send(
            session_id: str,
            message: str,
        ) -> dict[str, object]:
            """Отправить дополнительное сообщение в сессию.

            Примечание: для синхронного proxy (claude-code-proxy) эта операция
            создаёт новый запрос с дополнительным контекстом.

            Args:
                session_id: ID существующей сессии.
                message: Сообщение для под-агента.

            Returns:
                Словарь {ok, session_id, result}.
            """
            assert self._http is not None
            req = SendMessageRequest(session_id=session_id, message=message)
            session = self._sessions.get(req.session_id)
            if not session:
                return {"ok": False, "error": f"Session {req.session_id!r} not found"}

            # Строим контекст: оригинальный промпт + результат + новое сообщение
            messages = [
                {"role": "user", "content": str(session["prompt"])},
                {"role": "assistant", "content": str(session.get("result", ""))},
                {"role": "user", "content": req.message},
            ]

            try:
                resp = await self._http.post(
                    "/v1/chat/completions",
                    json={"model": str(session["model"]), "messages": messages, "stream": False},
                )
                resp.raise_for_status()
                data: dict[str, object] = resp.json()
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            content = ""
            choices = data.get("choices", [])
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    msg = first.get("message", {})
                    if isinstance(msg, dict):
                        content = str(msg.get("content", ""))

            session["result"] = content
            return {"ok": True, "session_id": req.session_id, "result": content}

        @mcp.tool()
        async def session_status(
            session_id: str,
        ) -> dict[str, object]:
            """Статус сессии под-агента.

            Args:
                session_id: ID сессии.

            Returns:
                Словарь {session_id, status, model, created_at}.
            """
            session = self._sessions.get(session_id)
            if not session:
                return {"ok": False, "error": f"Session {session_id!r} not found"}

            return {
                "session_id": session["session_id"],
                "status": session["status"],
                "model": session["model"],
                "created_at": session["created_at"],
            }

    async def shutdown(self) -> None:
        """Закрывает HTTP-клиент."""
        if self._http:
            await self._http.aclose()
