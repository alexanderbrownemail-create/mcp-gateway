"""Pydantic-модели для модуля telegram_user."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ---------- Выходные модели ----------

class TgUser(BaseModel):
    """Профиль пользователя Telegram.

    Attributes:
        id: ID пользователя.
        first_name: Имя.
        last_name: Фамилия (опционально).
        username: @username (опционально).
        phone: Номер телефона (только для контактов).
        is_bot: True если бот.
    """

    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    phone: str | None = None
    is_bot: bool = False


class TgChat(BaseModel):
    """Информация о чате/группе/канале.

    Attributes:
        id: ID чата.
        type: Тип: 'private', 'group', 'supergroup', 'channel'.
        title: Название (для групп/каналов).
        username: @username (опционально).
        members_count: Количество участников.
        description: Описание.
    """

    id: int
    type: str
    title: str | None = None
    username: str | None = None
    members_count: int | None = None
    description: str | None = None


class TgMessage(BaseModel):
    """Сообщение Telegram.

    Attributes:
        id: ID сообщения.
        chat_id: ID чата.
        sender_id: ID отправителя.
        sender_name: Имя отправителя.
        text: Текст сообщения.
        date: Unix timestamp.
        media_type: Тип медиа ('photo', 'document', 'video', 'voice', None).
        reply_to_id: ID сообщения-цитаты.
        is_outgoing: True если исходящее.
    """

    id: int
    chat_id: int
    sender_id: int | None = None
    sender_name: str | None = None
    text: str | None = None
    date: int
    media_type: str | None = None
    reply_to_id: int | None = None
    is_outgoing: bool = False


class TgDialog(BaseModel):
    """Диалог (запись в списке чатов).

    Attributes:
        chat_id: ID чата.
        title: Название/имя.
        unread_count: Непрочитанных сообщений.
        last_message_text: Текст последнего сообщения.
        last_message_date: Дата последнего сообщения (Unix).
    """

    chat_id: int
    title: str
    unread_count: int = 0
    last_message_text: str | None = None
    last_message_date: int | None = None


class TgMember(BaseModel):
    """Участник группы.

    Attributes:
        user_id: ID пользователя.
        first_name: Имя.
        username: @username (опционально).
        status: Статус: 'member', 'admin', 'creator', 'restricted', 'banned'.
        joined_date: Дата вступления (Unix, опционально).
    """

    user_id: int
    first_name: str
    username: str | None = None
    status: str = "member"
    joined_date: int | None = None


class TgSentResult(BaseModel):
    """Результат отправки сообщения.

    Attributes:
        ok: Успех.
        message_id: ID отправленного сообщения.
        chat_id: ID чата.
        date: Unix timestamp.
    """

    ok: bool
    message_id: int | None = None
    chat_id: int | None = None
    date: int | None = None


class AutoReply(BaseModel):
    """Правило автоответа.

    Attributes:
        id: Уникальный ID правила.
        keyword: Ключевое слово (регулярное выражение или точное совпадение).
        response: Текст ответа.
        chat_id: ID чата для применения (None = все чаты).
        case_sensitive: Учитывать регистр.
        enabled: Активно ли правило.
    """

    id: str
    keyword: str
    response: str
    chat_id: int | str | None = None
    case_sensitive: bool = False
    enabled: bool = True


class MessageTemplate(BaseModel):
    """Шаблон сообщения.

    Attributes:
        id: Уникальный ID шаблона.
        name: Название шаблона.
        text: Текст шаблона (поддерживает {placeholder}).
        parse_mode: Форматирование ('Markdown', 'HTML', 'disabled').
    """

    id: str
    name: str
    text: str
    parse_mode: str = "Markdown"
