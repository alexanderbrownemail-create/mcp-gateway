"""Pydantic-модели для Telegram Bot API."""
from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator


class ParseMode(str, Enum):
    """Режим форматирования текста.

    Attributes:
        MARKDOWN: Markdown v1.
        HTML: HTML-разметка.
        DISABLED: Без форматирования.
    """

    MARKDOWN = "Markdown"
    HTML = "HTML"
    DISABLED = "disabled"


class InlineButton(BaseModel):
    """Кнопка inline-клавиатуры.

    Attributes:
        text: Текст на кнопке.
        callback_data: Данные, возвращаемые при нажатии (до 64 байт).
        url: URL, открываемый при нажатии (вместо callback_data).
    """

    text: str = Field(..., min_length=1, max_length=200)
    callback_data: str | None = Field(None, max_length=64)
    url: str | None = None

    @model_validator(mode="after")
    def one_of_callback_or_url(self) -> InlineButton:
        """Проверяет, что задан ровно один из callback_data / url."""
        if self.callback_data is None and self.url is None:
            raise ValueError("Кнопка должна иметь callback_data или url")
        if self.callback_data is not None and self.url is not None:
            raise ValueError("Нельзя задать одновременно callback_data и url")
        return self


# Клавиатура: список строк, каждая строка — список кнопок
InlineKeyboard = list[list[InlineButton]]


# ---------- Входные модели (запросы) ----------

class SendMessageRequest(BaseModel):
    """Запрос на отправку текстового сообщения.

    Attributes:
        chat_id: ID чата (int) или @username (str).
        text: Текст сообщения.
        parse_mode: Режим форматирования.
        buttons: Inline-клавиатура (строки × кнопки).
        reply_to_message_id: ID сообщения для ответа.
    """

    chat_id: int | str
    text: str = Field(..., min_length=1, max_length=4096)
    parse_mode: ParseMode = ParseMode.MARKDOWN
    buttons: InlineKeyboard | None = None
    reply_to_message_id: int | None = None


class SendMediaRequest(BaseModel):
    """Запрос на отправку медиафайла (документ, фото, видео).

    Attributes:
        chat_id: ID чата (int) или @username (str).
        file_path: Абсолютный путь к файлу на сервере.
        caption: Подпись (до 1024 символов).
        parse_mode: Режим форматирования подписи.
    """

    chat_id: int | str
    file_path: str
    caption: str | None = Field(None, max_length=1024)
    parse_mode: ParseMode = ParseMode.MARKDOWN

    @field_validator("file_path")
    @classmethod
    def file_must_exist(cls, v: str) -> str:
        """Проверяет, что файл существует."""
        if not Path(v).exists():
            raise ValueError(f"Файл не найден: {v}")
        return v


class SendVoiceRequest(BaseModel):
    """Запрос на отправку голосового сообщения через TTS.

    Attributes:
        chat_id: ID чата (int) или @username (str).
        text: Текст для синтеза речи.
        voice: Голос edge-tts (например, ru-RU-SvetlanaNeural).
    """

    chat_id: int | str
    text: str = Field(..., min_length=1, max_length=4096)
    voice: str = "ru-RU-SvetlanaNeural"


class EditMessageRequest(BaseModel):
    """Запрос на редактирование сообщения.

    Attributes:
        chat_id: ID чата (int) или @username (str).
        message_id: ID редактируемого сообщения.
        text: Новый текст.
        parse_mode: Режим форматирования.
        buttons: Новая клавиатура (None — не менять, [] — убрать).
    """

    chat_id: int | str
    message_id: int
    text: str = Field(..., min_length=1, max_length=4096)
    parse_mode: ParseMode = ParseMode.MARKDOWN
    buttons: InlineKeyboard | None = None


class AnswerCallbackRequest(BaseModel):
    """Запрос на ответ нажатия inline-кнопки.

    Attributes:
        callback_query_id: ID из входящего callback_query.
        text: Текст всплывающего уведомления (до 200 символов).
        show_alert: Показать как alert-попап вместо тоста.
    """

    callback_query_id: str
    text: str | None = Field(None, max_length=200)
    show_alert: bool = False


class DeleteMessageRequest(BaseModel):
    """Запрос на удаление сообщения.

    Attributes:
        chat_id: ID чата (int) или @username (str).
        message_id: ID удаляемого сообщения.
    """

    chat_id: int | str
    message_id: int


class PinMessageRequest(BaseModel):
    """Запрос на закрепление сообщения.

    Attributes:
        chat_id: ID чата (int) или @username (str).
        message_id: ID закрепляемого сообщения.
        disable_notification: Закрепить без уведомления.
    """

    chat_id: int | str
    message_id: int
    disable_notification: bool = True


class ForwardMessageRequest(BaseModel):
    """Запрос на пересылку сообщения.

    Attributes:
        from_chat_id: ID исходного чата.
        message_id: ID пересылаемого сообщения.
        to_chat_id: ID целевого чата.
    """

    from_chat_id: int | str
    message_id: int
    to_chat_id: int | str


class SendTypingRequest(BaseModel):
    """Запрос на отправку индикатора действия.

    Attributes:
        chat_id: ID чата (int) или @username (str).
        action: Тип действия (typing, upload_document, upload_photo и т.д.).
    """

    chat_id: int | str
    action: str = "typing"


# ---------- Выходные модели (ответы) ----------

class BotChat(BaseModel):
    """Информация о чате из ответа Bot API.

    Attributes:
        id: ID чата.
        type: Тип чата (private, group, supergroup, channel).
        username: @username чата (если есть).
        title: Название чата (для групп и каналов).
        first_name: Имя пользователя (для private).
    """

    id: int
    type: str
    username: str | None = None
    title: str | None = None
    first_name: str | None = None


class SentMessage(BaseModel):
    """Результат отправки или редактирования сообщения.

    Attributes:
        ok: Успех операции.
        message_id: ID отправленного сообщения.
        chat_id: ID чата.
        date: Unix timestamp отправки.
        text: Текст сообщения (если есть).
    """

    ok: bool
    message_id: int
    chat_id: int
    date: int
    text: str | None = None

    @classmethod
    def from_api(cls, response: dict[str, object]) -> SentMessage:
        """Создаёт SentMessage из ответа Bot API.

        Args:
            response: Сырой ответ от api.telegram.org.

        Returns:
            Нормализованный результат.
        """
        result = response.get("result", {})
        assert isinstance(result, dict)
        chat = result.get("chat", {})
        assert isinstance(chat, dict)
        return cls(
            ok=bool(response.get("ok")),
            message_id=int(result["message_id"]),
            chat_id=int(chat["id"]),
            date=int(result.get("date", 0)),
            text=result.get("text") or result.get("caption"),  # type: ignore[arg-type]
        )


class SentFile(BaseModel):
    """Результат отправки файла.

    Attributes:
        ok: Успех операции.
        message_id: ID сообщения с файлом.
        chat_id: ID чата.
        file_id: Telegram file_id для повторного использования.
        file_type: Тип файла (document, photo, video, voice).
    """

    ok: bool
    message_id: int
    chat_id: int
    file_id: str | None = None
    file_type: str | None = None

    @classmethod
    def from_api(cls, response: dict[str, object], file_type: str) -> SentFile:
        """Создаёт SentFile из ответа Bot API.

        Args:
            response: Сырой ответ от api.telegram.org.
            file_type: Тип файла (document, photo, video, voice).

        Returns:
            Нормализованный результат.
        """
        result = response.get("result", {})
        assert isinstance(result, dict)
        chat = result.get("chat", {})
        assert isinstance(chat, dict)

        file_id: str | None = None
        if file_type == "photo":
            photos = result.get("photo", [])
            if isinstance(photos, list) and photos:
                last = photos[-1]
                file_id = last.get("file_id") if isinstance(last, dict) else None  # type: ignore[assignment]
        else:
            file_obj = result.get(file_type, {})
            if isinstance(file_obj, dict):
                file_id = file_obj.get("file_id")  # type: ignore[assignment]

        return cls(
            ok=bool(response.get("ok")),
            message_id=int(result["message_id"]),
            chat_id=int(chat["id"]),
            file_id=str(file_id) if file_id else None,
            file_type=file_type,
        )


class ActionResult(BaseModel):
    """Результат действия без возвращаемого объекта (удаление, закрепление и т.д.).

    Attributes:
        ok: Успех операции.
        description: Описание ошибки (если ok=False).
    """

    ok: bool
    description: str | None = None

    @classmethod
    def from_api(cls, response: dict[str, object]) -> ActionResult:
        """Создаёт ActionResult из ответа Bot API.

        Args:
            response: Сырой ответ от api.telegram.org.

        Returns:
            Нормализованный результат.
        """
        return cls(
            ok=bool(response.get("ok")),
            description=response.get("description"),  # type: ignore[arg-type]
        )
