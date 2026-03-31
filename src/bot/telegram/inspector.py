"""自动巡检模块：定期检查权限缺失、Webhook 异常、AI 超时率、动作失败率并主动告警。"""
from __future__ import annotations

import logging
from datetime import timedelta

from telegram import Bot
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

from bot.storage.repo import BotRepository
from bot.system_config import RuntimeConfig
from bot.utils.time import utc_now

logger = logging.getLogger(__name__)

# 巡检间隔（秒）
INSPECT_INTERVAL_SECONDS = 300  # 每 5 分钟一次

# 告警阈值
AI_TIMEOUT_RATE_THRESHOLD = 0.3   # AI 超时率 > 30% 告警
ACTION_FAIL_RATE_THRESHOLD = 0.3  # 动作失败率 > 30% 告警
LOOKBACK_MINUTES = 30             # 统计最近 30 分钟数据


async def _check_bot_permissions(bot: Bot, chat_id: int) -> list[str]:
    """检查机器人在群内是否缺少关键权限，返回缺失权限列表"""
    issues: list[str] = []
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id=chat_id, user_id=me.id)
        perms = getattr(member, "privileges", None) or getattr(member, "can_delete_messages", None)
        # 逐项检查关键权限
        for attr, label in [
            ("can_delete_messages", "删除消息"),
            ("can_restrict_members", "限制成员"),
            ("can_invite_users", "邀请用户"),
        ]:
            if not getattr(member, attr, True):
                issues.append(label)
    except TelegramError as exc:
        logger.warning("permission check failed chat=%s err=%s", chat_id, exc)
    return issues


def _calc_ai_timeout_rate(repo: BotRepository, lookback_minutes: int) -> float:
    """计算最近 N 分钟内 AI 超时率（ai_used=1 且 final_level=0 的比例近似）"""
    try:
        since = utc_now() - timedelta(minutes=lookback_minutes)
        from bot.utils.time import to_iso
        with repo.db.connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM moderation_decisions WHERE ai_used=1 AND created_at>=?",
                (to_iso(since),),
            ).fetchone()[0]
            if total == 0:
                return 0.0
            # ai_output 为空视为超时/失败
            failed = conn.execute(
                "SELECT COUNT(*) FROM moderation_decisions WHERE ai_used=1 AND created_at>=? AND (ai_output IS NULL OR ai_output='')",
                (to_iso(since),),
            ).fetchone()[0]
            return failed / total
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai timeout rate calc failed: %s", exc)
        return 0.0


def _calc_action_fail_rate(repo: BotRepository, lookback_minutes: int) -> float:
    """计算最近 N 分钟内动作失败率（downgraded=1 的比例）"""
    try:
        since = utc_now() - timedelta(minutes=lookback_minutes)
        from bot.utils.time import to_iso
        with repo.db.connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM enforcements WHERE created_at>=?",
                (to_iso(since),),
            ).fetchone()[0]
            if total == 0:
                return 0.0
            # reason 包含 'downgraded' 视为失败/降级
            failed = conn.execute(
                "SELECT COUNT(*) FROM enforcements WHERE created_at>=? AND reason LIKE '%downgraded%'",
                (to_iso(since),),
            ).fetchone()[0]
            return failed / total
    except Exception as exc:  # noqa: BLE001
        logger.warning("action fail rate calc failed: %s", exc)
        return 0.0


async def run_inspection(context: ContextTypes.DEFAULT_TYPE) -> None:
    """定时巡检入口，由 job_queue.run_repeating 调用"""
    app: Application = context.application
    repo: BotRepository | None = app.bot_data.get("repo")
    runtime_config: RuntimeConfig = app.bot_data.get("runtime_config") or RuntimeConfig()

    if repo is None:
        return

    alerts: list[str] = []

    # 1. 检查 AI 超时率
    ai_rate = _calc_ai_timeout_rate(repo, LOOKBACK_MINUTES)
    if ai_rate > AI_TIMEOUT_RATE_THRESHOLD:
        alerts.append(f"⚠️ AI 超时率过高：{ai_rate:.0%}（近 {LOOKBACK_MINUTES} 分钟）")

    # 2. 检查动作失败率
    fail_rate = _calc_action_fail_rate(repo, LOOKBACK_MINUTES)
    if fail_rate > ACTION_FAIL_RATE_THRESHOLD:
        alerts.append(f"⚠️ 动作失败/降级率过高：{fail_rate:.0%}（近 {LOOKBACK_MINUTES} 分钟）")

    # 3. 检查各活跃群的机器人权限
    try:
        chats = repo.list_chats(limit=50)
        for chat in chats:
            chat_id = int(chat["chat_id"])
            issues = await _check_bot_permissions(app.bot, chat_id)
            if issues:
                alerts.append(f"⚠️ 群 {chat.get('title') or chat_id} 权限缺失：{'、'.join(issues)}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat permission inspection failed: %s", exc)

    # 4. 检查 Webhook 模式下的连通性
    if runtime_config.run_mode == "webhook":
        try:
            wh_info = await app.bot.get_webhook_info()
            if wh_info.last_error_message:
                alerts.append(f"⚠️ Webhook 异常：{wh_info.last_error_message}")
        except TelegramError as exc:
            alerts.append(f"⚠️ Webhook 状态获取失败：{exc}")

    if not alerts:
        logger.debug("inspection passed, no issues found")
        return

    # 发送告警到所有活跃群
    alert_text = "🔍 自动巡检告警\n" + "\n".join(alerts)
    logger.warning("inspection alerts: %s", alert_text)
    try:
        chats = repo.list_chats(limit=50)
        sent = set()
        for chat in chats:
            chat_id = int(chat["chat_id"])
            if chat_id in sent:
                continue
            sent.add(chat_id)
            try:
                await app.bot.send_message(chat_id=chat_id, text=alert_text)
            except TelegramError as exc:
                logger.warning("send inspection alert failed chat=%s err=%s", chat_id, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("inspection alert broadcast failed: %s", exc)


def register_inspection_job(app: Application) -> None:
    """在 build_application 后注册定时巡检任务"""
    if app.job_queue is None:
        logger.warning("job_queue not available, inspection job not registered")
        return
    app.job_queue.run_repeating(
        run_inspection,
        interval=INSPECT_INTERVAL_SECONDS,
        first=60,  # 启动 60 秒后首次执行
        name="auto-inspection",
    )
    logger.info("auto inspection job registered, interval=%ds", INSPECT_INTERVAL_SECONDS)
