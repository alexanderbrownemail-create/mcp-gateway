"""HTTP-клиент для Telegram Bot API."""
from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
import structlog
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_gateway.modules.telegram_bot.models import (
    ActionResult,
    AnswerCallbackRequest,
    DeleteMessageRequest,
    EditMessageRequest,
    ForwardMessageRequest,
    PinMessageRequest,
    SendMediaRequest,
    SendMessageRequest,
    SendTypingRequest,
    SendVoiceRequest,
    SentFile,
    SentMessage,
)

logger = structlog.get_logger(__name__)

_TG_API = "https://api.telegram.org"
_TTS_FORMAT = "ogg-24khz-16bit-mono-opus"


class BotSettings(BaseSettings):
    """Конфигурация Telegram Bot модуля.

    Attributes:
        telegram_bot_token: Токен бота от @BotFather.
    """

    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(..., description="Telegram Bot API token")


class BotApiError(Exception):
    """Ошибка Telegram Bot API.

    Attributes:
        error_code: Код ошибки от API.
        description: Текстовое описание ошибки.
    """

    def __init__(self, error_code: int, description: str) -> None:
        self.error_code = error_code
        self.description = description
        super().__init__(f"Bot API error {error_code}: {description}")


class BotClient:
    """Асинхронный клиент Telegram Bot API.

    Attributes:
        _token: Токен бота.
        _http: httpx AsyncClient.
    """

    def __init__(self, token: str) -> None:
        self._token = token
        self._http: httpx.AsyncClient | None = None

    @property
    def _base(self) -> str:
        return f"{_TG_API}/bot{self._token}"

    async def start(self) -> str:
        """Инициализирует HTTP-клиент и проверяет токен.

        Returns:
            @username бота.

        Raises:
            BotApiError: Если токен невалиден.
        """
        self._http = httpx.AsyncClient(timeout=30)
        resp = await self._call("getMe")
        username: str = resp["result"]["username"]
        logger.info("bot_connected", username=username)
        return username

    async def stop(self) -> None:
        """Закрывает HTTP-соединение."""
        if self._http:
            await self._http.aclose()

    async def _call(self, method: str, **params: object) -> dict[str, object]:
        """Вызывает метод Bot API.

        Args:
            method: Имя метода (например, sendMessage).
            **params: Параметры запроса.

        Returns:
            Тело ответа (поле result).

        Raises:
            BotApiError: Если ok=false в ответе.
        """
        assert self._http is not None
        cleaned = {k: v for k, v in params.items() if v is not None}
        resp = await self._http.post(f"{self._base}/{method}", json=cleaned)
        resp.raise_for_status()
        data: dict[str, object] = resp.json()
        if not data.get("ok"):
            raise BotApiError(
                error_code=int(data.get("error_code", 0)),
                description=str(data.get("description", "unknown error")),
            )
        return data

    async def _upload(
        self,
        method: str,
        field: str,
        file_path: str,
        extra: dict[str, str],
    ) -> dict[str, object]:
        """Загружает файл через multipart/form-data.

        Args:
            method: Метод Bot API (sendDocument, sendPhoto и т.д.).
            field: Имя поля файла в форме.
            file_path: Абсолютный путь к файлу.
            extra: Дополнительные поля формы.

        Returns:
            Тело ответа.
        """
        assert self._http is not None
        with open(file_path, "rb") as f:
            resp = await self._http.post(
                f"{self._base}/{method}",
                data=extra,
                files={field: (Path(file_path).name, f)},
            )
        resp.raise_for_status()
        data: dict[str, object] = resp.json()
        if not data.get("ok"):
            raise BotApiError(
                error_code=int(data.get("error_code", 0)),
                description=str(data.get("description", "unknown error")),
            )
        return data

    # --- Public API ---

    async def send_message(self, req: SendMessageRequest) -> SentMessage:
        """Отправляет текстовое сообщение.

        Args:
            req: Параметры сообщения.

        Returns:
            Нормализованный результат отправки.
        """
        params: dict[str, object] = {
            "chat_id": req.chat_id,
            "text": req.text,
        }
        if req.parse_mode.value != "disabled":
            params["parse_mode"] = req.parse_mode.value
        if req.buttons:
            params["reply_markup"] = {
                "inline_keyboard": [
                    [btn.model_dump(exclude_none=True) for btn in row]
                    for row in req.buttons
                ]
            }
        if req.reply_to_message_id:
            params["reply_to_message_id"] = req.reply_to_message_id
        resp = await self._call("sendMessage", **params)
        return SentMessage.from_api(resp)

    async def send_document(self, req: SendMediaRequest) -> SentFile:
        """Отправляет файл-документ.

        Args:
            req: Параметры отправки.

        Returns:
            Нормализованный результат с file_id.
        """
        extra: dict[str, str] = {"chat_id": str(req.chat_id)}
        if req.caption:
            extra["caption"] = req.caption
            if req.parse_mode.value != "disabled":
                extra["parse_mode"] = req.parse_mode.value
        resp = await self._upload("sendDocument", "document", req.file_path, extra)
        return SentFile.from_api(resp, "document")

    async def send_photo(self, req: SendMediaRequest) -> SentFile:
        """Отправляет фотографию.

        Args:
            req: Параметры отправки.

        Returns:
            Нормализованный результат с file_id.
        """
        extra: dict[str, str] = {"chat_id": str(req.chat_id)}
        if req.caption:
            extra["caption"] = req.caption
            if req.parse_mode.value != "disabled":
                extra["parse_mode"] = req.parse_mode.value
        resp = await self._upload("sendPhoto", "photo", req.file_path, extra)
        return SentFile.from_api(resp, "photo")

    async def send_video(self, req: SendMediaRequest) -> SentFile:
        """Отправляет видео.

        Args:
            req: Параметры отправки.

        Returns:
            Нормализованный результат с file_id.
        """
        extra: dict[str, str] = {"chat_id": str(req.chat_id)}
        if req.caption:
            extra["caption"] = req.caption
            if req.parse_mode.value != "disabled":
                extra["parse_mode"] = req.parse_mode.value
        resp = await self._upload("sendVideo", "video", req.file_path, extra)
        return SentFile.from_api(resp, "video")

    async def send_voice(self, req: SendVoiceRequest) -> SentFile:
        """Синтезирует речь через edge-tts и отправляет как голосовое сообщение.

        Args:
            req: Параметры TTS.

        Returns:
            Нормализованный результат с file_id.
        """
        import asyncio
        import edge_tts  # type: ignore[import-untyped]

        communicate = edge_tts.Communicate(req.text, req.voice)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name

        await communicate.save(tmp_path)

        try:
            extra: dict[str, str] = {"chat_id": str(req.chat_id)}
            resp = await self._upload("sendVoice", "voice", tmp_path, extra)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return SentFile.from_api(resp, "voice")

    async def send_sticker(self, chat_id: int | str, sticker_file_id: str) -> SentMessage:
        """Отправляет стикер по file_id.

        Args:
            chat_id: ID чата.
            sticker_file_id: Telegram file_id стикера.

        Returns:
            Нормализованный результат.
        """
        resp = await self._call("sendSticker", chat_id=chat_id, sticker=sticker_file_id)
        return SentMessage.from_api(resp)

    async def forward_message(self, req: ForwardMessageRequest) -> SentMessage:
        """Пересылает сообщение.

        Args:
            req: Параметры пересылки.

        Returns:
            Нормализованный результат.
        """
        resp = await self._call(
            "forwardMessage",
            chat_id=req.to_chat_id,
            from_chat_id=req.from_chat_id,
            message_id=req.message_id,
        )
        return SentMessage.from_api(resp)

    async def edit_message(self, req: EditMessageRequest) -> SentMessage:
        """Редактирует ранее отправленное сообщение.

        Args:
            req: Параметры редактирования.

        Returns:
            Нормализованный результат.
        """
        params: dict[str, object] = {
            "chat_id": req.chat_id,
            "message_id": req.message_id,
            "text": req.text,
        }
        if req.parse_mode.value != "disabled":
            params["parse_mode"] = req.parse_mode.value
        if req.buttons is not None:
            params["reply_markup"] = {
                "inline_keyboard": [
                    [btn.model_dump(exclude_none=True) for btn in row]
                    for row in req.buttons
                ]
            }
        resp = await self._call("editMessageText", **params)
        return SentMessage.from_api(resp)

    async def delete_message(self, req: DeleteMessageRequest) -> ActionResult:
        """Удаляет сообщение.

        Args:
            req: Параметры удаления.

        Returns:
            Результат операции.
        """
        resp = await self._call(
            "deleteMessage", chat_id=req.chat_id, message_id=req.message_id
        )
        return ActionResult.from_api(resp)

    async def pin_message(self, req: PinMessageRequest) -> ActionResult:
        """Закрепляет сообщение.

        Args:
            req: Параметры закрепления.

        Returns:
            Результат операции.
        """
        resp = await self._call(
            "pinChatMessage",
            chat_id=req.chat_id,
            message_id=req.message_id,
            disable_notification=req.disable_notification,
        )
        return ActionResult.from_api(resp)

    async def unpin_message(self, chat_id: int | str, message_id: int) -> ActionResult:
        """Открепляет сообщение.

        Args:
            chat_id: ID чата.
            message_id: ID сообщения.

        Returns:
            Результат операции.
        """
        resp = await self._call(
            "unpinChatMessage", chat_id=chat_id, message_id=message_id
        )
        return ActionResult.from_api(resp)

    async def answer_callback(self, req: AnswerCallbackRequest) -> ActionResult:
        """Отвечает на нажатие inline-кнопки.

        Args:
            req: Параметры ответа.

        Returns:
            Результат операции.
        """
        resp = await self._call(
            "answerCallbackQuery",
            callback_query_id=req.callback_query_id,
            text=req.text,
            show_alert=req.show_alert,
        )
        return ActionResult.from_api(resp)

    async def set_typing(self, req: SendTypingRequest) -> ActionResult:
        """Отправляет индикатор действия (typing, upload_document и т.д.).

        Args:
            req: Параметры действия.

        Returns:
            Результат операции.
        """
        resp = await self._call(
            "sendChatAction", chat_id=req.chat_id, action=req.action
        )
        return ActionResult.from_api(resp)

    async def get_updates(self, offset: int | None = None, limit: int = 100) -> list[dict[str, object]]:
        """Получает входящие обновления (callback_query и сообщения).

        Args:
            offset: ID следующего обновления (все предыдущие подтверждаются).
            limit: Максимальное количество обновлений (1-100).

        Returns:
            Список обновлений из поля result.
        """
        resp = await self._call("getUpdates", offset=offset, limit=limit, timeout=0)
        result = resp.get("result", [])
        return result if isinstance(result, list) else []
