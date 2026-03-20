# CLAUDE.md — mcp-gateway

Инструкции для AI-ассистента, работающего над этим репозиторием.

## Цель проекта

**MCP-Gateway** — модульный MCP-сервер (Model Context Protocol), предоставляющий AI-агентам
(Claude Code CLI, OpenClaw) доступ к внешним сервисам через единую точку подключения.

Ключевые принципы:
- **Один MCP-сервер** — одна запись в `~/.claude.json`, один systemd-сервис
- **Плагин-архитектура** — модули подключаются/отключаются через `config.yml` или env vars
- **Разделение транспортов** — telegram_user (Pyrogram/MTProto), telegram_bot (Bot API)
- Все секреты в `~/.env`, никогда в коде или git
- Python 3.11+, FastMCP, pydantic-settings

---

## Работа с удалённым хостом

**Для работы на удалённом сервере необходимо подключаться через локальную tmux-сессию в WSL.**

```bash
# Запустить WSL и подключиться через tmux
wsl -d Ubuntu-22.04
tmux new-session -A -s gateway   # создать или подключиться к сессии
ssh assistant@94.183.188.104
```

Почему именно так:
- systemd user services требуют активной сессии или lingering
- SSH без tmux: при разрыве соединения все фоновые процессы погибают
- tmux сохраняет контекст между сессиями (логи, незавершённые команды)

**Не запускать команды на сервере через одиночный `ssh ... 'command'`** для длительных операций.
Для разовых проверок одиночный ssh допустим.

---

## Сервер

| Параметр | Значение |
|----------|----------|
| Хост | `94.183.188.104` |
| Пользователь | `assistant` |
| Репо на сервере | `~/automations/mcp-gateway/` |
| Сервис | `mcp-gateway.service` (systemd user) |
| Порт | `8200` |
| Конфиг MCP | `~/.claude.json` → `"gateway": { "type": "http", "url": "http://127.0.0.1:8200/mcp" }` |
| Python | `/usr/bin/python3` (3.12), установлен через `pip install -e .` |
| Env-файл | `~/.env` |

### Управление сервисом

```bash
systemctl --user status mcp-gateway
systemctl --user restart mcp-gateway
journalctl --user -u mcp-gateway -f
```

### Установка / обновление

```bash
cd ~/automations/mcp-gateway
git pull
pip install -e . --user
systemctl --user restart mcp-gateway
```

---

## Архитектура

```
Claude Code harness
  ~/.claude.json: "gateway" → http://127.0.0.1:8200/mcp
        │
        ▼
  MCP-Gateway (FastMCP, порт 8200)
  ┌──────────────────────────────────┐
  │         Module Registry          │
  │  (конфиг: config.yml / env vars) │
  └──┬──────────────┬────────────────┘
     │              │
     ▼              ▼
telegram_user   telegram_bot      openclaw (будущее)
(Pyrogram)      (Bot API)
tg_*            bot_*
     │              │
     ▼              ▼
Telegram        Telegram
User API        Bot API
```

### Модули

| Модуль | Префикс инструментов | Транспорт | Назначение |
|--------|----------------------|-----------|------------|
| `telegram_user` | `tg_*` | Pyrogram → MTProto | Чтение/мониторинг личного аккаунта |
| `telegram_bot` | `bot_*` | httpx → Bot API | Отправка сообщений с кнопками, файлов |
| `openclaw` | `oc_*` | — | Будущее: нативные инструменты OpenClaw |

**Важно:** `tg_*` (user account) **не используются для отправки сообщений агентом** —
это запрещено правилами. Отправка идёт только через `bot_*`.

---

## Структура репозитория

```
mcp-gateway/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── config.yml                  ← включить/отключить модули
├── src/
│   └── mcp_gateway/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py              ← FastMCP + загрузка модулей
│       ├── config.py           ← Settings (pydantic-settings)
│       ├── registry.py         ← Module Registry
│       └── modules/
│           ├── base.py         ← BaseModule (интерфейс)
│           ├── telegram_user/  ← перенесён из telegram-account-manager
│           │   ├── __init__.py
│           │   ├── client.py
│           │   ├── config.py
│           │   ├── services/
│           │   └── tools.py
│           ├── telegram_bot/
│           │   ├── __init__.py
│           │   ├── client.py   ← httpx Bot API client
│           │   ├── config.py
│           │   └── tools.py
│           └── openclaw/
│               └── __init__.py
└── tests/
    ├── unit/
    └── integration/
```

---

## Конфигурация

### config.yml

```yaml
modules:
  telegram_user:
    enabled: true
  telegram_bot:
    enabled: true
  openclaw:
    enabled: false
```

### Переменные окружения (`~/.env`)

```bash
# Общий Gateway
GATEWAY_HOST=127.0.0.1
GATEWAY_PORT=8200
GATEWAY_LOG_LEVEL=INFO

# Модуль telegram_user (Pyrogram)
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_PHONE=...
TG_MANAGER_SESSION_DIR=~/.telegram-sessions

# Модуль telegram_bot (Bot API)
TELEGRAM_BOT_TOKEN=...
```

### Регистрация в OpenClaw

В `~/.claude.json`:
```json
{
  "mcpServers": {
    "gateway": {
      "type": "http",
      "url": "http://127.0.0.1:8200/mcp"
    }
  }
}
```

**Только одна запись.** Старую запись `"telegram"` удалить после перехода.

---

## Инструменты модуля telegram_bot

### bot_send_message

```python
bot_send_message(
    chat_id: int | str,
    text: str,
    parse_mode: str = "markdown",         # "markdown" | "html" | "disabled"
    buttons: list[list[dict]] | None = None,  # inline keyboard
    reply_to_message_id: int | None = None,
)
```

`buttons` — двумерный массив (строки × кнопки):
```json
[
  [{"text": "Да", "callback_data": "yes"}, {"text": "Нет", "callback_data": "no"}],
  [{"text": "Отмена", "callback_data": "cancel"}]
]
```

### bot_send_document

```python
bot_send_document(
    chat_id: int | str,
    file_path: str,          # абсолютный путь на сервере
    caption: str | None = None,
    parse_mode: str = "markdown",
)
```

### bot_send_photo

```python
bot_send_photo(
    chat_id: int | str,
    file_path: str,
    caption: str | None = None,
    parse_mode: str = "markdown",
)
```

---

## Деплой через Ansible

Роль `mcp-gateway` в репозитории [ansible-openclaw-assistant](https://github.com/alexanderbrownemail-create/ansible-openclaw-assistant).

```bash
ansible-playbook site.yml --tags mcp-gateway
```

Роль выполняет:
- клонирование репо в `~/automations/mcp-gateway/`
- создание virtualenv, `pip install -e .`
- деплой `~/.env` из Ansible Vault
- регистрацию и запуск `mcp-gateway.service` (systemd user)
- обновление `~/.claude.json`: замена `"telegram"` на `"gateway"`

---

## Gitflow

- `main` — стабильная ветка, только через PR
- `develop` — интеграционная ветка
- `feature/*` — разработка модулей и фич

PR: `feature/* → develop → main`.

**Никогда не коммитить:**
- `~/.env`, `.env` с реальными токенами
- Pyrogram session-файлы (`*.session`)
- Любые файлы с токенами в открытом виде

---

## Связанные репозитории

| Репо | Назначение |
|------|-----------|
| [ansible-openclaw-assistant](https://github.com/alexanderbrownemail-create/ansible-openclaw-assistant) | Ansible деплой всей инфраструктуры |
| [claude-code-proxy](https://github.com/alexanderbrownemail-create/claude-code-proxy) | OpenAI Responses API → Claude Code CLI прокси |
| [telegram-account-manager](https://github.com/alexanderbrownemail-create/telegram-account-manager) | Устаревший: код telegram_user модуля переедет сюда |
| [openclaw-memory](https://github.com/alexanderbrownemail-create/openclaw-memory) | Синхронизация памяти агента |
| [tasks](https://github.com/alexanderbrownemail-create/tasks/issues) | Таск-трекер проекта |

---

## Что не делать

- **Не отправлять сообщения через `tg_*`** — это личный аккаунт пользователя (запрещено)
- **Не хардкодить токены** — только через `~/.env` и pydantic-settings
- **Не создавать отдельные MCP-серверы** для новых интеграций — расширять модулями
- **Не менять порт 8200** без обновления `~/.claude.json` и ansible vars
- **Не запускать долгие операции на сервере без tmux** — сессия оборвётся
