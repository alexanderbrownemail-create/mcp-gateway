# MCP-Gateway

Модульный MCP-сервер (Model Context Protocol) — шлюз между AI-агентами и внешними сервисами.
Решает проблему разрыва скоупов: Claude Code harness и OpenClaw mini-bot получают через MCP
то, что им недоступно нативно.

**99 инструментов** в 9 модулях.

---

## Концепция

```
Claude Code harness                OpenClaw mini-bot
(Read/Write/Edit/Bash нативно)     (browser/sessions нативно)
        │                                  │
        │            MCP/HTTP              │
        └──────────────┬───────────────────┘
                       ▼
              MCP-Gateway  :8200
        ┌──────────────────────────────────────────────┐
        │  telegram_bot   telegram_user   core          │
        │  browser        sessions        memory        │
        │  tasks          cron            media         │
        └──────────────────────────────────────────────┘
```

**Claude Code harness** получает через MCP: `bot_*`, `tg_*`, `browser_*`, `session_*`, `memory_*`
**OpenClaw mini-bot** получает через MCP: `core_*` (bash/read/write/edit — нативных нет)
**Оба агента** используют: `task_*`, `cron_*`, `media_*`

---

## Инструменты

### telegram_bot (13 инструментов)

Отправка от имени Telegram-бота — основной канал ответов агента пользователю.
Транспорт: `httpx` → Telegram Bot API.

| Инструмент | Что делает |
|---|---|
| `bot_send_message` | Отправить текстовое сообщение. Поддерживает Markdown/HTML и inline-клавиатуру `[[ {text, callback_data} ]]`. Агент использует для всех ответов пользователю. |
| `bot_send_document` | Отправить файл с диска сервера. Принимает абсолютный путь, передаёт через multipart upload. |
| `bot_send_photo` | Отправить изображение с диска сервера. Аналогично `bot_send_document`, но как фото. |
| `bot_send_video` | Отправить видеофайл с диска сервера. |
| `bot_send_voice` | Синтезировать речь (edge-tts) и отправить голосовым сообщением. Формат ogg-24khz-16bit-mono-opus — единственный, который Telegram принимает как voice, а не файл. |
| `bot_send_sticker` | Отправить стикер по Telegram file_id (получить из входящего сообщения). |
| `bot_forward_message` | Переслать существующее сообщение из одного чата в другой. |
| `bot_edit_message` | Изменить текст и/или inline-клавиатуру уже отправленного сообщения. |
| `bot_delete_message` | Удалить сообщение бота из чата. |
| `bot_pin_message` | Закрепить сообщение в чате. По умолчанию без уведомления. |
| `bot_unpin_message` | Открепить сообщение. |
| `bot_answer_callback` | Ответить на нажатие inline-кнопки (обязательно в течение 10 сек). Можно показать тост или alert-попап. |
| `bot_set_typing` | Отправить индикатор действия: `typing`, `upload_document`, `upload_photo`, `upload_video`, `record_voice`, `playing`. |
| `bot_get_updates` | Polling входящих обновлений (callback_query, сообщения). Каждый вызов подтверждает все update с id < offset. |

---

### telegram_user (50 инструментов)

Работа с Telegram через личный аккаунт (Pyrogram/MTProto).
Для отправки — только в группы/каналы/избранное, **не пользователю бота**.
Транспорт: `pyrogram` → Telegram MTProto.

#### Сессия и аккаунт

| Инструмент | Что делает |
|---|---|
| `tg_session_status` | Проверить, подключён ли Pyrogram-клиент. Возвращает `{connected, username, phone}`. |
| `tg_get_me` | Полный профиль текущего аккаунта: id, имя, username, телефон. |
| `tg_get_user` | Профиль пользователя по ID или @username. |
| `tg_get_contacts` | Список всех контактов аккаунта. |
| `tg_search_contacts` | Поиск по имени/username среди контактов. |
| `tg_get_user_status` | Online-статус пользователя: `online`, `recently`, `last_week`, `long_ago`. |

#### Сообщения

| Инструмент | Что делает |
|---|---|
| `tg_get_messages` | Последние N сообщений чата с пагинацией по offset_id. |
| `tg_search_messages` | Поиск сообщений по тексту внутри чата. |
| `tg_get_pending_messages` | Непрочитанные входящие из всех диалогов. Удобно для поллинга новых событий. |
| `tg_get_read_status` | Количество непрочитанных в конкретном чате. |

#### Диалоги и чаты

| Инструмент | Что делает |
|---|---|
| `tg_get_dialogs` | Список диалогов с количеством непрочитанных и последним сообщением. |
| `tg_get_chat` | Информация о чате/группе/канале: тип, название, username, число участников, описание. |
| `tg_get_chat_members` | Список участников группы со статусами (member/admin/creator). |

#### Медиафайлы

| Инструмент | Что делает |
|---|---|
| `tg_download_media` | Скачать медиафайл из сообщения по ID на диск сервера. |

#### Отправка (только в чужие чаты)

| Инструмент | Что делает |
|---|---|
| `tg_send_message` | Отправить текст от аккаунта. Для групп, каналов, избранного — но не пользователю бота. |
| `tg_send_photo` | Отправить фото с диска сервера. |
| `tg_send_document` | Отправить документ с диска сервера. |
| `tg_send_video` | Отправить видео с диска сервера. |
| `tg_send_voice` | Отправить готовый ogg/mp3-файл как голосовое. |
| `tg_send_sticker` | Отправить стикер по file_id или пути к .webp. |
| `tg_forward_messages` | Переслать несколько сообщений из одного чата в другой. |
| `tg_edit_message` | Редактировать отправленное сообщение аккаунта. |
| `tg_delete_messages` | Удалить несколько сообщений по списку ID. |
| `tg_set_reaction` | Поставить emoji-реакцию на сообщение. |
| `tg_pin_message` | Закрепить сообщение в чате. |
| `tg_unpin_message` | Открепить сообщение. |
| `tg_read_chat_history` | Отметить чат прочитанным (сбросить счётчик непрочитанных). |
| `tg_send_chat_action` | Показать индикатор действия: печатает, загружает файл и т.д. |

#### Управление чатами

| Инструмент | Что делает |
|---|---|
| `tg_join_chat` | Вступить в публичный чат или канал по @username или invite-ссылке. |
| `tg_leave_chat` | Покинуть чат или группу. |
| `tg_create_group` | Создать новую группу с указанными участниками. |
| `tg_set_chat_title` | Изменить название чата (нужны права администратора). |
| `tg_set_chat_description` | Изменить описание чата. |
| `tg_set_chat_photo` | Установить фото чата из файла на сервере. |

#### Управление участниками

| Инструмент | Что делает |
|---|---|
| `tg_ban_chat_member` | Заблокировать участника. Опционально — до указанной даты. |
| `tg_kick_chat_member` | Выкинуть без блокировки (ban + немедленный unban). |
| `tg_unban_chat_member` | Разблокировать участника. |
| `tg_promote_chat_member` | Назначить администратором с тонкой настройкой прав. |
| `tg_demote_chat_member` | Снять все права администратора. |

#### Запланированные сообщения

| Инструмент | Что делает |
|---|---|
| `tg_schedule_message` | Запланировать отправку сообщения на Unix-timestamp. Telegram сам отправит в указанное время. |
| `tg_list_scheduled` | Список запланированных сообщений в чате. |
| `tg_cancel_scheduled` | Отменить запланированное сообщение по ID. |

#### Автоответы

| Инструмент | Что делает |
|---|---|
| `tg_set_auto_reply` | Создать правило: если входящее сообщение содержит keyword (regex), ответить заданным текстом. Хранится в `~/.mcp-gateway/tg_user_state.json`. |
| `tg_list_auto_replies` | Список всех активных правил автоответа. |
| `tg_remove_auto_reply` | Удалить правило автоответа по ID. |

#### Шаблоны сообщений

| Инструмент | Что делает |
|---|---|
| `tg_create_template` | Создать именованный шаблон с подстановками `{placeholder}`. |
| `tg_list_templates` | Список всех шаблонов. |
| `tg_delete_template` | Удалить шаблон. |
| `tg_send_template` | Отправить сообщение по шаблону с подстановкой переменных. |
| `tg_send_bulk` | Разослать одно сообщение по списку чатов с задержкой между отправками (минимум 0.5 сек). |

---

### core (9 инструментов)

Реимплементация нативных инструментов Claude Code для OpenClaw mini-bot.
OpenClaw не имеет нативных Read/Write/Edit/Bash — получает их через MCP.

| Инструмент | Аналог CC | Что делает |
|---|---|---|
| `core_bash` | `Bash` | Выполнить shell-команду через `asyncio.create_subprocess_shell`. Поддерживает таймаут и рабочую директорию. Возвращает `{stdout, stderr, exit_code, timed_out}`. |
| `core_read` | `Read` | Прочитать файл с нумерацией строк. Поддерживает `offset` и `limit` для чтения фрагментов. |
| `core_write` | `Write` | Создать или перезаписать файл. Автоматически создаёт родительские директории. |
| `core_edit` | `Edit` | Заменить строку в файле (exact-string replacement). Проверяет уникальность совпадения, поддерживает `replace_all`. |
| `core_glob` | `Glob` | Найти файлы по glob-паттерну (`**/*.py`). Результат отсортирован по дате изменения (новейшие первые). |
| `core_grep` | `Grep` | Поиск по содержимому файлов. Использует `rg` (ripgrep), при отсутствии — Python-fallback. Поддерживает regex, glob-фильтр, контекст, режимы `content`/`files`/`count`. |
| `core_ls` | `LS` | Список файлов директории с метаданными: тип, размер, дата изменения. |
| `core_web_fetch` | `WebFetch` | Получить содержимое URL через httpx. HTML конвертируется в plain text (теги удаляются). |
| `core_web_search` | `WebSearch` | Веб-поиск через Brave Search API. Требует `BRAVE_API_KEY`. Возвращает `[{title, url, description}]`. |

---

### browser (8 инструментов)

Управление браузером через Playwright CDP.
Подключается к уже запущенному Chrome (OpenClaw держит его на порту 18800).
Claude Code harness не имеет нативного браузера — получает его через этот модуль.

| Инструмент | Что делает |
|---|---|
| `browser_navigate` | Открыть URL в активной вкладке. Поддерживает `wait_until`: `load`, `domcontentloaded`, `networkidle`. |
| `browser_snapshot` | Получить accessibility tree страницы — структурированное текстовое представление интерактивных элементов. Аналог «что видит скринридер». |
| `browser_screenshot` | Сохранить скриншот в PNG-файл. Опция `full_page` захватывает всю страницу, не только viewport. |
| `browser_click` | Кликнуть по элементу по CSS-селектору. Ждёт появления элемента до таймаута. |
| `browser_type` | Ввести текст в поле ввода. Опция `clear_first` сначала очищает поле. |
| `browser_evaluate` | Выполнить произвольный JavaScript в контексте страницы. Возвращает результат как JSON-строку. |
| `browser_get_url` | Получить текущий URL и заголовок активной вкладки. |
| `browser_close` | Закрыть текущую вкладку. Chrome при этом не завершается. |

**Типичный паттерн:**
```
browser_navigate → browser_snapshot → browser_click → browser_screenshot → bot_send_photo
```

---

### sessions (5 инструментов)

Запуск и управление под-агентами через claude-code-proxy `:3458`.
Аналог OpenClaw `sessions_spawn` для Claude Code harness.

| Инструмент | Что делает |
|---|---|
| `session_spawn` | Запустить под-агента с заданным промптом. Вызывает `/v1/chat/completions` на claude-code-proxy. Опционально уведомляет пользователя в Telegram по завершении. |
| `session_list` | Список всех запущенных сессий с их статусами. |
| `session_history` | Транскрипт сессии: промпт пользователя и ответ агента. |
| `session_send` | Отправить дополнительное сообщение в сессию. Передаёт полный контекст (промпт + предыдущий ответ + новое сообщение). |
| `session_status` | Статус конкретной сессии: `running`, `completed`, `failed`, `cancelled`. |

---

### memory (3 инструмента)

Семантический поиск и управление файлами памяти агента.
Работает с markdown-файлами в `~/.openclaw/workspace/memory/`.

| Инструмент | Что делает |
|---|---|
| `memory_search` | Поиск по всем markdown-файлам памяти. TF-IDF по ключевым словам: считает вхождения каждого слова запроса, ранжирует по суммарному score. Возвращает путь к файлу, score и excerpt вокруг первого совпадения. |
| `memory_get` | Прочитать конкретный файл памяти по относительному пути. Защита от path traversal — нельзя выйти за пределы директории памяти. |
| `memory_write` | Записать или обновить файл памяти. Создаёт поддиректории автоматически. |

---

### tasks (4 инструмента)

Персистентный трекер задач агента.
Замена сломанных `TodoWrite`/`TodoRead` в режиме `claude --print` (CC issue #7523, #5332).
Хранилище: `~/.mcp-gateway/tasks.json`.

| Инструмент | Что делает |
|---|---|
| `task_create` | Создать задачу с названием, описанием и приоритетом (`high`/`medium`/`low`). Возвращает короткий ID (8 символов UUID). |
| `task_update` | Обновить статус, название, описание или приоритет задачи. Статусы: `pending` → `in_progress` → `completed`/`cancelled`. |
| `task_list` | Список задач с фильтрами по статусу и приоритету. Сортировка: сначала high, затем по дате создания. |
| `task_delete` | Удалить задачу по ID. |

---

### cron (4 инструмента)

Планировщик задач по расписанию.
Фоновый asyncio-цикл проверяет расписание каждую минуту и вызывает указанный MCP-инструмент.

| Инструмент | Что делает |
|---|---|
| `cron_create` | Создать задачу по расписанию. Принимает стандартное cron-выражение (5 полей) и имя MCP-инструмента для вызова с аргументами. Пример: `*/5 * * * *` → `bot_send_message` каждые 5 минут. |
| `cron_list` | Список всех задач с расписанием, статусом, временем последнего запуска и счётчиком запусков. |
| `cron_pause` | Приостановить задачу (статус `paused`). Не удаляет, можно возобновить через `cron_create` с тем же расписанием. |
| `cron_delete` | Удалить задачу планировщика. |

**Поддерживаемый синтаксис cron:** `*`, числа, диапазоны `1-5`, шаги `*/5`, списки `1,3,5`.

---

### media (3 инструмента)

Конвертация и обработка медиафайлов на сервере.

| Инструмент | Что делает |
|---|---|
| `media_tts` | Синтез речи через edge-tts. Принимает текст и голос (например `ru-RU-SvetlanaNeural`). Формат `ogg` — готов для `bot_send_voice` или `tg_send_voice`. |
| `media_image_info` | Получить метаданные изображения: формат, ширина, высота, цветовой режим, размер файла. Использует Pillow. |
| `media_convert_image` | Конвертировать и/или изменить размер изображения. Поддерживает пропорциональное масштабирование (задать только ширину или только высоту). Сохраняет в любой формат, который поддерживает Pillow. |

---

## Быстрый старт

```bash
git clone https://github.com/alexanderbrownemail-create/mcp-gateway
cd mcp-gateway
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Переменные окружения (`~/.env`):

```bash
GATEWAY_HOST=127.0.0.1
GATEWAY_PORT=8200
GATEWAY_LOG_LEVEL=INFO
GATEWAY_CONFIG_FILE=config.yml

# telegram_bot
TELEGRAM_BOT_TOKEN=...

# telegram_user
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_PHONE=...
TG_MANAGER_SESSION_DIR=~/.telegram-sessions

# browser
BROWSER_CDP_URL=ws://127.0.0.1:18800

# sessions
SESSIONS_PROXY_URL=http://127.0.0.1:3458

# core (web_search, опционально)
BRAVE_API_KEY=...
```

Конфигурация модулей (`config.yml`):

```yaml
modules:
  telegram_bot:
    enabled: true
  telegram_user:
    enabled: true
  core:
    enabled: true
  browser:
    enabled: true
  sessions:
    enabled: true
  memory:
    enabled: true
  tasks:
    enabled: false
  cron:
    enabled: false
  media:
    enabled: false
```

Запуск:

```bash
python -m mcp_gateway
```

---

## Деплой

Через Ansible (роль `mcp-gateway` в [ansible-openclaw-assistant](https://github.com/alexanderbrownemail-create/ansible-openclaw-assistant)):

```bash
ansible-playbook site.yml --tags mcp-gateway
```

Вручную:

```bash
cd ~/automations/mcp-gateway
git pull && pip install -e .
systemctl --user restart mcp-gateway
journalctl --user -u mcp-gateway -f
```

---

## Связанные репозитории

- [ansible-openclaw-assistant](https://github.com/alexanderbrownemail-create/ansible-openclaw-assistant) — Ansible деплой всего стека
- [claude-code-proxy](https://github.com/alexanderbrownemail-create/claude-code-proxy) — OpenAI API прокси (sessions module target)
- [tasks](https://github.com/alexanderbrownemail-create/tasks/issues/15) — техдолг и решения по проекту
