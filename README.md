# MCP-Gateway

Модульный MCP-сервер (Model Context Protocol) для AI-агентов на базе Claude Code CLI.
Предоставляет доступ к Telegram (user account + bot) и другим сервисам через единую точку подключения.

---

## Назначение

**Проблема:** Claude Code harness поддерживает только MCP-инструменты. Нативные инструменты OpenClaw (отправка сообщений с кнопками, файлов через бота) в этой среде недоступны. Существующий `telegram-account-manager` работает через личный аккаунт пользователя — агенту запрещено отправлять сообщения от его имени.

**Решение:** единый MCP-шлюз с модульной архитектурой:
- `telegram_user` — чтение/мониторинг через Pyrogram (личный аккаунт, только чтение)
- `telegram_bot` — отправка сообщений с inline-кнопками и файлов через Telegram Bot API
- `openclaw` — будущие нативные интеграции

---

## Архитектура

```
Claude Code CLI / OpenClaw
        │
        │  MCP/HTTP
        ▼
  MCP-Gateway  :8200
  ┌────────────────────────────────────┐
  │  telegram_user  │  telegram_bot    │
  │  tg_*           │  bot_*           │
  │  (Pyrogram)     │  (Bot API/httpx) │
  └────────────────────────────────────┘
        │                   │
        ▼                   ▼
  Telegram User API   Telegram Bot API
```

---

## Инструменты

### telegram_user (tg_*)

Унаследованы из `telegram-account-manager`. Только для чтения и мониторинга.

| Группа | Инструменты |
|--------|------------|
| Сессия | `tg_session_status`, `tg_create_session` |
| Аккаунт | `tg_get_me`, `tg_get_user` |
| Сообщения | `tg_get_messages`, `tg_search_messages`, `tg_get_pending_messages` |
| Чаты | `tg_get_dialogs`, `tg_get_chat`, `tg_get_chat_members` |
| Медиа | `tg_download_media`, `tg_get_file_info` |

### telegram_bot (bot_*)

Отправка от имени бота — основной канал агента для ответов пользователю.

| Инструмент | Описание |
|------------|----------|
| `bot_send_message` | Текст с поддержкой inline-кнопок |
| `bot_send_document` | Отправка файла |
| `bot_send_photo` | Отправка фото |
| `bot_answer_callback` | Ответ на нажатие кнопки |
| `bot_edit_message` | Редактирование отправленного сообщения |

---

## Быстрый старт (разработка)

```bash
git clone https://github.com/alexanderbrownemail-create/mcp-gateway
cd mcp-gateway
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Настроить переменные
cp .env.example ~/.env
# Заполнить TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN ...

python -m mcp_gateway
```

---

## Конфигурация

`config.yml` в корне проекта:

```yaml
modules:
  telegram_user:
    enabled: true
  telegram_bot:
    enabled: true
  openclaw:
    enabled: false
```

Переменные окружения (`~/.env`):

```bash
GATEWAY_PORT=8200
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_PHONE=...
TELEGRAM_BOT_TOKEN=...
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
git pull
pip install -e . --user
systemctl --user restart mcp-gateway
journalctl --user -u mcp-gateway -f
```

---

## Связанные репозитории

- [ansible-openclaw-assistant](https://github.com/alexanderbrownemail-create/ansible-openclaw-assistant) — Ansible деплой
- [claude-code-proxy](https://github.com/alexanderbrownemail-create/claude-code-proxy) — OpenAI API прокси
- [telegram-account-manager](https://github.com/alexanderbrownemail-create/telegram-account-manager) — устаревший (код переедет сюда)
- [tasks](https://github.com/alexanderbrownemail-create/tasks/issues) — таск-трекер
