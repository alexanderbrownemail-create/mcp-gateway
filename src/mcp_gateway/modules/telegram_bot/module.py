"""Модуль telegram_bot — отправка сообщений через Telegram Bot API."""
from __future__ import annotations

import structlog

from mcp.server.fastmcp import FastMCP

from mcp_gateway.modules.base import BaseModule
from mcp_gateway.modules.telegram_bot.client import BotApiError, BotClient, BotSettings
from mcp_gateway.modules.telegram_bot.models import (
    AnswerCallbackRequest,
    DeleteMessageRequest,
    EditMessageRequest,
    ForwardMessageRequest,
    InlineButton,
    ParseMode,
    PinMessageRequest,
    SendMediaRequest,
    SendMessageRequest,
    SendTypingRequest,
    SendVoiceRequest,
)

logger = structlog.get_logger(__name__)


class TelegramBotModule(BaseModule):
    """Модуль Telegram Bot API.

    Предоставляет инструменты для отправки сообщений, файлов, голосовых сообщений
    и управления inline-клавиатурой от имени Telegram-бота.

    Attributes:
        name: Уникальное имя модуля.
        _client: HTTP-клиент Bot API.
    """

    name = "telegram_bot"

    def __init__(self) -> None:
        settings = BotSettings()
        self._client = BotClient(settings.telegram_bot_token)

    async def startup(self) -> None:
        """Инициализирует клиент и проверяет токен бота."""
        await self._client.start()

    def register_tools(self, mcp: FastMCP) -> None:
        """Регистрирует все bot_* инструменты.

        Args:
            mcp: Экземпляр FastMCP.
        """
        client = self._client

        @mcp.tool()
        async def bot_send_message(
            chat_id: int | str,
            text: str,
            parse_mode: str = "Markdown",
            buttons: list[list[dict[str, str]]] | None = None,
            reply_to_message_id: int | None = None,
        ) -> dict[str, object]:
            """Отправить текстовое сообщение через бота с опциональной inline-клавиатурой.

            Args:
                chat_id: ID чата (int) или @username (str).
                text: Текст сообщения (до 4096 символов).
                parse_mode: Форматирование: Markdown, HTML или disabled.
                buttons: Строки клавиатуры. Каждая строка — список кнопок:
                         [{"text": "Да", "callback_data": "yes"}, ...].
                         Кнопка может иметь callback_data ИЛИ url.
                reply_to_message_id: ID сообщения для ответа (опционально).
            """
            parsed_buttons: list[list[InlineButton]] | None = None
            if buttons:
                parsed_buttons = [
                    [InlineButton.model_validate(btn) for btn in row]
                    for row in buttons
                ]
            req = SendMessageRequest(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode(parse_mode),
                buttons=parsed_buttons,
                reply_to_message_id=reply_to_message_id,
            )
            try:
                result = await client.send_message(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_send_document(
            chat_id: int | str,
            file_path: str,
            caption: str | None = None,
            parse_mode: str = "Markdown",
        ) -> dict[str, object]:
            """Отправить файл-документ через бота.

            Args:
                chat_id: ID чата (int) или @username (str).
                file_path: Абсолютный путь к файлу на сервере.
                caption: Подпись к файлу (до 1024 символов, опционально).
                parse_mode: Форматирование подписи: Markdown, HTML или disabled.
            """
            req = SendMediaRequest(
                chat_id=chat_id,
                file_path=file_path,
                caption=caption,
                parse_mode=ParseMode(parse_mode),
            )
            try:
                result = await client.send_document(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_send_photo(
            chat_id: int | str,
            file_path: str,
            caption: str | None = None,
            parse_mode: str = "Markdown",
        ) -> dict[str, object]:
            """Отправить фотографию через бота.

            Args:
                chat_id: ID чата (int) или @username (str).
                file_path: Абсолютный путь к изображению на сервере.
                caption: Подпись (до 1024 символов, опционально).
                parse_mode: Форматирование подписи: Markdown, HTML или disabled.
            """
            req = SendMediaRequest(
                chat_id=chat_id,
                file_path=file_path,
                caption=caption,
                parse_mode=ParseMode(parse_mode),
            )
            try:
                result = await client.send_photo(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_send_video(
            chat_id: int | str,
            file_path: str,
            caption: str | None = None,
            parse_mode: str = "Markdown",
        ) -> dict[str, object]:
            """Отправить видео через бота.

            Args:
                chat_id: ID чата (int) или @username (str).
                file_path: Абсолютный путь к видеофайлу на сервере.
                caption: Подпись (до 1024 символов, опционально).
                parse_mode: Форматирование подписи: Markdown, HTML или disabled.
            """
            req = SendMediaRequest(
                chat_id=chat_id,
                file_path=file_path,
                caption=caption,
                parse_mode=ParseMode(parse_mode),
            )
            try:
                result = await client.send_video(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_send_voice(
            chat_id: int | str,
            text: str,
            voice: str = "ru-RU-SvetlanaNeural",
        ) -> dict[str, object]:
            """Синтезировать речь и отправить голосовым сообщением через бота.

            Использует edge-tts, формат ogg-24khz-16bit-mono-opus (Telegram принимает как voice).

            Args:
                chat_id: ID чата (int) или @username (str).
                text: Текст для синтеза (до 4096 символов).
                voice: Голос edge-tts. Примеры:
                       ru-RU-SvetlanaNeural, ru-RU-DmitryNeural,
                       en-US-AriaNeural, en-US-GuyNeural.
            """
            req = SendVoiceRequest(chat_id=chat_id, text=text, voice=voice)
            try:
                result = await client.send_voice(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_send_sticker(
            chat_id: int | str,
            sticker_file_id: str,
        ) -> dict[str, object]:
            """Отправить стикер через бота.

            Args:
                chat_id: ID чата (int) или @username (str).
                sticker_file_id: Telegram file_id стикера
                                 (можно получить из входящего сообщения).
            """
            try:
                result = await client.send_sticker(chat_id, sticker_file_id)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_forward_message(
            from_chat_id: int | str,
            message_id: int,
            to_chat_id: int | str,
        ) -> dict[str, object]:
            """Переслать сообщение через бота.

            Args:
                from_chat_id: ID исходного чата.
                message_id: ID пересылаемого сообщения.
                to_chat_id: ID целевого чата.
            """
            req = ForwardMessageRequest(
                from_chat_id=from_chat_id,
                message_id=message_id,
                to_chat_id=to_chat_id,
            )
            try:
                result = await client.forward_message(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_edit_message(
            chat_id: int | str,
            message_id: int,
            text: str,
            parse_mode: str = "Markdown",
            buttons: list[list[dict[str, str]]] | None = None,
        ) -> dict[str, object]:
            """Редактировать ранее отправленное сообщение бота.

            Args:
                chat_id: ID чата (int) или @username (str).
                message_id: ID редактируемого сообщения.
                text: Новый текст.
                parse_mode: Форматирование: Markdown, HTML или disabled.
                buttons: Новая клавиатура (None — не менять, [] — убрать).
            """
            parsed_buttons: list[list[InlineButton]] | None = None
            if buttons is not None:
                parsed_buttons = [
                    [InlineButton.model_validate(btn) for btn in row]
                    for row in buttons
                ]
            req = EditMessageRequest(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=ParseMode(parse_mode),
                buttons=parsed_buttons,
            )
            try:
                result = await client.edit_message(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_delete_message(
            chat_id: int | str,
            message_id: int,
        ) -> dict[str, object]:
            """Удалить сообщение бота.

            Args:
                chat_id: ID чата (int) или @username (str).
                message_id: ID удаляемого сообщения.
            """
            req = DeleteMessageRequest(chat_id=chat_id, message_id=message_id)
            try:
                result = await client.delete_message(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_pin_message(
            chat_id: int | str,
            message_id: int,
            disable_notification: bool = True,
        ) -> dict[str, object]:
            """Закрепить сообщение в чате.

            Args:
                chat_id: ID чата (int) или @username (str).
                message_id: ID закрепляемого сообщения.
                disable_notification: Закрепить без уведомления (по умолчанию True).
            """
            req = PinMessageRequest(
                chat_id=chat_id,
                message_id=message_id,
                disable_notification=disable_notification,
            )
            try:
                result = await client.pin_message(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_unpin_message(
            chat_id: int | str,
            message_id: int,
        ) -> dict[str, object]:
            """Открепить сообщение в чате.

            Args:
                chat_id: ID чата (int) или @username (str).
                message_id: ID открепляемого сообщения.
            """
            try:
                result = await client.unpin_message(chat_id, message_id)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_answer_callback(
            callback_query_id: str,
            text: str | None = None,
            show_alert: bool = False,
        ) -> dict[str, object]:
            """Ответить на нажатие inline-кнопки.

            Обязательно вызвать в течение 10 секунд после нажатия,
            иначе Telegram покажет ошибку пользователю.

            Args:
                callback_query_id: ID из поля callback_query.id входящего update.
                text: Текст уведомления (до 200 символов, опционально).
                show_alert: Показать как alert-попап вместо быстрого тоста.
            """
            req = AnswerCallbackRequest(
                callback_query_id=callback_query_id,
                text=text,
                show_alert=show_alert,
            )
            try:
                result = await client.answer_callback(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_set_typing(
            chat_id: int | str,
            action: str = "typing",
        ) -> dict[str, object]:
            """Отправить индикатор действия боту (печатает, загружает файл и т.д.).

            Args:
                chat_id: ID чата (int) или @username (str).
                action: Тип действия:
                        typing — печатает,
                        upload_document — загружает файл,
                        upload_photo — загружает фото,
                        upload_video — загружает видео,
                        record_voice — записывает голосовое,
                        playing — играет.
            """
            req = SendTypingRequest(chat_id=chat_id, action=action)
            try:
                result = await client.set_typing(req)
                return result.model_dump()
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

        @mcp.tool()
        async def bot_get_updates(
            offset: int | None = None,
            limit: int = 100,
        ) -> dict[str, object]:
            """Получить входящие обновления (нажатия кнопок, сообщения боту).

            Polling-метод. Каждый вызов подтверждает все update с id < offset.
            Для получения следующей порции передай offset = last_update_id + 1.

            Args:
                offset: ID следующего ожидаемого update (предыдущие подтверждаются).
                limit: Максимум обновлений в ответе (1-100, по умолчанию 100).

            Returns:
                Словарь {"ok": true, "updates": [...], "count": int}.
                Каждый update может содержать поля: message, callback_query и др.
            """
            try:
                updates = await client.get_updates(offset=offset, limit=limit)
                return {"ok": True, "updates": updates, "count": len(updates)}
            except BotApiError as e:
                return {"ok": False, "error_code": e.error_code, "description": e.description}

    async def shutdown(self) -> None:
        """Закрывает HTTP-соединение с Bot API."""
        await self._client.stop()
