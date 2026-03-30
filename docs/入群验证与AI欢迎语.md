# 入群验证与 AI 欢迎语

## 功能说明

本版本新增两项群治理能力：

- 入群验证：新成员入群后会先被临时限制发言，需要在限定时间内点击“完成入群验证”按钮。
- 欢迎语：成员通过验证（或未开启验证时直接入群）后，机器人会发送欢迎语；可选择使用 AI 生成欢迎语。

这两项能力共用现有 AI 配置（`openai_api_key`、`openai_base_url`、模型与超时配置），无需新增独立密钥。

## 配置项

运行配置新增以下字段（支持首次向导和运行时热更新）：

- `join_verification_enabled`：是否开启入群验证（默认 `true`）
- `join_verification_timeout_seconds`：验证超时秒数（默认 `180`）
- `join_welcome_enabled`：是否发送欢迎语（默认 `true`）
- `join_welcome_use_ai`：是否使用 AI 生成欢迎语（默认 `true`）
- `join_welcome_template`：欢迎语模板（支持 `{user}`、`{chat}` 占位符）

示例模板：

```text
欢迎 {user} 加入 {chat}，请先阅读群规并友善交流。
```

## 行为细节

1. 新成员入群
- 若 `join_verification_enabled=true`：机器人限制该成员发言，并发送验证按钮。
- 若 `join_verification_enabled=false`：跳过验证，进入欢迎流程。

2. 成员点击验证按钮
- 仅允许该新成员本人点击通过。
- 验证通过后解除限制，并触发欢迎语（若开启）。

3. 超时未验证
- 到达 `join_verification_timeout_seconds` 后，机器人会将该成员移出群聊。

4. 欢迎语生成
- 当 `join_welcome_enabled=true` 时发送欢迎语。
- 若 `join_welcome_use_ai=true` 且 AI 可用：优先调用 AI 生成。
- AI 失败或未配置时：自动回退到 `join_welcome_template`。

## API 更新

`PUT /api/v1/runtime/config` 现支持更新上述 5 个字段（热生效）。

## 管理台入口

- 首次配置向导：可直接配置入群验证与欢迎语参数。
- 管理后台「AI 配置」页：可在线调整并热生效。

