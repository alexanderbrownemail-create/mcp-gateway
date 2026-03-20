"""Pyrogram-клиент для Telegram User API."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)


class UserSettings(BaseSettings):
    """Конфигурация telegram_user модуля.

    Attributes:
        telegram_api_id: API ID от my.telegram.org.
        telegram_api_hash: API Hash от my.telegram.org.
        telegram_phone: Номер телефона аккаунта.
        tg_manager_session_dir: Директория для хранения .session файлов.
        tg_manager_rate_limit: Максимум запросов в минуту.
    """

    model_config = SettingsConfigDict(
        env_file="~/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_api_id: int = Field(..., description="Telegram API ID")
    telegram_api_hash: str = Field(..., description="Telegram API Hash")
    telegram_phone: str = Field(..., description="Telegram phone number")
    tg_manager_session_dir: str = Field(
        "~/.telegram-sessions",
        description="Directory to store .session files",
    )
    tg_manager_rate_limit: int = Field(20, ge=1, le=100)


class UserClient:
    """Асинхронный клиент Telegram через Pyrogram.

    Attributes:
        _settings: Настройки.
        _app: Pyrogram Client instance.
        _pending_offset: Offset для get_pending_messages.
    """

    def __init__(self, settings: UserSettings) -> None:
        self._settings = settings
        self._app: Any | None = None
        self._pending_offset: int = 0

    async def start(self) -> str:
        """Инициализирует Pyrogram-клиент.

        Returns:
            @username или phone аккаунта.

        Raises:
            RuntimeError: Если сессионный файл не найден и нет флага создания.
        """
        from pyrogram import Client  # type: ignore[import-untyped]

        session_dir = Path(self._settings.tg_manager_session_dir).expanduser()
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / "account"

        self._app = Client(
            name=str(session_file),
            api_id=self._settings.telegram_api_id,
            api_hash=self._settings.telegram_api_hash,
            phone_number=self._settings.telegram_phone,
            in_memory=False,
        )
        await self._app.start()
        me = await self._app.get_me()
        username = me.username or self._settings.telegram_phone
        logger.info("tg_user_connected", username=username)
        return username

    async def stop(self) -> None:
        """Закрывает Pyrogram-сессию."""
        if self._app:
            try:
                await self._app.stop()
            except Exception:
                pass

    def _app_required(self) -> Any:
        if self._app is None:
            raise RuntimeError("Pyrogram client not started")
        return self._app

    # --- Public API ---

    async def get_me(self) -> dict[str, Any]:
        """Возвращает информацию о текущем аккаунте."""
        app = self._app_required()
        me = await app.get_me()
        return _user_to_dict(me)

    async def get_user(self, user_id: int | str) -> dict[str, Any]:
        """Возвращает профиль пользователя."""
        app = self._app_required()
        user = await app.get_users(user_id)
        return _user_to_dict(user)

    async def get_messages(
        self,
        chat_id: int | str,
        limit: int = 50,
        offset_id: int = 0,
        offset_date: int | None = None,
    ) -> list[dict[str, Any]]:
        """Возвращает последние сообщения чата."""
        app = self._app_required()
        kwargs: dict[str, Any] = {"limit": limit}
        if offset_id:
            kwargs["offset_id"] = offset_id
        if offset_date:
            kwargs["offset_date"] = offset_date
        messages = []
        async for msg in app.get_chat_history(chat_id, **kwargs):
            messages.append(_message_to_dict(msg))
        return messages

    async def search_messages(
        self,
        chat_id: int | str,
        query: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Ищет сообщения по тексту в чате."""
        app = self._app_required()
        messages = []
        async for msg in app.search_messages(chat_id, query=query, limit=limit):
            messages.append(_message_to_dict(msg))
        return messages

    async def get_pending_messages(self, limit: int = 50) -> list[dict[str, Any]]:
        """Возвращает новые входящие сообщения с момента последнего вызова."""
        # Читаем из «Saved Messages» (Favorites) все непрочитанные
        # Полноценная реализация требует getDialogs + фильтрацию по unread
        app = self._app_required()
        messages = []
        async for dialog in app.get_dialogs(limit=50):
            if dialog.unread_messages_count and dialog.unread_messages_count > 0:
                async for msg in app.get_chat_history(dialog.chat.id, limit=min(limit, dialog.unread_messages_count)):
                    messages.append(_message_to_dict(msg))
                    if len(messages) >= limit:
                        break
            if len(messages) >= limit:
                break
        return messages

    async def get_dialogs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Возвращает список диалогов."""
        app = self._app_required()
        result = []
        async for dialog in app.get_dialogs(limit=limit):
            last_msg = dialog.top_message
            result.append({
                "chat_id": dialog.chat.id,
                "title": getattr(dialog.chat, "title", None) or getattr(dialog.chat, "first_name", str(dialog.chat.id)),
                "unread_count": dialog.unread_messages_count or 0,
                "last_message_text": last_msg.text[:100] if last_msg and last_msg.text else None,
                "last_message_date": int(last_msg.date.timestamp()) if last_msg and last_msg.date else None,
            })
        return result

    async def get_chat(self, chat_id: int | str) -> dict[str, Any]:
        """Возвращает информацию о чате."""
        app = self._app_required()
        chat = await app.get_chat(chat_id)
        return {
            "id": chat.id,
            "type": str(chat.type).split(".")[-1].lower(),
            "title": getattr(chat, "title", None),
            "username": getattr(chat, "username", None),
            "members_count": getattr(chat, "members_count", None),
            "description": getattr(chat, "description", None),
        }

    async def get_chat_members(
        self,
        chat_id: int | str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Возвращает участников группы."""
        app = self._app_required()
        members = []
        async for member in app.get_chat_members(chat_id, limit=limit):
            members.append({
                "user_id": member.user.id,
                "first_name": member.user.first_name or "",
                "username": member.user.username,
                "status": str(member.status).split(".")[-1].lower(),
                "joined_date": int(member.joined_date.timestamp()) if member.joined_date else None,
            })
        return members

    async def download_media(self, chat_id: int | str, message_id: int, file_path: str) -> str:
        """Скачивает медиафайл из сообщения."""
        app = self._app_required()
        msg = await app.get_messages(chat_id, message_id)
        result = await app.download_media(msg, file_name=file_path)
        return str(result)

    async def get_contacts(self) -> list[dict[str, Any]]:
        """Возвращает список контактов."""
        app = self._app_required()
        contacts = await app.get_contacts()
        return [_user_to_dict(c) for c in contacts]

    async def get_user_status(self, user_id: int | str) -> dict[str, Any]:
        """Возвращает online-статус пользователя."""
        app = self._app_required()
        user = await app.get_users(user_id)
        status = user.status
        return {
            "user_id": user.id,
            "status": str(status).split(".")[-1].lower() if status else "unknown",
        }

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str = "Markdown",
        reply_to_message_id: int | None = None,
        schedule_date: int | None = None,
    ) -> dict[str, Any]:
        """Отправляет текстовое сообщение."""
        from pyrogram.enums import ParseMode as PyroParseMode  # type: ignore[import-untyped]

        app = self._app_required()
        pm = _parse_mode(parse_mode)
        kwargs: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": pm}
        if reply_to_message_id:
            kwargs["reply_to_message_id"] = reply_to_message_id
        if schedule_date:
            from datetime import datetime, timezone
            kwargs["schedule_date"] = datetime.fromtimestamp(schedule_date, timezone.utc)
        msg = await app.send_message(**kwargs)
        return _sent_to_dict(msg)

    async def send_photo(self, chat_id: int | str, file_path: str, caption: str | None = None, parse_mode: str = "Markdown") -> dict[str, Any]:
        """Отправляет фото."""
        app = self._app_required()
        msg = await app.send_photo(chat_id, photo=file_path, caption=caption, parse_mode=_parse_mode(parse_mode))
        return _sent_to_dict(msg)

    async def send_document(self, chat_id: int | str, file_path: str, caption: str | None = None) -> dict[str, Any]:
        """Отправляет документ."""
        app = self._app_required()
        msg = await app.send_document(chat_id, document=file_path, caption=caption)
        return _sent_to_dict(msg)

    async def send_video(self, chat_id: int | str, file_path: str, caption: str | None = None) -> dict[str, Any]:
        """Отправляет видео."""
        app = self._app_required()
        msg = await app.send_video(chat_id, video=file_path, caption=caption)
        return _sent_to_dict(msg)

    async def send_voice(self, chat_id: int | str, file_path: str) -> dict[str, Any]:
        """Отправляет голосовое сообщение."""
        app = self._app_required()
        msg = await app.send_voice(chat_id, voice=file_path)
        return _sent_to_dict(msg)

    async def send_sticker(self, chat_id: int | str, sticker: str) -> dict[str, Any]:
        """Отправляет стикер (file_id или путь)."""
        app = self._app_required()
        msg = await app.send_sticker(chat_id, sticker=sticker)
        return _sent_to_dict(msg)

    async def forward_messages(
        self,
        from_chat_id: int | str,
        message_ids: list[int],
        to_chat_id: int | str,
    ) -> list[dict[str, Any]]:
        """Пересылает сообщения."""
        app = self._app_required()
        msgs = await app.forward_messages(
            chat_id=to_chat_id,
            from_chat_id=from_chat_id,
            message_ids=message_ids,
        )
        if not isinstance(msgs, list):
            msgs = [msgs]
        return [_sent_to_dict(m) for m in msgs]

    async def edit_message(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any]:
        """Редактирует сообщение."""
        app = self._app_required()
        msg = await app.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=_parse_mode(parse_mode),
        )
        return _sent_to_dict(msg)

    async def delete_messages(self, chat_id: int | str, message_ids: list[int]) -> bool:
        """Удаляет сообщения."""
        app = self._app_required()
        await app.delete_messages(chat_id=chat_id, message_ids=message_ids)
        return True

    async def set_reaction(self, chat_id: int | str, message_id: int, emoji: str) -> bool:
        """Ставит реакцию на сообщение."""
        from pyrogram.types import ReactionTypeEmoji  # type: ignore[import-untyped]

        app = self._app_required()
        await app.send_reaction(
            chat_id=chat_id,
            message_id=message_id,
            emoji=emoji,
        )
        return True

    async def pin_message(self, chat_id: int | str, message_id: int, disable_notification: bool = True) -> bool:
        """Закрепляет сообщение."""
        app = self._app_required()
        await app.pin_chat_message(chat_id=chat_id, message_id=message_id, disable_notification=disable_notification)
        return True

    async def unpin_message(self, chat_id: int | str, message_id: int) -> bool:
        """Открепляет сообщение."""
        app = self._app_required()
        await app.unpin_chat_message(chat_id=chat_id, message_id=message_id)
        return True

    async def read_chat_history(self, chat_id: int | str, max_id: int = 0) -> bool:
        """Отмечает чат прочитанным."""
        app = self._app_required()
        await app.read_chat_history(chat_id=chat_id, max_id=max_id)
        return True

    async def send_chat_action(self, chat_id: int | str, action: str) -> bool:
        """Отправляет индикатор действия."""
        from pyrogram.enums import ChatAction  # type: ignore[import-untyped]

        app = self._app_required()
        action_map = {
            "typing": ChatAction.TYPING,
            "upload_photo": ChatAction.UPLOAD_PHOTO,
            "upload_document": ChatAction.UPLOAD_DOCUMENT,
            "upload_video": ChatAction.UPLOAD_VIDEO,
            "record_voice": ChatAction.RECORD_AUDIO,
            "playing": ChatAction.PLAYING,
        }
        chat_action = action_map.get(action, ChatAction.TYPING)
        await app.send_chat_action(chat_id=chat_id, action=chat_action)
        return True

    async def join_chat(self, chat_id: int | str) -> dict[str, Any]:
        """Вступает в чат/канал."""
        app = self._app_required()
        chat = await app.join_chat(chat_id)
        return {"ok": True, "chat_id": chat.id, "title": getattr(chat, "title", None)}

    async def leave_chat(self, chat_id: int | str) -> bool:
        """Покидает чат/группу."""
        app = self._app_required()
        await app.leave_chat(chat_id)
        return True

    async def create_group(self, title: str, user_ids: list[int | str]) -> dict[str, Any]:
        """Создаёт группу."""
        app = self._app_required()
        chat = await app.create_group(title=title, users=user_ids)
        return {"ok": True, "chat_id": chat.id, "title": chat.title}

    async def set_chat_title(self, chat_id: int | str, title: str) -> bool:
        """Изменяет название чата."""
        app = self._app_required()
        await app.set_chat_title(chat_id=chat_id, title=title)
        return True

    async def set_chat_description(self, chat_id: int | str, description: str) -> bool:
        """Изменяет описание чата."""
        app = self._app_required()
        await app.set_chat_description(chat_id=chat_id, description=description)
        return True

    async def set_chat_photo(self, chat_id: int | str, photo_path: str) -> bool:
        """Изменяет фото чата."""
        app = self._app_required()
        await app.set_chat_photo(chat_id=chat_id, photo=photo_path)
        return True

    async def ban_chat_member(self, chat_id: int | str, user_id: int | str, until_date: int | None = None) -> bool:
        """Блокирует участника группы."""
        from datetime import datetime, timezone  # noqa: PLC0415

        app = self._app_required()
        kwargs: dict[str, Any] = {"chat_id": chat_id, "user_id": user_id}
        if until_date:
            kwargs["until_date"] = datetime.fromtimestamp(until_date, timezone.utc)
        await app.ban_chat_member(**kwargs)
        return True

    async def unban_chat_member(self, chat_id: int | str, user_id: int | str) -> bool:
        """Разблокирует участника."""
        app = self._app_required()
        await app.unban_chat_member(chat_id=chat_id, user_id=user_id)
        return True

    async def promote_chat_member(
        self,
        chat_id: int | str,
        user_id: int | str,
        can_manage_chat: bool = True,
        can_delete_messages: bool = True,
        can_restrict_members: bool = False,
        can_promote_members: bool = False,
        can_change_info: bool = False,
        can_invite_users: bool = True,
        can_pin_messages: bool = False,
    ) -> bool:
        """Назначает участника администратором."""
        from pyrogram.types import ChatPrivileges  # type: ignore[import-untyped]

        app = self._app_required()
        await app.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            privileges=ChatPrivileges(
                can_manage_chat=can_manage_chat,
                can_delete_messages=can_delete_messages,
                can_restrict_members=can_restrict_members,
                can_promote_members=can_promote_members,
                can_change_info=can_change_info,
                can_invite_users=can_invite_users,
                can_pin_messages=can_pin_messages,
            ),
        )
        return True

    async def demote_chat_member(self, chat_id: int | str, user_id: int | str) -> bool:
        """Снимает с администратора."""
        from pyrogram.types import ChatPrivileges  # type: ignore[import-untyped]

        app = self._app_required()
        await app.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            privileges=ChatPrivileges(),
        )
        return True

    async def get_scheduled_messages(self, chat_id: int | str) -> list[dict[str, Any]]:
        """Возвращает запланированные сообщения."""
        app = self._app_required()
        msgs = await app.get_scheduled_messages(chat_id)
        return [_message_to_dict(m) for m in (msgs or [])]

    async def delete_scheduled_message(self, chat_id: int | str, message_id: int) -> bool:
        """Отменяет запланированное сообщение."""
        app = self._app_required()
        await app.delete_scheduled_messages(chat_id, [message_id])
        return True


# ---------- Хелперы ----------

def _user_to_dict(user: Any) -> dict[str, Any]:
    return {
        "id": user.id,
        "first_name": user.first_name or "",
        "last_name": user.last_name,
        "username": user.username,
        "phone": getattr(user, "phone_number", None),
        "is_bot": bool(getattr(user, "is_bot", False)),
    }


def _message_to_dict(msg: Any) -> dict[str, Any]:
    sender_id: int | None = None
    sender_name: str | None = None
    if msg.from_user:
        sender_id = msg.from_user.id
        sender_name = msg.from_user.first_name

    media_type: str | None = None
    if msg.photo:
        media_type = "photo"
    elif msg.document:
        media_type = "document"
    elif msg.video:
        media_type = "video"
    elif msg.voice:
        media_type = "voice"
    elif msg.sticker:
        media_type = "sticker"

    return {
        "id": msg.id,
        "chat_id": msg.chat.id if msg.chat else None,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "text": msg.text or msg.caption,
        "date": int(msg.date.timestamp()) if msg.date else 0,
        "media_type": media_type,
        "reply_to_id": msg.reply_to_message_id,
        "is_outgoing": bool(getattr(msg, "outgoing", False)),
    }


def _sent_to_dict(msg: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "message_id": msg.id,
        "chat_id": msg.chat.id if msg.chat else None,
        "date": int(msg.date.timestamp()) if msg.date else 0,
    }


def _parse_mode(mode: str) -> Any:
    from pyrogram.enums import ParseMode  # type: ignore[import-untyped]

    mapping = {
        "Markdown": ParseMode.MARKDOWN,
        "HTML": ParseMode.HTML,
        "disabled": ParseMode.DISABLED,
    }
    return mapping.get(mode, ParseMode.MARKDOWN)
