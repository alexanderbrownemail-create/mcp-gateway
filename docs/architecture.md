# Архитектура MCP-Gateway

## Контекст

AI-агент (OpenClaw + Claude Code CLI) работает через **Claude Code harness**.
В этой среде доступны только MCP-инструменты — нативные инструменты OpenClaw
(отправка сообщений через бота, inline-кнопки) **не инжектируются**.

Существующий `telegram-account-manager` работает через Pyrogram (MTProto, личный
аккаунт пользователя). Агенту **запрещено** отправлять сообщения от имени личного аккаунта.

## Решение: модульный шлюз

```
Claude Code CLI (агент)
        │
        │  MCP/HTTP POST /mcp
        ▼
┌───────────────────────────────────────────────────────────────┐
│                        MCP-Gateway                            │
│                     FastMCP · :8200                           │
│                                                               │
│  ┌──────────────────┐      ┌──────────────────────────────┐   │
│  │  Module Registry │      │         config.yml           │   │
│  │  загружает модули│◄─────│  modules.telegram_user: true │   │
│  │  при старте      │      │  modules.telegram_bot: true  │   │
│  └────────┬─────────┘      └──────────────────────────────┘   │
│           │                                                   │
│    ┌──────┴──────┐                                            │
│    │             │                                            │
│    ▼             ▼                                            │
│  ┌──────────┐  ┌────────────────────────┐                    │
│  │telegram  │  │     telegram_bot       │                    │
│  │_user     │  │                        │                    │
│  │          │  │  bot_send_message()    │                    │
│  │tg_get_   │  │    + inline_keyboard   │                    │
│  │messages()│  │  bot_send_document()   │                    │
│  │tg_get_   │  │  bot_send_photo()      │                    │
│  │dialogs() │  │  bot_answer_callback() │                    │
│  │tg_down-  │  │  bot_edit_message()    │                    │
│  │load_     │  │                        │                    │
│  │media()   │  │  httpx → Bot API       │                    │
│  │...       │  │  api.telegram.org      │                    │
│  │          │  └────────────┬───────────┘                    │
│  │Pyrogram  │               │ HTTPS                          │
│  │MTProto   │               ▼                                │
│  └────┬─────┘         Telegram Bot API                       │
│       │ MTProto        (отправка от бота)                    │
│       ▼                                                       │
│  Telegram User API                                           │
│  (чтение/мониторинг)                                         │
└───────────────────────────────────────────────────────────────┘
```

## Поток инструментов

### Отправить сообщение с кнопками

```
Агент вызывает: bot_send_message(chat_id=..., text="...", buttons=[[...]])
    │
    ▼
telegram_bot/tools.py → BotClient.send_message()
    │
    ▼
POST https://api.telegram.org/bot<TOKEN>/sendMessage
{
  "chat_id": ...,
  "text": "...",
  "reply_markup": {"inline_keyboard": [[...]]}
}
    │
    ▼
Telegram доставляет пользователю сообщение с кнопками
```

### Получить входящие сообщения

```
Агент вызывает: tg_get_pending_messages()
    │
    ▼
telegram_user/tools.py → MonitoringService.get_pending_messages()
    │
    ▼
Возвращает очередь сообщений, накопленных Pyrogram background handler
```

## Жизненный цикл модуля

```python
class BaseModule:
    async def startup(self) -> None: ...   # инициализация (подключение к TG и т.п.)
    def register_tools(self, mcp: FastMCP) -> None: ...  # регистрация @mcp.tool()
    async def shutdown(self) -> None: ...  # graceful stop
```

`registry.py` при старте:
1. Читает `config.yml`
2. Импортирует включённые модули
3. Вызывает `module.startup()`
4. Вызывает `module.register_tools(mcp)`

## Почему не отдельные MCP-серверы

| Критерий | Отдельные серверы | MCP-Gateway |
|----------|-------------------|-------------|
| Записей в `~/.claude.json` | N | 1 |
| systemd сервисов | N | 1 |
| Добавить новый модуль | новый репо + деплой + регистрация | файл в `modules/` + `config.yml` |
| Общий контекст (сессия, rate limit) | нет | да |

## Миграция с telegram-account-manager

1. Код `telegram_account_manager/` → `mcp_gateway/modules/telegram_user/`
2. В `~/.claude.json`: `"telegram"` → `"gateway"` (порт тот же: 8200)
3. `telegram-account-manager.service` → `mcp-gateway.service`
4. Репо `telegram-account-manager` архивируется на GitHub
