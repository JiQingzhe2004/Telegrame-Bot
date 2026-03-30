# Telegram 管理机器人

基于 Python + `python-telegram-bot` + SQLite + OpenAI SDK 的群管理服务，支持规则与 AI 联合判定、分级处置、审计追溯、管理命令与 HTTP 管理 API。

## 快速开始

```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -e .[dev]
copy .env.example .env
python -m bot.main
```

## 运行模式

- `RUN_MODE=polling`：本地开发默认模式（长轮询）。
- `RUN_MODE=webhook`：生产建议模式，通过 FastAPI + Uvicorn 提供 webhook 与管理 API。

## 管理 API

- 健康检查：`GET /healthz`
- 运行状态：`GET /api/v1/status`
- 需要请求头：`X-Admin-Token: <ADMIN_API_TOKEN>`

## systemd 示例

```ini
[Unit]
Description=Telegram Moderator Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/telegram-moderator-bot
EnvironmentFile=/opt/telegram-moderator-bot/.env
ExecStart=/opt/telegram-moderator-bot/.venv/bin/python -m bot.main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
