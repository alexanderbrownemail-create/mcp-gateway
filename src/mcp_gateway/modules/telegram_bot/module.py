"""TelegramBotModule — Telegram Bot API integration."""

from __future__ import annotations

import logging

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_gateway.modules.base import BaseModule

logger = logging.getLogger(__name__)


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(..., description="Telegram Bot API token")


class TelegramBotModule(BaseModule):
    name = "telegram_bot"

    def __init__(self) -> None:
        self._settings = BotSettings()
        self._client: httpx.AsyncClient | None = None

    @property
    def _base_url(self) -> str:
        return f"https://api.telegram.org/bot{self._settings.telegram_bot_token}"

    async def _call(self, method: str, **params: object) -> dict:
        assert self._client is not None
        resp = await self._client.post(f"{self._base_url}/{method}", json=params)
        resp.raise_for_status()
        return resp.json()

    async def startup(self) -> None:
        self._client = httpx.AsyncClient(timeout=30)
        me = await self._call("getMe")
        logger.info("telegram_bot: connected as @%s", me["result"]["username"])

    def register_tools(self, mcp: FastMCP) -> None:

        @mcp.tool()
        async def bot_send_message(
            chat_id: int | str,
            text: str,
            parse_mode: str = "Markdown",
            buttons: list[list[dict]] | None = None,
            reply_to_message_id: int | None = None,
        ) -> dict:  # type: ignore[type-arg]
            """Send a text message via Telegram bot.

            Args:
                chat_id: Target chat ID (int) or username (str, e.g. 'username').
                text: Message text content.
                parse_mode: Formatting: 'Markdown', 'HTML', or 'disabled'.
                buttons: Inline keyboard rows. Each row is a list of button dicts:
                         [{"text": "Label", "callback_data": "value"}].
                         Example: [[{"text": "Yes", "callback_data": "yes"},
                                    {"text": "No", "callback_data": "no"}]]
                reply_to_message_id: Optional message ID to reply to.
            """
            params: dict = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode if parse_mode != "disabled" else None,
            }
            if buttons:
                params["reply_markup"] = {"inline_keyboard": buttons}
            if reply_to_message_id:
                params["reply_to_message_id"] = reply_to_message_id
            params = {k: v for k, v in params.items() if v is not None}
            return await self._call("sendMessage", **params)

        @mcp.tool()
        async def bot_send_document(
            chat_id: int | str,
            file_path: str,
            caption: str | None = None,
            parse_mode: str = "Markdown",
        ) -> dict:  # type: ignore[type-arg]
            """Send a file (document) via Telegram bot.

            Args:
                chat_id: Target chat ID (int) or username (str).
                file_path: Absolute path to the file on the server.
                caption: Optional caption text.
                parse_mode: Caption formatting: 'Markdown', 'HTML', or 'disabled'.
            """
            assert self._client is not None
            with open(file_path, "rb") as f:
                data: dict = {"chat_id": str(chat_id)}
                if caption:
                    data["caption"] = caption
                    if parse_mode != "disabled":
                        data["parse_mode"] = parse_mode
                resp = await self._client.post(
                    f"{self._base_url}/sendDocument",
                    data=data,
                    files={"document": f},
                )
            resp.raise_for_status()
            return resp.json()

        @mcp.tool()
        async def bot_send_photo(
            chat_id: int | str,
            file_path: str,
            caption: str | None = None,
            parse_mode: str = "Markdown",
        ) -> dict:  # type: ignore[type-arg]
            """Send a photo via Telegram bot.

            Args:
                chat_id: Target chat ID (int) or username (str).
                file_path: Absolute path to the image file on the server.
                caption: Optional caption text.
                parse_mode: Caption formatting: 'Markdown', 'HTML', or 'disabled'.
            """
            assert self._client is not None
            with open(file_path, "rb") as f:
                data: dict = {"chat_id": str(chat_id)}
                if caption:
                    data["caption"] = caption
                    if parse_mode != "disabled":
                        data["parse_mode"] = parse_mode
                resp = await self._client.post(
                    f"{self._base_url}/sendPhoto",
                    data=data,
                    files={"photo": f},
                )
            resp.raise_for_status()
            return resp.json()

        @mcp.tool()
        async def bot_answer_callback(
            callback_query_id: str,
            text: str | None = None,
            show_alert: bool = False,
        ) -> dict:  # type: ignore[type-arg]
            """Answer an inline keyboard button press.

            Args:
                callback_query_id: ID from the incoming callback_query.
                text: Optional notification text shown to the user.
                show_alert: If True, show as alert popup instead of toast.
            """
            return await self._call(
                "answerCallbackQuery",
                callback_query_id=callback_query_id,
                text=text,
                show_alert=show_alert,
            )

        @mcp.tool()
        async def bot_edit_message(
            chat_id: int | str,
            message_id: int,
            text: str,
            parse_mode: str = "Markdown",
            buttons: list[list[dict]] | None = None,
        ) -> dict:  # type: ignore[type-arg]
            """Edit a previously sent bot message.

            Args:
                chat_id: Chat ID (int) or username (str).
                message_id: ID of the message to edit.
                text: New message text.
                parse_mode: Formatting: 'Markdown', 'HTML', or 'disabled'.
                buttons: New inline keyboard (replaces old one). Pass [] to remove.
            """
            params: dict = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": parse_mode if parse_mode != "disabled" else None,
            }
            if buttons is not None:
                params["reply_markup"] = {"inline_keyboard": buttons}
            params = {k: v for k, v in params.items() if v is not None}
            return await self._call("editMessageText", **params)

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
