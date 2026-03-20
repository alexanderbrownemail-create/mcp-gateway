# Модули MCP-Gateway

## Интерфейс модуля (base.py)

Каждый модуль наследует `BaseModule`:

```python
class BaseModule:
    name: str                          # уникальное имя (telegram_user, telegram_bot)

    async def startup(self) -> None:
        """Инициализация: подключения, сессии, background tasks."""

    def register_tools(self, mcp: FastMCP) -> None:
        """Регистрация @mcp.tool() — вызывается один раз при старте."""

    async def shutdown(self) -> None:
        """Graceful shutdown: закрыть соединения, остановить tasks."""
```

---

## Модуль: telegram_user

**Статус:** в разработке (перенос из `telegram-account-manager`)

**Транспорт:** Pyrogram → Telegram MTProto → User Account

**Назначение:** чтение и мониторинг. Агент **не отправляет** сообщения через этот модуль.

### Конфигурация

```bash
TELEGRAM_API_ID=...          # Telegram App ID (my.telegram.org)
TELEGRAM_API_HASH=...        # Telegram App Hash
TELEGRAM_PHONE=...           # Номер телефона аккаунта
TG_MANAGER_SESSION_DIR=~/.telegram-sessions
TG_MANAGER_RATE_LIMIT=20     # req/min
```

### Инструменты (tg_*)

| Инструмент | Описание |
|------------|----------|
| `tg_session_status` | Статус сессии (подключён/нет) |
| `tg_create_session` | Создать/обновить сессию |
| `tg_get_me` | Информация о текущем аккаунте |
| `tg_get_user` | Профиль пользователя по ID/username |
| `tg_get_messages` | Последние сообщения чата |
| `tg_search_messages` | Поиск по тексту в чате |
| `tg_get_pending_messages` | Входящие с последнего опроса |
| `tg_get_dialogs` | Список последних диалогов |
| `tg_get_chat` | Информация о чате/группе |
| `tg_get_chat_members` | Участники группы |
| `tg_download_media` | Скачать медиафайл |
| `tg_get_file_info` | Метаданные медиафайла |
| `tg_get_contacts` | Список контактов |
| `tg_search_contacts` | Поиск контактов |
| `tg_get_user_status` | Online-статус пользователя |
| `tg_get_read_status` | Статус прочтения чата |

---

## Модуль: telegram_bot

**Статус:** в разработке (новый)

**Транспорт:** httpx → Telegram Bot API (HTTPS)

**Назначение:** все исходящие сообщения агента — только через бота.

### Конфигурация

```bash
TELEGRAM_BOT_TOKEN=...    # @BotFather token
```

### Инструменты (bot_*)

#### bot_send_message

```
Параметры:
  chat_id: int | str          — ID чата или username
  text: str                   — текст (markdown/html)
  parse_mode: str = "markdown"
  buttons: list[list[dict]] | None
    — inline keyboard: [[{"text": "Да", "callback_data": "yes"}, ...], ...]
  reply_to_message_id: int | None

Возвращает: {"ok": true, "message_id": int}
```

#### bot_send_document

```
Параметры:
  chat_id: int | str
  file_path: str              — абсолютный путь на сервере
  caption: str | None
  parse_mode: str = "markdown"

Примечание: файл читается с диска сервера и загружается multipart/form-data.
```

#### bot_send_photo

```
Параметры:
  chat_id: int | str
  file_path: str
  caption: str | None
  parse_mode: str = "markdown"
```

#### bot_answer_callback

```
Параметры:
  callback_query_id: str      — ID из входящего callback_query
  text: str | None            — текст всплывающего уведомления
  show_alert: bool = False    — показать как alert (не тост)

Использование: ответить на нажатие inline-кнопки.
```

#### bot_edit_message

```
Параметры:
  chat_id: int | str
  message_id: int
  text: str
  parse_mode: str = "markdown"
  buttons: list[list[dict]] | None

Использование: обновить текст или клавиатуру уже отправленного сообщения.
```

---

## Модуль: openclaw (будущее)

**Статус:** заглушка

**Назначение:** обёртки над нативными инструментами OpenClaw, недоступными в Claude Code harness.

Потенциальные инструменты:
- `oc_memory_read(key)` — чтение из памяти агента
- `oc_memory_write(key, value)` — запись в память
- `oc_task_create(...)` — создание задачи
- `oc_session_spawn(prompt)` — запуск sub-агента

Реализация зависит от OpenClaw API / IPC-механизма.
