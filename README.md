# Telegram 管理机器人使用说明

这是一个 Telegram 群管理机器人后端服务，支持：
- 规则判定（黑名单词、可疑链接、刷屏）
- AI 判定（语义补充）
- 自动处置（提醒/删帖/禁言）
- SQLite 审计追踪
- 管理员命令 + HTTP 管理 API

## 1. 使用前准备（必须）

1. 你需要先在 Telegram 的 `@BotFather` 创建机器人，拿到 `BOT_TOKEN`。  
2. 把机器人拉进目标群并设为管理员，至少给这些权限：
- 删除消息
- 限制成员（禁言）
3. 本机安装 Python 3.12+。

如果没给权限，机器人会降级处理（例如只能提醒，不能删帖/禁言）。

## 2. 本地启动（Windows PowerShell）

在项目根目录执行：

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -e .[dev]
Copy-Item .env.example .env
```

编辑 `.env`，至少改这 3 项：

```env
BOT_TOKEN=你的TelegramBotToken
OPENAI_API_KEY=你的OpenAIKey
ADMIN_API_TOKEN=一个你自己定义的API令牌
```

如果你要接第三方模型平台（OpenAI 兼容协议），再加：

```env
OPENAI_BASE_URL=https://你的兼容网关/v1
OPENAI_API_KEY=第三方平台签发的Key
AI_LOW_RISK_MODEL=对应模型名
AI_HIGH_RISK_MODEL=对应模型名
```

然后启动：

```powershell
python -m bot.main
```

## 3. 运行模式

`.env` 里：
- `RUN_MODE=polling`：开发默认。机器人主动拉取 Telegram 更新，最省事。
- `RUN_MODE=webhook`：生产推荐。Telegram 主动回调到你的服务地址。

### Webhook 额外配置

```env
RUN_MODE=webhook
WEBHOOK_PUBLIC_URL=https://你的公网域名
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_PORT=8080
```

注意：Webhook 必须公网可访问并有 HTTPS。

## 4. 机器人命令（群内）

管理员命令：
- `/status` 查看运行统计
- `/config` 查看当前群配置
- `/ai on|off` 开关 AI
- `/threshold 0.75` 设置 AI 置信度阈值
- `/banword add 关键词`
- `/banword del 关键词`
- `/whitelist add @username或user_id`
- `/whitelist del @username或user_id`
- `/forgive user_id` 清空某用户累犯分

用户命令：
- `/appeal 申诉理由` 记录申诉

## 5. HTTP 管理 API（可选）

默认服务地址 `http://127.0.0.1:8080`。

### 健康检查

```powershell
curl http://127.0.0.1:8080/healthz
```

### 读取状态

```powershell
curl -H "X-Admin-Token: 你的ADMIN_API_TOKEN" http://127.0.0.1:8080/api/v1/status
```

### 查看群配置

```powershell
curl -H "X-Admin-Token: 你的ADMIN_API_TOKEN" http://127.0.0.1:8080/api/v1/chats/-1001234567890/settings
```

### 更新群配置

```powershell
curl -X PUT `
  -H "X-Admin-Token: 你的ADMIN_API_TOKEN" `
  -H "Content-Type: application/json" `
  -d "{\"ai_enabled\":true,\"ai_threshold\":0.8,\"mode\":\"balanced\"}" `
  http://127.0.0.1:8080/api/v1/chats/-1001234567890/settings
```

## 6. 默认处置策略

- Level 0：不处理
- Level 1：提醒
- Level 2：删除/短时限制（按累犯升级）
- Level 3：长时禁言（默认 7 天）

低置信度时，高风险动作会自动降级为 `warn`。

## 7. 常见问题（直接排查）

1. 机器人没反应
- 先确认 `BOT_TOKEN` 正确
- 确认机器人在群里且是管理员
- `RUN_MODE=webhook` 时确认公网 HTTPS 可达

2. 只能提醒，不能删帖/禁言
- 群管理员权限没给全

3. API 返回 401
- 请求头没带或带错 `X-Admin-Token`

4. AI 一直不生效
- `OPENAI_API_KEY` 未配置或错误
- 群配置中 `ai_enabled` 被关掉

## 8. 生产托管（systemd 示例）

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
