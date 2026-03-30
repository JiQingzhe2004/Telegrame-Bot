# Telegram 管理机器人

## 启动方式（终端只做安装和启动）

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
python -m bot.bootstrap
python -m bot.main
```

`python -m bot.bootstrap` 会自动：
- 安装后端依赖
- 安装前端依赖
- 构建前端（`web-admin/dist`）

## 首次配置（在前端向导完成）

1. 启动后端后，终端会打印一次性口令（20 分钟有效）。
2. 浏览器打开：`http://127.0.0.1:10010`
3. 在向导页面输入一次性口令，填写：
- BOT Token
- 管理 API Token
- OpenAI/兼容平台 Key
- 运行模式（polling/webhook）
- 模型参数
4. 点击“保存并激活”，后端热生效，无需重启。

激活后会进入企业风格管理后台（左侧菜单 + 顶部栏），一级菜单为：
- 运行总览
- 群管理
- AI 配置（支持热生效）
- 策略配置
- 名单管理
- 审计中心
- 处置记录
- 申诉与回滚
- 系统设置

## 新增：入群验证与 AI 欢迎语

- 新成员可先验证再发言，超时自动移出；
- 欢迎语可使用 AI 生成，失败自动回退模板；
- 使用已有 AI 配置，不新增独立密钥。

详细说明见：[入群验证与AI欢迎语文档](docs/入群验证与AI欢迎语.md)

## 运行状态

- `SETUP`：仅向导与配置接口可用，机器人未连接 Telegram。
- `ACTIVE`：机器人运行中，管理台和 `/api/v1/...` 管理接口可用。

健康检查：

```powershell
curl http://127.0.0.1:10010/healthz
```

## 前端交付方式

- 默认内置：后端直接托管 `web-admin/dist`，访问根路径即可。
- 独立开发：可单独运行前端

```powershell
cd web-admin
npm install
npm run dev
```

## 主要接口

- 运行状态：`GET /api/v1/runtime/state`
- 向导状态：`GET /api/v1/setup/state`
- 口令认证：`POST /api/v1/setup/auth`
- 保存配置：`POST /api/v1/setup/config`
- 激活运行：`POST /api/v1/setup/activate`

管理接口在 `ACTIVE` 状态启用：
- `GET /api/v1/status`
- `GET/PUT /api/v1/chats/{chat_id}/settings`
- 白黑名单、审计、处置、申诉、回滚等接口保持不变

## 基础环境变量

业务配置不再使用 `.env`。  
`.env` 仅保留基础参数（端口、日志、数据库路径等），见 `.env.example`。

## AI 协作约定

- 仓库已定义 AI 规则文件 [AGENTS.md](/D:/JiQingzhe/GitHub项目/管理机器人/AGENTS.md)。
- 所有 Git 提交信息必须使用中文。
