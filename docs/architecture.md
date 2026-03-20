# Архитектура MCP-Gateway

## Концепция: универсальный инструментальный слой

MCP-Gateway решает проблему **разрыва скоупов** между агентами.

Оба агента работают на одном сервере, но имеют разные наборы нативных инструментов:

| | Claude Code harness | OpenClaw mini-bot |
|--|---------------------|-------------------|
| Файловые операции (Read/Write/Edit/Bash) | ✓ нативно | ✗ другой скоуп |
| Отправка сообщений через бота с кнопками | ✗ | ✓ нативно (`message`) |
| Браузер (CDP :18800) | ✗ | ✓ нативно (`browser`) |
| Сессии / под-агенты | ✓ (`Agent`) | ✓ (`sessions_spawn`) |
| TodoWrite/TodoRead | ✗ сломан в `--print` | ✓ |

**MCP-Gateway — общий слой, через который каждый агент получает то, чего ему не хватает нативно.**

```
Claude Code harness                              OpenClaw mini-bot
(subprocess: claude --print)                     (native OpenClaw session)
        │                                                │
        │                                                │
        │  нет бота, нет браузера                        │  нет файловых ops,
        │  TodoWrite сломан                              │  нет TodoWrite
        │                                                │
        └──────────────┐          ┌─────────────────────┘
                       │          │
                       ▼          ▼
              ┌──────────────────────────────────────────────┐
              │               MCP-Gateway  :8200             │
              │                                              │
              │  telegram_user   telegram_bot   core         │
              │  tg_*            bot_*          core_*       │
              │                                              │
              │  browser         sessions        memory      │
              │  browser_*       session_*       memory_*    │
              │                                              │
              │  tasks           media           cron        │
              │  task_*          media_*         cron_*      │
              └──────────────────────────────────────────────┘
                       │          │          │
                       ▼          ▼          ▼
                  Telegram    Filesystem   Chrome
                  Bot API     (server)     CDP :18800
```

### Что получает каждый агент через MCP

```
Claude Code harness → MCP:
  bot_*        — отправка сообщений, кнопки, файлы, голос
  browser_*    — браузер (нет нативно)
  session_*    — spawn под-агентов с передачей результата в TG
  task_*       — замена сломанных TodoWrite/TodoRead
  memory_*     — семантический поиск по памяти
  cron_*       — управление расписанием
  media_*      — анализ изображений и PDF
  tg_*         — чтение/мониторинг Telegram

OpenClaw mini-bot → MCP:
  core_*       — файловые операции, bash, web (Claude Code scope)
  task_*       — единый таск-менеджер
  memory_*     — семантический поиск
  tg_*         — мониторинг Telegram (дополняет нативный message)
  browser_*    — тот же Chrome, но через MCP (shared state)
  session_*    — дополняет нативный sessions_spawn
```

---

## Полная карта модулей

### Приоритет 1 — критичные (блокируют работу агента)

```
telegram_user/    52 инструмента (tg_*)
  Источник: перенос из telegram-account-manager
  Транспорт: Pyrogram → MTProto → User Account

telegram_bot/     13 инструментов (bot_*)
  Источник: новая реализация
  Транспорт: httpx → Telegram Bot API
  Статус: частично готов (module.py)

core/             14 инструментов (core_*)
  Источник: реимплементация Claude Code native tools
  Назначение: файловые операции и bash для OpenClaw mini-bot
```

### Приоритет 2 — важные

```
browser/          8 инструментов (browser_*)
  Транспорт: playwright.async_api → CDP ws://127.0.0.1:18800
  Доступен обоим агентам: Claude Code (нет нативного),
  OpenClaw (есть нативный, но shared MCP state полезен)

sessions/         5 инструментов (session_*)
  Spawn под-агентов через claude-code-proxy :3458
  Управление жизненным циклом сессий

memory/           3 инструмента (memory_*)
  Семантический поиск: индекс ~/.openclaw/workspace/memory/
  memory_search, memory_get, memory_write
```

### Приоритет 3 — расширение

```
tasks/            4 инструмента (task_*)
  Замена сломанных TodoWrite/TodoRead в --print режиме
  Персистентный JSON-файл задач

cron/             4 инструмента (cron_*)
  Управление расписанием через OpenClaw Gateway API
  cron_create, cron_list, cron_delete, cron_wakeup

media/            3 инструмента (media_*)
  image_analyze, image_generate, pdf_analyze
```

---

## Жизненный цикл модуля

```python
class BaseModule:
    name: str

    async def startup(self) -> None:
        # инициализация: подключения, сессии, background tasks

    def register_tools(self, mcp: FastMCP) -> None:
        # регистрация @mcp.tool() — вызывается один раз при старте

    async def shutdown(self) -> None:
        # graceful stop: закрыть соединения, остановить tasks
```

`registry.py` при старте:
1. Читает `config.yml`
2. Импортирует включённые модули
3. `module.startup()` — инициализация
4. `module.register_tools(mcp)` — регистрация инструментов

---

## Почему не отдельные MCP-серверы

| Критерий | Отдельные серверы | MCP-Gateway |
|----------|-------------------|-------------|
| Записей в `~/.claude.json` | N | 1 |
| systemd сервисов | N | 1 |
| Добавить модуль | новый репо + деплой + регистрация | файл в `modules/` + строка в `config.yml` |
| Общий контекст (сессия, rate limit, CDP) | нет | да |
| Shared browser state | нет | да |

---

## Миграция с telegram-account-manager

1. Код `telegram_account_manager/` → `mcp_gateway/modules/telegram_user/`
2. В `~/.claude.json`: `"telegram"` → `"gateway"` (порт тот же: 8200)
3. `telegram-account-manager.service` → `mcp-gateway.service` (disable старый)
4. Репо `telegram-account-manager` архивируется на GitHub
