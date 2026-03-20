"""Модуль telegram_user — чтение и мониторинг Telegram через MTProto (Pyrogram)."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog
from mcp.server.fastmcp import FastMCP

from mcp_gateway.modules.base import BaseModule
from mcp_gateway.modules.telegram_user.client import UserClient, UserSettings
from mcp_gateway.modules.telegram_user.models import AutoReply, MessageTemplate

logger = structlog.get_logger(__name__)

_STATE_FILE = Path("~/.mcp-gateway/tg_user_state.json").expanduser()


class TelegramUserModule(BaseModule):
    """Модуль Telegram User API (MTProto через Pyrogram).

    Предоставляет чтение сообщений, поиск, профили, участников групп.
    Отправка tg_* — только в чужие чаты/группы/каналы, не пользователю бота.

    Attributes:
        name: Уникальное имя модуля.
        _client: Pyrogram UserClient.
        _auto_replies: Правила автоответа {id: AutoReply}.
        _templates: Шаблоны сообщений {id: MessageTemplate}.
    """

    name = "telegram_user"

    def __init__(self) -> None:
        settings = UserSettings()
        self._client = UserClient(settings)
        self._auto_replies: dict[str, AutoReply] = {}
        self._templates: dict[str, MessageTemplate] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Загружает автоответы и шаблоны из файла."""
        if not _STATE_FILE.exists():
            return
        try:
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            for ar in data.get("auto_replies", []):
                self._auto_replies[ar["id"]] = AutoReply(**ar)
            for tmpl in data.get("templates", []):
                self._templates[tmpl["id"]] = MessageTemplate(**tmpl)
        except Exception as exc:
            logger.warning("tg_user_state_load_error", error=str(exc))

    def _save_state(self) -> None:
        """Сохраняет автоответы и шаблоны в файл."""
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "auto_replies": [ar.model_dump() for ar in self._auto_replies.values()],
            "templates": [t.model_dump() for t in self._templates.values()],
        }
        _STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def startup(self) -> None:
        """Инициализирует Pyrogram-клиент."""
        await self._client.start()

    def register_tools(self, mcp: FastMCP) -> None:  # noqa: C901, PLR0915
        """Регистрирует tg_* инструменты.

        Args:
            mcp: Экземпляр FastMCP.
        """
        client = self._client

        # ------------------------------------------------------------------ #
        # Статус сессии                                                       #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_session_status() -> dict[str, object]:
            """Проверить статус Pyrogram-сессии.

            Returns:
                Словарь {connected, username, phone}.
            """
            try:
                me = await client.get_me()
                return {"connected": True, "username": me.get("username"), "phone": me.get("phone")}
            except Exception as exc:
                return {"connected": False, "error": str(exc)}

        @mcp.tool()
        async def tg_get_me() -> dict[str, object]:
            """Информация о текущем аккаунте.

            Returns:
                Профиль {id, first_name, last_name, username, phone}.
            """
            try:
                return await client.get_me()
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        # ------------------------------------------------------------------ #
        # Пользователи                                                        #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_get_user(
            user_id: int | str,
        ) -> dict[str, object]:
            """Профиль пользователя по ID или @username.

            Args:
                user_id: ID (int) или @username (str).

            Returns:
                Профиль {id, first_name, last_name, username, phone, is_bot}.
            """
            try:
                return await client.get_user(user_id)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_get_contacts() -> dict[str, object]:
            """Список контактов аккаунта.

            Returns:
                Словарь {contacts: [...], count: int}.
            """
            try:
                contacts = await client.get_contacts()
                return {"contacts": contacts, "count": len(contacts)}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_search_contacts(
            query: str,
        ) -> dict[str, object]:
            """Поиск контактов по имени или username.

            Args:
                query: Строка поиска.

            Returns:
                Словарь {contacts: [...], count: int}.
            """
            try:
                contacts = await client.get_contacts()
                q = query.lower()
                filtered = [
                    c for c in contacts
                    if q in (c.get("first_name") or "").lower()
                    or q in (c.get("last_name") or "").lower()
                    or q in (c.get("username") or "").lower()
                ]
                return {"contacts": filtered, "count": len(filtered)}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_get_user_status(
            user_id: int | str,
        ) -> dict[str, object]:
            """Online-статус пользователя.

            Args:
                user_id: ID или @username.

            Returns:
                Словарь {user_id, status} ('online', 'recently', 'last_week', 'long_ago', 'offline').
            """
            try:
                return await client.get_user_status(user_id)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        # ------------------------------------------------------------------ #
        # Сообщения                                                           #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_get_messages(
            chat_id: int | str,
            limit: int = 50,
            offset_id: int = 0,
        ) -> dict[str, object]:
            """Последние сообщения чата.

            Args:
                chat_id: ID чата или @username.
                limit: Количество сообщений (1–200).
                offset_id: ID сообщения для пагинации (0 — с конца).

            Returns:
                Словарь {messages: [...], count: int}.
            """
            try:
                messages = await client.get_messages(chat_id, limit=min(limit, 200), offset_id=offset_id)
                return {"messages": messages, "count": len(messages)}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_search_messages(
            chat_id: int | str,
            query: str,
            limit: int = 50,
        ) -> dict[str, object]:
            """Поиск сообщений по тексту в чате.

            Args:
                chat_id: ID чата или @username.
                query: Поисковый запрос.
                limit: Максимум результатов.

            Returns:
                Словарь {messages: [...], count: int}.
            """
            try:
                messages = await client.search_messages(chat_id, query, limit=limit)
                return {"messages": messages, "count": len(messages)}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_get_pending_messages(
            limit: int = 50,
        ) -> dict[str, object]:
            """Входящие непрочитанные сообщения.

            Возвращает непрочитанные сообщения из всех диалогов.

            Args:
                limit: Максимум сообщений.

            Returns:
                Словарь {messages: [...], count: int}.
            """
            try:
                messages = await client.get_pending_messages(limit=limit)
                return {"messages": messages, "count": len(messages)}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_get_read_status(
            chat_id: int | str,
        ) -> dict[str, object]:
            """Статус прочтения чата.

            Args:
                chat_id: ID чата.

            Returns:
                Словарь {chat_id, unread_count}.
            """
            try:
                dialogs = await client.get_dialogs(limit=100)
                for d in dialogs:
                    if str(d["chat_id"]) == str(chat_id):
                        return {"chat_id": d["chat_id"], "unread_count": d["unread_count"]}
                return {"chat_id": chat_id, "unread_count": 0}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        # ------------------------------------------------------------------ #
        # Диалоги и чаты                                                     #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_get_dialogs(
            limit: int = 50,
        ) -> dict[str, object]:
            """Список диалогов (папки чатов).

            Args:
                limit: Количество диалогов (1–200).

            Returns:
                Словарь {dialogs: [...], count: int}.
            """
            try:
                dialogs = await client.get_dialogs(limit=min(limit, 200))
                return {"dialogs": dialogs, "count": len(dialogs)}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_get_chat(
            chat_id: int | str,
        ) -> dict[str, object]:
            """Информация о чате/группе/канале.

            Args:
                chat_id: ID чата или @username.

            Returns:
                Информация {id, type, title, username, members_count, description}.
            """
            try:
                return await client.get_chat(chat_id)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_get_chat_members(
            chat_id: int | str,
            limit: int = 100,
        ) -> dict[str, object]:
            """Список участников группы.

            Args:
                chat_id: ID группы или @username.
                limit: Максимум участников (1–1000).

            Returns:
                Словарь {members: [...], count: int}.
            """
            try:
                members = await client.get_chat_members(chat_id, limit=min(limit, 1000))
                return {"members": members, "count": len(members)}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        # ------------------------------------------------------------------ #
        # Медиафайлы                                                         #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_download_media(
            chat_id: int | str,
            message_id: int,
            file_path: str,
        ) -> dict[str, object]:
            """Скачать медиафайл из сообщения.

            Args:
                chat_id: ID чата.
                message_id: ID сообщения с медиафайлом.
                file_path: Путь для сохранения файла.

            Returns:
                Словарь {ok, path}.
            """
            try:
                path = await client.download_media(chat_id, message_id, file_path)
                return {"ok": True, "path": path}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        # ------------------------------------------------------------------ #
        # Отправка (только в чужие чаты, не пользователю бота!)             #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_send_message(
            chat_id: int | str,
            text: str,
            parse_mode: str = "Markdown",
            reply_to_message_id: int | None = None,
        ) -> dict[str, object]:
            """Отправить текстовое сообщение от аккаунта.

            ⚠️ Использовать только в группах, каналах, избранном.
            НЕ отправлять пользователю бота — для этого используй bot_send_message.

            Args:
                chat_id: ID чата или @username.
                text: Текст сообщения.
                parse_mode: 'Markdown', 'HTML' или 'disabled'.
                reply_to_message_id: ID сообщения для ответа (опционально).

            Returns:
                Словарь {ok, message_id, chat_id, date}.
            """
            try:
                return await client.send_message(chat_id, text, parse_mode, reply_to_message_id)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_send_photo(
            chat_id: int | str,
            file_path: str,
            caption: str | None = None,
            parse_mode: str = "Markdown",
        ) -> dict[str, object]:
            """Отправить фото от аккаунта.

            Args:
                chat_id: ID чата или @username.
                file_path: Абсолютный путь к изображению.
                caption: Подпись (опционально).
                parse_mode: 'Markdown', 'HTML' или 'disabled'.

            Returns:
                Словарь {ok, message_id, chat_id, date}.
            """
            try:
                return await client.send_photo(chat_id, file_path, caption, parse_mode)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_send_document(
            chat_id: int | str,
            file_path: str,
            caption: str | None = None,
        ) -> dict[str, object]:
            """Отправить документ от аккаунта.

            Args:
                chat_id: ID чата или @username.
                file_path: Абсолютный путь к файлу.
                caption: Подпись (опционально).

            Returns:
                Словарь {ok, message_id, chat_id, date}.
            """
            try:
                return await client.send_document(chat_id, file_path, caption)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_send_video(
            chat_id: int | str,
            file_path: str,
            caption: str | None = None,
        ) -> dict[str, object]:
            """Отправить видео от аккаунта.

            Args:
                chat_id: ID чата или @username.
                file_path: Абсолютный путь к видеофайлу.
                caption: Подпись (опционально).

            Returns:
                Словарь {ok, message_id, chat_id, date}.
            """
            try:
                return await client.send_video(chat_id, file_path, caption)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_send_voice(
            chat_id: int | str,
            file_path: str,
        ) -> dict[str, object]:
            """Отправить голосовое сообщение от аккаунта.

            Args:
                chat_id: ID чата или @username.
                file_path: Путь к ogg/mp3-файлу (голосовое).

            Returns:
                Словарь {ok, message_id, chat_id, date}.
            """
            try:
                return await client.send_voice(chat_id, file_path)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_send_sticker(
            chat_id: int | str,
            sticker: str,
        ) -> dict[str, object]:
            """Отправить стикер от аккаунта.

            Args:
                chat_id: ID чата или @username.
                sticker: file_id стикера или путь к .webp файлу.

            Returns:
                Словарь {ok, message_id, chat_id, date}.
            """
            try:
                return await client.send_sticker(chat_id, sticker)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_forward_messages(
            from_chat_id: int | str,
            message_ids: list[int],
            to_chat_id: int | str,
        ) -> dict[str, object]:
            """Переслать сообщения из одного чата в другой.

            Args:
                from_chat_id: ID исходного чата.
                message_ids: Список ID сообщений для пересылки.
                to_chat_id: ID целевого чата.

            Returns:
                Словарь {ok, messages: [...]}.
            """
            try:
                results = await client.forward_messages(from_chat_id, message_ids, to_chat_id)
                return {"ok": True, "messages": results}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_edit_message(
            chat_id: int | str,
            message_id: int,
            text: str,
            parse_mode: str = "Markdown",
        ) -> dict[str, object]:
            """Редактировать сообщение.

            Args:
                chat_id: ID чата.
                message_id: ID редактируемого сообщения.
                text: Новый текст.
                parse_mode: 'Markdown', 'HTML' или 'disabled'.

            Returns:
                Словарь {ok, message_id, chat_id, date}.
            """
            try:
                return await client.edit_message(chat_id, message_id, text, parse_mode)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_delete_messages(
            chat_id: int | str,
            message_ids: list[int],
        ) -> dict[str, object]:
            """Удалить сообщения.

            Args:
                chat_id: ID чата.
                message_ids: Список ID сообщений.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.delete_messages(chat_id, message_ids)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_set_reaction(
            chat_id: int | str,
            message_id: int,
            emoji: str,
        ) -> dict[str, object]:
            """Поставить реакцию на сообщение.

            Args:
                chat_id: ID чата.
                message_id: ID сообщения.
                emoji: Emoji реакции (например '👍', '❤️', '🔥').

            Returns:
                Словарь {ok}.
            """
            try:
                await client.set_reaction(chat_id, message_id, emoji)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_pin_message(
            chat_id: int | str,
            message_id: int,
            disable_notification: bool = True,
        ) -> dict[str, object]:
            """Закрепить сообщение в чате.

            Args:
                chat_id: ID чата.
                message_id: ID сообщения.
                disable_notification: Без уведомления (по умолчанию True).

            Returns:
                Словарь {ok}.
            """
            try:
                await client.pin_message(chat_id, message_id, disable_notification)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_unpin_message(
            chat_id: int | str,
            message_id: int,
        ) -> dict[str, object]:
            """Открепить сообщение.

            Args:
                chat_id: ID чата.
                message_id: ID сообщения.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.unpin_message(chat_id, message_id)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_read_chat_history(
            chat_id: int | str,
            max_id: int = 0,
        ) -> dict[str, object]:
            """Отметить чат прочитанным.

            Args:
                chat_id: ID чата.
                max_id: ID последнего прочитанного сообщения (0 = все).

            Returns:
                Словарь {ok}.
            """
            try:
                await client.read_chat_history(chat_id, max_id)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_send_chat_action(
            chat_id: int | str,
            action: str = "typing",
        ) -> dict[str, object]:
            """Отправить индикатор действия ('печатает...').

            Args:
                chat_id: ID чата.
                action: 'typing', 'upload_photo', 'upload_document', 'upload_video',
                        'record_voice', 'playing'.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.send_chat_action(chat_id, action)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        # ------------------------------------------------------------------ #
        # Управление чатами                                                   #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_join_chat(
            chat_id: int | str,
        ) -> dict[str, object]:
            """Вступить в чат или канал.

            Args:
                chat_id: ID или @username публичного чата.

            Returns:
                Словарь {ok, chat_id, title}.
            """
            try:
                return await client.join_chat(chat_id)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_leave_chat(
            chat_id: int | str,
        ) -> dict[str, object]:
            """Покинуть чат или группу.

            Args:
                chat_id: ID чата.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.leave_chat(chat_id)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_create_group(
            title: str,
            user_ids: list[int],
        ) -> dict[str, object]:
            """Создать группу.

            Args:
                title: Название группы.
                user_ids: Список ID участников (кроме себя).

            Returns:
                Словарь {ok, chat_id, title}.
            """
            try:
                return await client.create_group(title, user_ids)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_set_chat_title(
            chat_id: int | str,
            title: str,
        ) -> dict[str, object]:
            """Изменить название чата.

            Args:
                chat_id: ID чата (нужны права администратора).
                title: Новое название.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.set_chat_title(chat_id, title)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_set_chat_description(
            chat_id: int | str,
            description: str,
        ) -> dict[str, object]:
            """Изменить описание чата.

            Args:
                chat_id: ID чата.
                description: Новое описание.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.set_chat_description(chat_id, description)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_set_chat_photo(
            chat_id: int | str,
            photo_path: str,
        ) -> dict[str, object]:
            """Изменить фото чата.

            Args:
                chat_id: ID чата.
                photo_path: Абсолютный путь к изображению.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.set_chat_photo(chat_id, photo_path)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        # ------------------------------------------------------------------ #
        # Управление участниками                                              #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_ban_chat_member(
            chat_id: int | str,
            user_id: int | str,
            until_date: int | None = None,
        ) -> dict[str, object]:
            """Заблокировать участника группы.

            Args:
                chat_id: ID чата.
                user_id: ID пользователя.
                until_date: Unix timestamp снятия блокировки (None = навсегда).

            Returns:
                Словарь {ok}.
            """
            try:
                await client.ban_chat_member(chat_id, user_id, until_date)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_kick_chat_member(
            chat_id: int | str,
            user_id: int | str,
        ) -> dict[str, object]:
            """Выкинуть участника из группы (без постоянной блокировки).

            Args:
                chat_id: ID чата.
                user_id: ID пользователя.

            Returns:
                Словарь {ok}.
            """
            try:
                # Pyrogram: бан + немедленный разбан = кик
                await client.ban_chat_member(chat_id, user_id)
                await client.unban_chat_member(chat_id, user_id)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_unban_chat_member(
            chat_id: int | str,
            user_id: int | str,
        ) -> dict[str, object]:
            """Разблокировать участника.

            Args:
                chat_id: ID чата.
                user_id: ID пользователя.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.unban_chat_member(chat_id, user_id)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_promote_chat_member(
            chat_id: int | str,
            user_id: int | str,
            can_delete_messages: bool = True,
            can_restrict_members: bool = False,
            can_promote_members: bool = False,
            can_change_info: bool = False,
            can_invite_users: bool = True,
            can_pin_messages: bool = False,
        ) -> dict[str, object]:
            """Назначить участника администратором.

            Args:
                chat_id: ID чата.
                user_id: ID пользователя.
                can_delete_messages: Удалять сообщения.
                can_restrict_members: Ограничивать участников.
                can_promote_members: Назначать администраторов.
                can_change_info: Изменять информацию о чате.
                can_invite_users: Приглашать пользователей.
                can_pin_messages: Закреплять сообщения.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.promote_chat_member(
                    chat_id, user_id,
                    can_delete_messages=can_delete_messages,
                    can_restrict_members=can_restrict_members,
                    can_promote_members=can_promote_members,
                    can_change_info=can_change_info,
                    can_invite_users=can_invite_users,
                    can_pin_messages=can_pin_messages,
                )
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_demote_chat_member(
            chat_id: int | str,
            user_id: int | str,
        ) -> dict[str, object]:
            """Снять администратора.

            Args:
                chat_id: ID чата.
                user_id: ID пользователя.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.demote_chat_member(chat_id, user_id)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        # ------------------------------------------------------------------ #
        # Запланированные сообщения                                           #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_schedule_message(
            chat_id: int | str,
            text: str,
            schedule_date: int,
            parse_mode: str = "Markdown",
        ) -> dict[str, object]:
            """Запланировать сообщение.

            Args:
                chat_id: ID чата.
                text: Текст сообщения.
                schedule_date: Unix timestamp для отправки.
                parse_mode: 'Markdown', 'HTML' или 'disabled'.

            Returns:
                Словарь {ok, message_id, chat_id, date}.
            """
            try:
                return await client.send_message(chat_id, text, parse_mode, schedule_date=schedule_date)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_list_scheduled(
            chat_id: int | str,
        ) -> dict[str, object]:
            """Список запланированных сообщений.

            Args:
                chat_id: ID чата.

            Returns:
                Словарь {messages: [...], count: int}.
            """
            try:
                messages = await client.get_scheduled_messages(chat_id)
                return {"messages": messages, "count": len(messages)}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_cancel_scheduled(
            chat_id: int | str,
            message_id: int,
        ) -> dict[str, object]:
            """Отменить запланированное сообщение.

            Args:
                chat_id: ID чата.
                message_id: ID запланированного сообщения.

            Returns:
                Словарь {ok}.
            """
            try:
                await client.delete_scheduled_message(chat_id, message_id)
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        # ------------------------------------------------------------------ #
        # Автоответы                                                          #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_set_auto_reply(
            keyword: str,
            response: str,
            chat_id: int | str | None = None,
            case_sensitive: bool = False,
        ) -> dict[str, object]:
            """Создать правило автоответа по ключевому слову.

            Правила применяются к входящим сообщениям. Для активации требуется
            запущенный обработчик событий (get_pending_messages + ручная проверка).

            Args:
                keyword: Ключевое слово или regex для поиска в тексте.
                response: Текст автоответа.
                chat_id: ID чата (None = все чаты).
                case_sensitive: Учитывать регистр.

            Returns:
                Словарь {ok, id, rule}.
            """
            rule = AutoReply(
                id=str(uuid.uuid4())[:8],
                keyword=keyword,
                response=response,
                chat_id=chat_id,
                case_sensitive=case_sensitive,
            )
            self._auto_replies[rule.id] = rule
            self._save_state()
            return {"ok": True, "id": rule.id, "rule": rule.model_dump()}

        @mcp.tool()
        async def tg_list_auto_replies() -> dict[str, object]:
            """Список всех правил автоответа.

            Returns:
                Словарь {rules: [...], count: int}.
            """
            rules = [r.model_dump() for r in self._auto_replies.values()]
            return {"rules": rules, "count": len(rules)}

        @mcp.tool()
        async def tg_remove_auto_reply(
            rule_id: str,
        ) -> dict[str, object]:
            """Удалить правило автоответа.

            Args:
                rule_id: ID правила (из tg_set_auto_reply или tg_list_auto_replies).

            Returns:
                Словарь {ok}.
            """
            if rule_id not in self._auto_replies:
                return {"ok": False, "error": f"Rule {rule_id!r} not found"}
            del self._auto_replies[rule_id]
            self._save_state()
            return {"ok": True}

        # ------------------------------------------------------------------ #
        # Шаблоны сообщений                                                  #
        # ------------------------------------------------------------------ #

        @mcp.tool()
        async def tg_create_template(
            name: str,
            text: str,
            parse_mode: str = "Markdown",
        ) -> dict[str, object]:
            """Создать шаблон сообщения.

            Шаблон поддерживает подстановки: используй {placeholder} в тексте
            и передавай variables в tg_send_template.

            Args:
                name: Название шаблона (уникальное).
                text: Текст шаблона (например, 'Привет, {name}! {message}').
                parse_mode: 'Markdown', 'HTML' или 'disabled'.

            Returns:
                Словарь {ok, id, template}.
            """
            tmpl = MessageTemplate(
                id=str(uuid.uuid4())[:8],
                name=name,
                text=text,
                parse_mode=parse_mode,
            )
            self._templates[tmpl.id] = tmpl
            self._save_state()
            return {"ok": True, "id": tmpl.id, "template": tmpl.model_dump()}

        @mcp.tool()
        async def tg_list_templates() -> dict[str, object]:
            """Список шаблонов сообщений.

            Returns:
                Словарь {templates: [...], count: int}.
            """
            templates = [t.model_dump() for t in self._templates.values()]
            return {"templates": templates, "count": len(templates)}

        @mcp.tool()
        async def tg_delete_template(
            template_id: str,
        ) -> dict[str, object]:
            """Удалить шаблон сообщения.

            Args:
                template_id: ID шаблона.

            Returns:
                Словарь {ok}.
            """
            if template_id not in self._templates:
                return {"ok": False, "error": f"Template {template_id!r} not found"}
            del self._templates[template_id]
            self._save_state()
            return {"ok": True}

        @mcp.tool()
        async def tg_send_template(
            chat_id: int | str,
            template_id: str,
            variables: dict[str, str] | None = None,
        ) -> dict[str, object]:
            """Отправить сообщение по шаблону.

            Args:
                chat_id: ID чата.
                template_id: ID шаблона (из tg_create_template или tg_list_templates).
                variables: Словарь подстановок {placeholder: value}.

            Returns:
                Словарь {ok, message_id, chat_id, date}.
            """
            tmpl = self._templates.get(template_id)
            if not tmpl:
                return {"ok": False, "error": f"Template {template_id!r} not found"}
            try:
                text = tmpl.text.format(**(variables or {}))
            except KeyError as exc:
                return {"ok": False, "error": f"Missing template variable: {exc}"}
            try:
                return await client.send_message(chat_id, text, tmpl.parse_mode)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @mcp.tool()
        async def tg_send_bulk(
            chat_ids: list[int | str],
            text: str,
            parse_mode: str = "Markdown",
            delay_sec: float = 1.0,
        ) -> dict[str, object]:
            """Массовая рассылка сообщения по нескольким чатам.

            Args:
                chat_ids: Список ID чатов или @username.
                text: Текст для рассылки.
                parse_mode: 'Markdown', 'HTML' или 'disabled'.
                delay_sec: Задержка между отправками в секундах (минимум 0.5).

            Returns:
                Словарь {ok, sent: int, failed: int, errors: [...]}.
            """
            import asyncio as _asyncio

            delay = max(0.5, delay_sec)
            sent, failed = 0, 0
            errors = []

            for chat_id in chat_ids:
                try:
                    await client.send_message(chat_id, text, parse_mode)
                    sent += 1
                except Exception as exc:
                    failed += 1
                    errors.append({"chat_id": str(chat_id), "error": str(exc)})
                if chat_id != chat_ids[-1]:
                    await _asyncio.sleep(delay)

            return {"ok": True, "sent": sent, "failed": failed, "errors": errors}

    async def shutdown(self) -> None:
        """Закрывает Pyrogram-сессию."""
        await self._client.stop()
