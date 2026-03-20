# Деплой MCP-Gateway

## Требования

- Ubuntu 24.04, пользователь `assistant`
- Python 3.12 (`/usr/bin/python3`)
- systemd user services (lingering включён)
- `~/.env` с переменными окружения

## Через Ansible (рекомендуется)

Роль `mcp-gateway` в [ansible-openclaw-assistant](https://github.com/alexanderbrownemail-create/ansible-openclaw-assistant):

```bash
# Предварительно: добавить TELEGRAM_BOT_TOKEN в vault
ansible-playbook site.yml --tags mcp-gateway
```

Роль выполняет:
1. Клонирование `mcp-gateway` в `~/automations/mcp-gateway/`
2. `pip install -e .` (user install)
3. Деплой `~/.env` из Ansible Vault (merge с существующим)
4. Копирование `mcp-gateway.service` в `~/.config/systemd/user/`
5. `systemctl --user enable --now mcp-gateway`
6. Обновление `~/.claude.json`: `"telegram"` → `"gateway"`
7. Перезапуск openclaw-gateway (подхватывает новый MCP)

## Вручную

### 1. Клонировать и установить

```bash
ssh assistant@94.183.188.104
cd ~/automations
git clone https://github.com/alexanderbrownemail-create/mcp-gateway
cd mcp-gateway
pip install -e . --user
```

### 2. Настроить окружение

Добавить в `~/.env`:
```bash
GATEWAY_HOST=127.0.0.1
GATEWAY_PORT=8200
GATEWAY_LOG_LEVEL=INFO
TELEGRAM_BOT_TOKEN=<токен от @BotFather>
# Остальные TELEGRAM_* уже должны быть от telegram-account-manager
```

### 3. Systemd unit

```bash
mkdir -p ~/.config/systemd/user/
cat > ~/.config/systemd/user/mcp-gateway.service << 'EOF'
[Unit]
Description=MCP Gateway
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/automations/mcp-gateway
ExecStart=/usr/bin/python3 -m mcp_gateway
EnvironmentFile=%h/.env
Restart=always
RestartSec=5
KillMode=control-group

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now mcp-gateway
```

### 4. Обновить ~/.claude.json

```bash
# Заменить "telegram" на "gateway"
python3 -c "
import json, pathlib
p = pathlib.Path('~/.claude.json').expanduser()
d = json.loads(p.read_text())
servers = d.setdefault('mcpServers', {})
servers['gateway'] = {'type': 'http', 'url': 'http://127.0.0.1:8200/mcp'}
servers.pop('telegram', None)
p.write_text(json.dumps(d, indent=2))
print('Done')
"
```

### 5. Перезапустить openclaw-gateway

```bash
systemctl --user restart openclaw-gateway
# Проверить что новые инструменты доступны
```

## Миграция с telegram-account-manager

1. Убедиться что `mcp-gateway` запущен и отвечает на `:8200`
2. Обновить `~/.claude.json` (шаг 4 выше)
3. Остановить старый сервис: `systemctl --user stop telegram-account-manager`
4. Отключить: `systemctl --user disable telegram-account-manager`
5. Проверить работу агента

## Обновление

```bash
# Через tmux-сессию в WSL:
wsl -d Ubuntu-22.04
tmux attach -t gateway  # или: tmux new-session -A -s gateway
ssh assistant@94.183.188.104

cd ~/automations/mcp-gateway
git pull
pip install -e . --user
systemctl --user restart mcp-gateway
journalctl --user -u mcp-gateway -f
```

## Диагностика

```bash
# Статус сервиса
systemctl --user status mcp-gateway

# Логи в реальном времени
journalctl --user -u mcp-gateway -f

# Проверить что MCP отвечает
curl -s http://127.0.0.1:8200/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 -m json.tool

# Проверить переменные окружения сервиса
systemctl --user show-environment
```
