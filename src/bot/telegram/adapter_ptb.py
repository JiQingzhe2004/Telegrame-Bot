from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

from telegram import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    Chat,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.ai.openai_client import OpenAiModerator
from bot.points_service import PointsService
from bot.lottery_service import LotteryService
from bot.ai.redact import redact_pii
from bot.domain.models import ChatRef, MessageRef, ModerationContext, UserRef
from bot.domain.moderation import Enforcer, ModerationService
from bot.storage.repo import BotRepository
from bot.system_config import RuntimeConfig
from bot.telegram.commands import (
    POINTS_SELF_CALLBACK_PREFIX,
    USER_FLOW_CALLBACK_PREFIX,
    _send_private_points,
    ai_cmd,
    appeal_cmd,
    banword_cmd,
    checkin_cmd,
    on_private_text,
    on_user_flow_callback,
    config_cmd,
    forgive_cmd,
    pay_cmd,
    points_entry_markup,
    points_add_cmd,
    points_cmd,
    points_sub_cmd,
    rank_cmd,
    redeem_cmd,
    shop_cmd,
    start_cmd,
    status_cmd,
    tasks_cmd,
    threshold_cmd,
    whitelist_cmd,
)
from bot.telegram.permissions import get_permission_snapshot, is_admin
from bot.utils.time import utc_now
from bot.utils.rate_limit import RaidDetector
from bot.telegram.inspector import register_inspection_job
from bot.telegram.lottery import LOTTERY_CALLBACK_PREFIX, on_lottery_callback, register_lottery_job

logger = logging.getLogger(__name__)
VERIFY_CALLBACK_PREFIX = "join_verify:"
VERIFY_NOTICE_TTL_SECONDS = 45


def _pending_verifications(application: Application) -> dict[str, dict[str, Any]]:
    bucket = application.bot_data.get("pending_join_verifications")
    if not isinstance(bucket, dict):
        bucket = {}
        application.bot_data["pending_join_verifications"] = bucket
    return bucket


async def _safe_delete_message(bot, chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=int(message_id))
    except TelegramError as exc:
        logger.warning("delete message failed chat=%s message=%s err=%s", chat_id, message_id, exc)


async def _delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data if context.job else None
    if not isinstance(data, dict):
        return
    await _safe_delete_message(
        context.bot,
        int(data.get("chat_id", 0)),
        int(data.get("message_id", 0)),
    )


async def _send_temporary_notice(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    text: str,
    ttl_seconds: int = VERIFY_NOTICE_TTL_SECONDS,
) -> None:
    notice = await context.bot.send_message(chat_id=chat_id, text=text)
    if context.application.job_queue:
        context.application.job_queue.run_once(
            _delete_message_job,
            when=ttl_seconds,
            data={"chat_id": chat_id, "message_id": notice.message_id},
            name=f"cleanup-notice-{chat_id}-{notice.message_id}",
        )


async def _cleanup_verification_messages(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    entry: dict[str, Any] | None,
) -> None:
    payload = entry or {}
    await _safe_delete_message(context.bot, chat_id, payload.get("verify_message_id"))
    await _safe_delete_message(context.bot, chat_id, payload.get("join_message_id"))


def _remember_group_chat(repo: BotRepository, chat: Chat) -> None:
    if chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        return
    repo.upsert_chat(ChatRef(chat_id=chat.id, type=chat.type, title=chat.title))


def _chat_enabled(repo: BotRepository, chat_id: int) -> bool:
    try:
        return bool(repo.get_settings(chat_id).chat_enabled)
    except Exception:
        return False


def _render_welcome_template(template: str, user_name: str, chat_title: str | None) -> str:
    base = template or "欢迎 {user} 加入 {chat}，请先阅读群规并友善交流。"
    return base.replace("{user}", user_name).replace("{chat}", chat_title or "本群")


def _get_time_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


async def _build_welcome_text(
    context: ContextTypes.DEFAULT_TYPE,
    runtime_config: RuntimeConfig,
    *,
    chat_id: int,
    chat_title: str | None,
    chat_type: str | None,
    user_name: str,
    user_id: int | None = None,
) -> str:
    from datetime import datetime, timezone as _tz
    repo: BotRepository | None = context.application.bot_data.get("repo")
    points_service: PointsService | None = context.application.bot_data.get("points_service")
    now_hour = datetime.now(tz=_tz.utc).hour
    time_of_day = _get_time_of_day(now_hour)

    # 多模板轮换：从数据库取匹配时段/群类型的模板
    chosen_template = runtime_config.join_welcome_template
    if repo is not None:
        templates = repo.list_welcome_templates(chat_id, hour=now_hour, chat_type=chat_type)
        if templates:
            chosen_template = templates[0]["template"]
        if points_service is not None and user_id is not None:
            bonus = points_service.get_active_welcome_bonus(chat_id, user_id)
            if bonus and bonus.get("reward_payload"):
                try:
                    payload = json.loads(str(bonus["reward_payload"]))
                    bonus_template = str(payload.get("template", "")).strip()
                    if bonus_template:
                        chosen_template = bonus_template
                        if bonus.get("id"):
                            points_service.consume_welcome_bonus(int(bonus["id"]))
                except json.JSONDecodeError:
                    pass

    fallback = _render_welcome_template(chosen_template, user_name, chat_title)
    if not runtime_config.join_welcome_use_ai:
        logger.info("welcome_template_used reason=ai_disabled chat_id=%s", chat_id)
        return fallback
    ai_moderator = context.application.bot_data.get("ai_moderator")
    if not isinstance(ai_moderator, OpenAiModerator):
        logger.info("welcome_template_used reason=ai_unavailable chat_id=%s", chat_id)
        return fallback
    try:
        welcome = await ai_moderator.generate_welcome(
            chat_title=chat_title or "群聊",
            user_display_name=user_name,
            language="zh",
            template=chosen_template,
            time_of_day=time_of_day,
            chat_type=chat_type,
        )
        if welcome.strip() == fallback.strip():
            logger.info("ai_welcome_matches_template chat_id=%s", chat_id)
        return welcome
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai welcome generation failed: %s", exc)
        return fallback


def _restricted_permissions() -> ChatPermissions:
    return ChatPermissions.no_permissions()


def _verification_release_permissions() -> ChatPermissions:
    return ChatPermissions.all_permissions()


async def _verification_timeout(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data if context.job else None
    if not isinstance(data, dict):
        return
    chat_id = int(data.get("chat_id", 0))
    user_id = int(data.get("user_id", 0))
    if not chat_id or not user_id:
        return
    key = f"{chat_id}:{user_id}"
    store = _pending_verifications(context.application)
    if key not in store:
        return
    entry = store.pop(key, {}) or {}
    attempts = int(entry.get("attempts", 0))
    display_name = str(entry.get("display_name") or user_id)

    repo: BotRepository | None = context.application.bot_data.get("repo")
    if repo:
        try:
            repo.save_verification_log(
                chat_id=chat_id,
                user_id=user_id,
                username=None,
                result="fail_timeout",
                attempts=attempts,
                whitelist_bypass=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("save verification log failed: %s", exc)

    try:
        await _cleanup_verification_messages(context, chat_id=chat_id, entry=entry)
        await context.bot.ban_chat_member(
            chat_id=chat_id, user_id=user_id, until_date=utc_now() + timedelta(minutes=1)
        )
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
        await _send_temporary_notice(
            context,
            chat_id=chat_id,
            text=f"{display_name} 未在限时内完成入群验证，已被移出群聊。",
        )
    except TelegramError as exc:
        logger.warning(
            "join verification timeout action failed chat=%s user=%s err=%s", chat_id, user_id, exc
        )


async def on_join_verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    payload = query.data.removeprefix(VERIFY_CALLBACK_PREFIX)
    parts = payload.split(":")
    # 格式: {chat_id}:{user_id}:{answer}  answer="ok"(button) 或 "0"/"1"/"2"/"3"(quiz)
    if len(parts) != 3:
        await query.answer("验证参数错误", show_alert=True)
        return
    try:
        chat_id = int(parts[0])
        user_id = int(parts[1])
        answer = parts[2]
    except ValueError:
        await query.answer("验证参数错误", show_alert=True)
        return

    if not query.from_user or query.from_user.id != user_id:
        await query.answer("请由新成员本人点击验证。", show_alert=True)
        return

    runtime_config: RuntimeConfig = context.application.bot_data.get("runtime_config") or RuntimeConfig()
    repo: BotRepository = context.application.bot_data["repo"]
    key = f"{chat_id}:{user_id}"
    store = _pending_verifications(context.application)
    if key not in store:
        await query.answer("验证已失效，请重新入群。", show_alert=True)
        return

    entry = store[key]
    question_type = entry.get("question_type", "button")
    max_attempts = int(runtime_config.join_verification_max_attempts)

    # 判断答案是否正确
    if question_type == "quiz":
        correct_index = entry.get("answer_index")
        try:
            passed = int(answer) == int(correct_index)
        except (ValueError, TypeError):
            passed = False
    else:
        passed = answer == "ok"

    if passed:
        store.pop(key, None)
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=_verification_release_permissions(),
                use_independent_chat_permissions=True,
            )
        except TelegramError as exc:
            logger.warning(
                "release member after verify failed chat=%s user=%s err=%s", chat_id, user_id, exc
            )

        try:
            repo.save_verification_log(
                chat_id=chat_id,
                user_id=user_id,
                username=query.from_user.username,
                result="pass",
                attempts=int(entry.get("attempts", 0)) + 1,
                whitelist_bypass=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("save verification log failed: %s", exc)

        await query.answer("验证成功")
        await _cleanup_verification_messages(context, chat_id=chat_id, entry=entry)
        points_service: PointsService | None = context.application.bot_data.get("points_service")
        if points_service is not None:
            try:
                task_rewards = points_service.handle_verification_pass(chat_id, user_id)
                for reward in task_rewards:
                    await _send_temporary_notice(
                        context,
                        chat_id=chat_id,
                        text=f"{query.from_user.full_name} 完成任务「{reward['task_key']}」，获得 {reward['reward_points']} 积分。",
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("verification task progress failed chat=%s user=%s err=%s", chat_id, user_id, exc)

        if runtime_config.join_welcome_enabled:
            welcome = await _build_welcome_text(
                context,
                runtime_config,
                chat_id=chat_id,
                chat_title=update.effective_chat.title if update.effective_chat else None,
                chat_type=update.effective_chat.type if update.effective_chat else None,
                user_name=query.from_user.full_name,
                user_id=query.from_user.id,
            )
            await context.bot.send_message(chat_id=chat_id, text=welcome)
    else:
        # 答错
        entry["attempts"] = int(entry.get("attempts", 0)) + 1
        attempts = int(entry["attempts"])
        if attempts >= max_attempts:
            store.pop(key, None)
            try:
                repo.save_verification_log(
                    chat_id=chat_id,
                    user_id=user_id,
                    username=query.from_user.username,
                    result="fail_max_attempts",
                    attempts=attempts,
                    whitelist_bypass=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("save verification log failed: %s", exc)
            await query.answer("验证失败次数过多，已移出群聊。", show_alert=True)
            try:
                await _cleanup_verification_messages(context, chat_id=chat_id, entry=entry)
                await context.bot.ban_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    until_date=utc_now() + timedelta(minutes=1),
                )
                await context.bot.unban_chat_member(
                    chat_id=chat_id, user_id=user_id, only_if_banned=True
                )
                await _send_temporary_notice(
                    context,
                    chat_id=chat_id,
                    text=f"{query.from_user.full_name} 验证失败次数过多，已被移出群聊。",
                )
            except TelegramError as exc:
                logger.warning(
                    "kick after max attempts failed chat=%s user=%s err=%s", chat_id, user_id, exc
                )
        else:
            remaining = max_attempts - attempts
            await query.answer(f"答案错误，还剩 {remaining} 次机会。", show_alert=True)


async def on_points_self_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    payload = query.data.removeprefix(POINTS_SELF_CALLBACK_PREFIX)
    parts = payload.split(":")
    if len(parts) != 2:
        await query.answer("参数错误", show_alert=True)
        return
    try:
        chat_id = int(parts[0])
        user_id = int(parts[1])
    except ValueError:
        await query.answer("参数错误", show_alert=True)
        return
    if not query.from_user or query.from_user.id != user_id:
        await query.answer("只能查看你自己的积分。", show_alert=True)
        return
    repo: BotRepository = context.application.bot_data["repo"]
    success, notice = await _send_private_points(
        bot=context.bot,
        repo=repo,
        chat_id=chat_id,
        user_id=user_id,
        username=getattr(context.bot, "username", None),
        chat_title=update.effective_chat.title if update.effective_chat else None,
    )
    await query.answer(notice if not success else "已私聊发送", show_alert=not success)


async def _register_bot_commands(app: Application) -> None:
    bot = app.bot
    private_commands = [
        BotCommand("start", "打开使用说明与私聊入口"),
    ]
    group_commands = [
        BotCommand("points", "查看我的积分（私聊返回）"),
        BotCommand("rank", "查看本群积分排行榜"),
        BotCommand("pay", "给群成员转账积分 /pay 用户 金额"),
        BotCommand("checkin", "每日签到领取积分"),
        BotCommand("tasks", "查看今日任务进度"),
        BotCommand("shop", "查看当前可兑换商品"),
        BotCommand("redeem", "兑换商品 /redeem 商品键名"),
    ]
    admin_commands = group_commands + [
        BotCommand("points_add", "管理员加分 /points_add 用户 金额"),
        BotCommand("points_sub", "管理员扣分 /points_sub 用户 金额"),
        BotCommand("status", "查看机器人运行状态摘要"),
        BotCommand("config", "查看当前群配置详情"),
        BotCommand("ai", "切换 AI 审核开关 /ai on|off"),
        BotCommand("threshold", "调整 AI 阈值 /threshold 0-1"),
        BotCommand("banword", "管理黑名单词 /banword add|del 词"),
        BotCommand("whitelist", "管理白名单 /whitelist add|del 用户"),
        BotCommand("forgive", "清空用户违规分 /forgive 用户"),
    ]
    try:
        await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeAllChatAdministrators())
    except TelegramError as exc:
        logger.warning("register bot commands failed: %s", exc)


async def on_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_message:
        return
    chat = update.effective_chat
    if chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        return
    msg = update.effective_message
    members = msg.new_chat_members or []
    if not members:
        return

    repo: BotRepository = context.application.bot_data["repo"]
    _remember_group_chat(repo, chat)
    if not _chat_enabled(repo, chat.id):
        return
    runtime_config: RuntimeConfig = context.application.bot_data.get("runtime_config") or RuntimeConfig()
    timeout_seconds = max(30, int(runtime_config.join_verification_timeout_seconds))
    max_attempts = int(runtime_config.join_verification_max_attempts)
    question_type = runtime_config.join_verification_question_type
    whitelist_bypass_enabled = runtime_config.join_verification_whitelist_bypass

    # Raid 检测：逐个成员记录入群事件，任一触发则记录并广播告警
    raid_triggered = False
    for joined in members:
        if joined.is_bot:
            continue
        _name = joined.full_name or joined.username or str(joined.id)
        from datetime import datetime, timezone as _tz
        raid_result = _raid_detector.record_and_check(
            chat_id=chat.id,
            display_name=_name,
            now=datetime.now(tz=_tz.utc),
        )
        if raid_result.hit and not raid_triggered:
            raid_triggered = True
            try:
                import json as _json
                repo.save_raid_event(
                    chat_id=chat.id,
                    trigger_type=raid_result.trigger_type,
                    join_count=raid_result.join_count,
                    details=_json.dumps(
                        {"similar_names": raid_result.similar_names or []},
                        ensure_ascii=False,
                    ),
                )
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=(
                        f"⚠️ 检测到可疑入群行为（{raid_result.trigger_type}）："
                        f"{raid_result.join_count} 人在 {raid_result.window_seconds} 秒内入群，已触发高压策略。"
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("raid alert failed chat=%s err=%s", chat.id, exc)

    for joined in members:
        if joined.is_bot:
            continue

        display_name = joined.full_name or joined.username or str(joined.id)
        repo.upsert_chat_user(
            ChatRef(chat_id=chat.id, type=chat.type, title=chat.title),
            UserRef(
                user_id=joined.id,
                username=joined.username,
                is_bot=bool(joined.is_bot),
                first_name=joined.first_name,
                last_name=joined.last_name,
            ),
        )

        if not runtime_config.join_verification_enabled:
            if runtime_config.join_welcome_enabled:
                welcome = await _build_welcome_text(
                    context, runtime_config, chat_id=chat.id, chat_title=chat.title, chat_type=chat.type, user_name=display_name, user_id=joined.id
                )
                await msg.reply_text(welcome)
            continue

        # 白名单豁免
        if whitelist_bypass_enabled:
            try:
                whitelisted = repo.is_whitelisted(chat.id, joined.id, joined.username)
            except Exception as exc:  # noqa: BLE001
                logger.warning("is_whitelisted check failed: %s", exc)
                whitelisted = False
            if whitelisted:
                try:
                    repo.save_verification_log(
                        chat_id=chat.id,
                        user_id=joined.id,
                        username=joined.username,
                        result="whitelist_bypass",
                        attempts=0,
                        whitelist_bypass=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("save verification log failed: %s", exc)
                if runtime_config.join_welcome_enabled:
                    welcome = await _build_welcome_text(
                        context, runtime_config, chat_id=chat.id, chat_title=chat.title, chat_type=chat.type, user_name=display_name, user_id=joined.id
                    )
                    await msg.reply_text(welcome)
                continue

        # 限制发言
        restrict_ok = True
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=joined.id,
                permissions=_restricted_permissions(),
                use_independent_chat_permissions=True,
            )
        except TelegramError as exc:
            restrict_ok = False
            logger.warning(
                "restrict member failed chat=%s user=%s err=%s", chat.id, joined.id, exc
            )
            try:
                await _send_temporary_notice(
                    context,
                    chat_id=chat.id,
                    text=f"{display_name} 的入群验证未生效：机器人无法限制新成员发言，请检查管理员权限。",
                )
            except TelegramError as notice_exc:
                logger.warning(
                    "send verification setup failure notice failed chat=%s user=%s err=%s",
                    chat.id,
                    joined.id,
                    notice_exc,
                )
        if not restrict_ok:
            try:
                repo.save_verification_log(
                    chat_id=chat.id,
                    user_id=joined.id,
                    username=joined.username,
                    result="setup_failed",
                    attempts=0,
                    whitelist_bypass=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("save verification log failed: %s", exc)
            continue

        # 决定验证类型（quiz 无题库则降级为 button）
        actual_question_type = question_type
        question_data: dict | None = None
        if question_type == "quiz":
            try:
                question_data = repo.get_verification_question(chat.id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("get verification question failed: %s", exc)
            if not question_data:
                actual_question_type = "button"

        if actual_question_type == "quiz" and question_data:
            raw_options = question_data["options"]
            options = json.loads(raw_options) if isinstance(raw_options, str) else raw_options
            labels = ["A", "B", "C", "D"]
            buttons = [
                [
                    InlineKeyboardButton(
                        f"{labels[i]}. {opt}",
                        callback_data=f"{VERIFY_CALLBACK_PREFIX}{chat.id}:{joined.id}:{i}",
                    )
                ]
                for i, opt in enumerate(options[:4])
            ]
            keyboard = InlineKeyboardMarkup(buttons)
            question_text = question_data["question"]
            verify_msg = await msg.reply_text(
                f"欢迎 {display_name}，请在 {timeout_seconds} 秒内回答以下问题完成入群验证：\n\n{question_text}",
                reply_markup=keyboard,
            )
            key = f"{chat.id}:{joined.id}"
            _pending_verifications(context.application)[key] = {
                "verify_message_id": verify_msg.message_id,
                "join_message_id": msg.message_id,
                "attempts": 0,
                "question_id": question_data["id"],
                "answer_index": question_data["answer_index"],
                "question_type": "quiz",
                "display_name": display_name,
            }
        else:
            # button 模式
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "✅ 点击完成入群验证",
                    callback_data=f"{VERIFY_CALLBACK_PREFIX}{chat.id}:{joined.id}:ok",
                )
            ]])
            verify_msg = await msg.reply_text(
                f"欢迎 {display_name}，请在 {timeout_seconds} 秒内点击下方按钮完成验证。",
                reply_markup=keyboard,
            )
            key = f"{chat.id}:{joined.id}"
            _pending_verifications(context.application)[key] = {
                "verify_message_id": verify_msg.message_id,
                "join_message_id": msg.message_id,
                "attempts": 0,
                "question_id": None,
                "answer_index": None,
                "question_type": "button",
                "display_name": display_name,
            }

        if context.application.job_queue:
            context.application.job_queue.run_once(
                _verification_timeout,
                when=timeout_seconds,
                data={"chat_id": chat.id, "user_id": joined.id},
                name=f"join-verify-timeout-{chat.id}-{joined.id}",
            )


async def on_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return
    chat = update.effective_chat
    if chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        return
    repo: BotRepository = context.application.bot_data["repo"]
    _remember_group_chat(repo, chat)
    if not _chat_enabled(repo, chat.id):
        return
    msg = update.effective_message
    text = msg.text or msg.caption or ""
    if not text:
        return

    service: ModerationService = context.application.bot_data["moderation_service"]
    enforcer: Enforcer = context.application.bot_data["enforcer"]
    runtime_config: RuntimeConfig = context.application.bot_data.get("runtime_config") or RuntimeConfig()

    user = update.effective_user
    if user.is_bot:
        return
    settings = repo.get_settings(chat.id)
    admin_message = await is_admin(context.bot, chat.id, user.id)
    if admin_message and not settings.allow_admin_self_test:
        return

    chat_ref = ChatRef(chat_id=chat.id, type=chat.type, title=chat.title)
    user_ref = UserRef(
        user_id=user.id,
        username=user.username,
        is_bot=bool(user.is_bot),
        first_name=user.first_name,
        last_name=user.last_name,
    )
    repo.upsert_chat_user(chat_ref, user_ref)

    strike_score = repo.get_strike_score(chat.id, user.id)
    whitelist_hit = repo.is_whitelisted(chat.id, user.id, user.username)
    blacklist_words = repo.get_blacklist_words(chat.id)
    recent_texts = repo.recent_texts(chat.id, user.id)

    mod_context = ModerationContext(
        chat=chat_ref,
        user=user_ref,
        settings=settings,
        strike_score=strike_score,
        whitelist_hit=whitelist_hit,
        blacklist_words=blacklist_words,
        recent_message_texts=recent_texts,
    )

    message_ref = MessageRef(
        chat_id=chat.id,
        message_id=msg.message_id,
        user_id=user.id,
        date=msg.date,
        text=text,
        meta={
            "admin_self_test": admin_message,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "display_name": " ".join(x for x in [user.first_name, user.last_name] if x).strip() or user.username or "该用户",
        },
    )

    redacted = redact_pii(text)
    repo.save_violation_message(message_ref, redacted)

    decision = await service.decide(message_ref, mod_context)
    repo.save_decision(
        message_ref,
        decision,
        ai_model=decision.ai_decision.raw.get("_model") if decision.ai_decision else None,
    )

    if admin_message:
        logger.info(
            "admin_self_test_completed chat_id=%s user_id=%s level=%s action=%s ai_used=%s",
            chat.id,
            user.id,
            decision.final_level,
            decision.final_action,
            decision.ai_used,
        )
        try:
            await msg.reply_text(
                f"管理员自测完成：level={decision.final_level}，action={decision.final_action}，"
                f"ai_used={'yes' if decision.ai_used else 'no'}，ai_status={decision.ai_status}，"
                f"confidence={decision.confidence:.2f}"
                f"{f'，ai_error={decision.ai_error}' if decision.ai_error else ''}。未执行真实处置。"
            )
        except TelegramError as exc:
            logger.warning("admin self test reply failed chat=%s user=%s err=%s", chat.id, user.id, exc)
        return

    try:
        points_service: PointsService | None = context.application.bot_data.get("points_service")
        if points_service is not None:
            points_result = points_service.handle_message_activity(chat.id, user.id, text, settings)
            for reward in points_result.get("task_rewards", []):
                await _send_temporary_notice(
                    context,
                    chat_id=chat.id,
                    text=f"{user.full_name} 完成任务「{reward['task_key']}」，获得 {reward['reward_points']} 积分。",
                )
        else:
            repo.maybe_reward_message_points(chat.id, user.id, text, settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reward message points failed chat=%s user=%s err=%s", chat.id, user.id, exc)

    if text.strip().lower() in {"积分", "查积分", "我的积分"}:
        try:
            await msg.reply_text(
                "我把个人积分入口放到下面了，点一下就能进私聊继续看。",
                reply_markup=points_entry_markup(chat.id, user.id),
            )
        except TelegramError as exc:
            logger.warning("send points entry button failed chat=%s user=%s err=%s", chat.id, user.id, exc)

    perms = await get_permission_snapshot(context.bot, chat.id)
    enforcement = await enforcer.apply(context.bot, message_ref, decision, perms)
    if enforcement.applied_action != "none":
        repo.save_enforcement(message_ref, enforcement)


_raid_detector = RaidDetector()


def build_application(
    bot_token: str,
    repo: BotRepository,
    moderation_service: ModerationService,
    enforcer: Enforcer,
    ai_moderator: OpenAiModerator | None = None,
    runtime_config: RuntimeConfig | None = None,
) -> Application:
    points_service = PointsService(repo)
    app = ApplicationBuilder().token(bot_token).build()
    app.bot_data["repo"] = repo
    app.bot_data["moderation_service"] = moderation_service
    app.bot_data["enforcer"] = enforcer
    app.bot_data["ai_moderator"] = ai_moderator
    app.bot_data["runtime_config"] = runtime_config or RuntimeConfig()
    app.bot_data["pending_join_verifications"] = {}
    app.bot_data["points_service"] = points_service
    app.bot_data["lottery_service"] = LotteryService(repo)

    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("config", config_cmd))
    app.add_handler(CommandHandler("ai", ai_cmd))
    app.add_handler(CommandHandler("threshold", threshold_cmd))
    app.add_handler(CommandHandler("banword", banword_cmd))
    app.add_handler(CommandHandler("whitelist", whitelist_cmd))
    app.add_handler(CommandHandler("forgive", forgive_cmd))
    app.add_handler(CommandHandler("appeal", appeal_cmd))
    app.add_handler(CommandHandler("points", points_cmd))
    app.add_handler(CommandHandler("rank", rank_cmd))
    app.add_handler(CommandHandler("pay", pay_cmd))
    app.add_handler(CommandHandler("checkin", checkin_cmd))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("redeem", redeem_cmd))
    app.add_handler(CommandHandler("points_add", points_add_cmd))
    app.add_handler(CommandHandler("points_sub", points_sub_cmd))
    app.add_handler(CallbackQueryHandler(on_lottery_callback, pattern=f"^{LOTTERY_CALLBACK_PREFIX}"))
    app.add_handler(CallbackQueryHandler(on_user_flow_callback, pattern=f"^{USER_FLOW_CALLBACK_PREFIX}"))
    app.add_handler(CallbackQueryHandler(on_points_self_callback, pattern=f"^{POINTS_SELF_CALLBACK_PREFIX}"))
    app.add_handler(CallbackQueryHandler(on_join_verify_callback, pattern=f"^{VERIFY_CALLBACK_PREFIX}"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_members))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & (~filters.COMMAND), on_private_text))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), on_group_message))
    register_inspection_job(app)
    register_lottery_job(app)
    app.post_init = _register_bot_commands
    return app
