# Модули MCP-Gateway

Полный справочник по всем модулям, инструментам и их спецификациям.

## Интерфейс модуля (base.py)

```python
class BaseModule:
    name: str                          # уникальное имя модуля

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

```bash
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_PHONE=...
TG_MANAGER_SESSION_DIR=~/.telegram-sessions
TG_MANAGER_RATE_LIMIT=20
```

| Инструмент | Описание |
|------------|----------|
| `tg_session_status` | Статус сессии |
| `tg_create_session` | Создать/обновить сессию |
| `tg_get_me` | Информация об аккаунте |
| `tg_get_user` | Профиль пользователя |
| `tg_get_messages` | Последние сообщения чата |
| `tg_search_messages` | Поиск по тексту |
| `tg_get_pending_messages` | Входящие с последнего опроса |
| `tg_get_dialogs` | Список диалогов |
| `tg_get_chat` | Информация о чате/группе |
| `tg_get_chat_members` | Участники группы |
| `tg_download_media` | Скачать медиафайл |
| `tg_get_file_info` | Метаданные медиафайла |
| `tg_get_contacts` | Список контактов |
| `tg_search_contacts` | Поиск контактов |
| `tg_get_user_status` | Online-статус пользователя |
| `tg_get_read_status` | Статус прочтения чата |
| `tg_send_message` | Отправить текст (только в чужие чаты, не пользователю!) |
| `tg_send_photo` | Отправить фото |
| `tg_send_document` | Отправить файл |
| `tg_send_video` | Отправить видео |
| `tg_send_voice` | Отправить голосовое |
| `tg_send_sticker` | Отправить стикер |
| `tg_forward_messages` | Переслать сообщения |
| `tg_edit_message` | Редактировать сообщение |
| `tg_delete_messages` | Удалить сообщения |
| `tg_set_reaction` | Поставить реакцию |
| `tg_pin_message` | Закрепить сообщение |
| `tg_unpin_message` | Открепить сообщение |
| `tg_read_chat_history` | Отметить чат прочитанным |
| `tg_send_chat_action` | Индикатор "печатает..." |
| `tg_join_chat` | Вступить в чат |
| `tg_leave_chat` | Покинуть чат |
| `tg_create_group` | Создать группу |
| `tg_set_chat_title` | Изменить название |
| `tg_set_chat_description` | Изменить описание |
| `tg_set_chat_photo` | Изменить фото |
| `tg_ban_chat_member` | Заблокировать пользователя |
| `tg_kick_chat_member` | Выкинуть пользователя |
| `tg_unban_chat_member` | Разблокировать |
| `tg_promote_chat_member` | Назначить админом |
| `tg_demote_chat_member` | Снять с админа |
| `tg_get_read_status` | Статус прочтения |
| `tg_schedule_message` | Запланировать сообщение |
| `tg_list_scheduled` | Список запланированных |
| `tg_cancel_scheduled` | Отменить запланированное |
| `tg_set_auto_reply` | Автоответ по ключевому слову |
| `tg_list_auto_replies` | Список автоответов |
| `tg_remove_auto_reply` | Удалить автоответ |
| `tg_create_template` | Создать шаблон |
| `tg_list_templates` | Список шаблонов |
| `tg_delete_template` | Удалить шаблон |
| `tg_send_template` | Отправить шаблон |
| `tg_send_bulk` | Массовая рассылка |

---

## Модуль: telegram_bot

**Статус:** частично готов (`modules/telegram_bot/module.py`)
**Транспорт:** httpx → Telegram Bot API
**Назначение:** все исходящие сообщения агента пользователю — только через бота.

```bash
TELEGRAM_BOT_TOKEN=...
```

| Инструмент | Описание |
|------------|----------|
| `bot_send_message` | Текст + optional inline-кнопки |
| `bot_send_document` | Файл с диска сервера |
| `bot_send_photo` | Фото с диска сервера |
| `bot_send_video` | Видео с диска сервера |
| `bot_send_voice` | Голосовое: edge-tts → ogg-opus → sendVoice |
| `bot_send_sticker` | Стикер по file_id |
| `bot_forward_message` | Переслать сообщение |
| `bot_set_typing` | sendChatAction "typing" |
| `bot_edit_message` | Изменить текст и/или клавиатуру |
| `bot_delete_message` | Удалить сообщение |
| `bot_pin_message` | Закрепить сообщение |
| `bot_answer_callback` | Ответ на нажатие inline-кнопки |
| `bot_get_updates` | Polling входящих callback_query |

**Формат кнопок для `bot_send_message` / `bot_edit_message`:**
```json
[
  [{"text": "✅ Да", "callback_data": "yes"}, {"text": "❌ Нет", "callback_data": "no"}],
  [{"text": "Отмена", "callback_data": "cancel"}]
]
```

**`bot_send_voice` — реализация:**
```
text → edge-tts (Microsoft TTS) → ogg-24khz-16bit-mono-opus → sendVoice
```
Формат ogg-opus обязателен — Telegram принимает его как голосовое, а не файл.

---

## Модуль: core

**Статус:** в разработке
**Назначение:** реимплементация Claude Code native tools для OpenClaw mini-bot.
Решает проблему разрыва скоупов: mini-bot получает файловые операции и bash
через MCP вместо того чтобы спавнить полный Claude Code процесс.

| Инструмент | Аналог в Claude Code | Описание |
|------------|----------------------|----------|
| `core_bash` | `Bash` | Выполнить shell-команду, вернуть stdout/stderr |
| `core_process` | — | Управление фоновыми процессами (старт, poll, kill) |
| `core_read` | `Read` | Прочитать файл (с поддержкой offset/limit) |
| `core_write` | `Write` | Создать/перезаписать файл |
| `core_edit` | `Edit` | Exact-string замена в файле |
| `core_patch` | `MultiEdit` | Применить unified-diff патч |
| `core_glob` | `Glob` | Найти файлы по паттерну |
| `core_grep` | `Grep` | Поиск по содержимому файлов (ripgrep) |
| `core_ls` | `LS` | Список файлов в директории |
| `core_web_fetch` | `WebFetch` | Получить содержимое URL (text extraction) |
| `core_web_search` | `WebSearch` | Веб-поиск (Perplexity / Brave API) |
| `core_notebook_read` | `NotebookRead` | Прочитать Jupyter notebook |
| `core_notebook_edit` | `NotebookEdit` | Редактировать ячейку notebook |

**Важно:** `core_bash` выполняет команды от имени пользователя `assistant` на сервере.
Инструмент доступен обоим агентам — безопасность обеспечивается правилами агента, не кодом.

---

## Модуль: browser

**Статус:** в разработке
**Транспорт:** `playwright.async_api` → CDP `ws://127.0.0.1:18800`
**Назначение:**
- Claude Code harness: браузер недоступен нативно → получает через MCP
- OpenClaw mini-bot: дополняет нативный `browser` tool, shared CDP state

```bash
BROWSER_CDP_URL=ws://127.0.0.1:18800
```

| Инструмент | Аналог в OpenClaw | Описание |
|------------|--------------------|----------|
| `browser_navigate` | `browser navigate` | Открыть URL |
| `browser_snapshot` | `browser snapshot` | DOM / accessibility tree страницы |
| `browser_screenshot` | `browser screenshot` | PNG → абс. путь к файлу |
| `browser_click` | `browser click` | Клик по CSS selector или coords |
| `browser_type` | `browser type` | Ввод текста в поле |
| `browser_evaluate` | `browser eval` | Выполнить JS, вернуть результат |
| `browser_get_url` | — | Текущий URL активной вкладки |
| `browser_close` | — | Закрыть текущую вкладку |

**Типичный паттерн:**
```
browser_navigate(url)
→ browser_snapshot()          # посмотреть структуру
→ browser_click(selector)     # нажать кнопку
→ browser_screenshot(path)    # сохранить результат
→ bot_send_photo(chat_id, path)  # отправить пользователю
```

---

## Модуль: sessions

**Статус:** в разработке
**Назначение:** запуск под-агентов и управление сессиями. Аналог OpenClaw `sessions_spawn`.
**Реализация:** вызов claude-code-proxy (`:3458`) для spawn, локальный реестр сессий.

```bash
SESSIONS_PROXY_URL=http://127.0.0.1:3458
```

| Инструмент | Аналог в OpenClaw | Описание |
|------------|-------------------|----------|
| `session_spawn` | `sessions_spawn` | Запустить под-агента с промптом; результат → bot |
| `session_list` | `sessions_list` | Список активных сессий |
| `session_history` | `sessions_history` | Транскрипт сессии |
| `session_send` | `sessions_send` | Отправить сообщение в сессию |
| `session_status` | `session_status` | Статус / отмена сессии |

```python
session_spawn(
    prompt: str,
    chat_id: int | str,        # куда отправить результат (bot_send_message)
    model: str = "claude-haiku-4-5-20251001",
    notify_on_complete: bool = True,
)
```

---

## Модуль: memory

**Статус:** в разработке
**Назначение:** семантический поиск по памяти агента.
**Источник данных:** `~/.openclaw/workspace/memory/` (markdown-файлы)

| Инструмент | Аналог в OpenClaw | Описание |
|------------|-------------------|----------|
| `memory_search` | `memory_search` | Семантический поиск по всей памяти |
| `memory_get` | `memory_get` | Прочитать конкретный файл памяти |
| `memory_write` | — | Записать/обновить файл памяти |

**`memory_search` — реализация:**
TF-IDF или простой grep по markdown-файлам (без внешних vector DB).
При наличии OpenClaw API — делегировать ему.

---

## Модуль: tasks

**Статус:** в разработке
**Назначение:** замена сломанных `TodoWrite`/`TodoRead` в режиме `--print`.
**Хранилище:** `~/.openclaw/workspace/.gateway-tasks.json`

| Инструмент | Аналог в Claude Code | Описание |
|------------|----------------------|----------|
| `task_create` | `TodoWrite` (create) | Создать задачу |
| `task_list` | `TodoRead` | Список задач (фильтр по статусу) |
| `task_update` | `TodoWrite` (update) | Обновить статус / содержание |
| `task_get` | `TodoRead` (single) | Получить задачу по ID |

---

## Модуль: media

**Статус:** планируется
**Назначение:** анализ изображений и PDF, генерация изображений.

| Инструмент | Аналог в OpenClaw | Описание |
|------------|-------------------|----------|
| `media_image_analyze` | `image` | Анализ изображения vision-моделью |
| `media_image_generate` | `image_generate` | Генерация изображения |
| `media_pdf_analyze` | `pdf` | Извлечение текста и анализ PDF |

---

## Модуль: cron

**Статус:** планируется
**Назначение:** управление расписанием задач через OpenClaw Gateway API.

| Инструмент | Аналог в OpenClaw | Описание |
|------------|-------------------|----------|
| `cron_create` | `cron create` | Создать cron job |
| `cron_list` | `cron list` | Список активных jobs |
| `cron_delete` | `cron delete` | Удалить job |
| `cron_wakeup` | `cron wakeup` | Одноразовый delayed wakeup |

---

## Итого по модулям

| Модуль | Инструментов | Приоритет | Статус |
|--------|-------------|-----------|--------|
| `telegram_user` | 52 | 1 — критичный | Перенос из telegram-account-manager |
| `telegram_bot` | 13 | 1 — критичный | Частично готов |
| `core` | 13 | 1 — критичный | В разработке |
| `browser` | 8 | 2 — важный | В разработке |
| `sessions` | 5 | 2 — важный | В разработке |
| `memory` | 3 | 2 — важный | В разработке |
| `tasks` | 4 | 3 — расширение | Планируется |
| `cron` | 4 | 3 — расширение | Планируется |
| `media` | 3 | 3 — расширение | Планируется |
| **Итого** | **~105** | | |
