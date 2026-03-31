from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

from telegram import Chat, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from bot.ai.redact import redact_pii
from bot.domain.models import ChatRef, MessageRef, ModerationContext, UserRef
from bot.domain.moderation import Enforcer, ModerationService
from bot.storage.repo import BotRepository
from bot.system_config import RuntimeConfig
from bot.telegram.commands import (
    ai_cmd,
    appeal_cmd,
    banword_cmd,
    config_cmd,
    forgive_cmd,
    status_cmd,
    threshold_cmd,
    whitelist_cmd,
)
from bot.telegram.permissions import get_permission_snapshot, is_admin
from bot.utils.time import utc_now
from bot.utils.rate_limit import RaidDetector
from bot.telegram.inspector import register_inspection_job

logger = logging.getLogger(__name__)
VERIFY_CALLBACK_PREFIX = "join_verify:"


def _pending_verifications(application: Application) -> dict[str, dict[str, Any]]:
    bucket = application.bot_data.get("pending_join_verifications")
    if not isinstance(bucket, dict):
        bucket = {}
        application.bot_data["pending_join_verifications"] = bucket
    return bucket


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
) -> str:
    from datetime import datetime, timezone as _tz
    repo: BotRepository | None = context.application.bot_data.get("repo")
    now_hour = datetime.now(tz=_tz.utc).hour
    time_of_day = _get_time_of_day(now_hour)

    # 多模板轮换：从数据库取匹配时段/群类型的模板
    chosen_template = runtime_config.join_welcome_template
    if repo is not None:
        templates = repo.list_welcome_templates(chat_id, hour=now_hour, chat_type=chat_type)
        if templates:
            chosen_template = templates[0]["template"]

    fallback = _render_welcome_template(chosen_template, user_name, chat_title)
    if not runtime_config.join_welcome_use_ai:
        return fallback
    ai_moderator = context.application.bot_data.get("ai_moderator")
    if not isinstance(ai_moderator, OpenAiModerator):
        return fallback
    try:
        return await ai_moderator.generate_welcome(
            chat_title=chat_title or "群聊",
            user_display_name=user_name,
            language="zh",
            template=chosen_template,
            time_of_day=time_of_day,
            chat_type=chat_type,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai welcome generation failed: %s", exc)
        return fallback


def _restricted_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_manage_topics=False,
    )


def _verification_release_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_manage_topics=False,
    )


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
        await context.bot.ban_chat_member(
            chat_id=chat_id, user_id=user_id, until_date=utc_now() + timedelta(minutes=1)
        )
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
        await context.bot.send_message(
            chat_id=chat_id, text=f"用户 {user_id} 未在限时内完成入群验证，已移出群聊。"
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
        try:
            await query.edit_message_text(f"验证通过，欢迎 {query.from_user.full_name}。")
        except TelegramError:
            pass

        if runtime_config.join_welcome_enabled:
            welcome = await _build_welcome_text(
                context,
                runtime_config,
                chat_id=chat_id,
                chat_title=update.effective_chat.title if update.effective_chat else None,
                chat_type=update.effective_chat.type if update.effective_chat else None,
                user_name=query.from_user.full_name,
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
                await query.edit_message_text(
                    f"{query.from_user.full_name} 验证失败次数过多，已被移出群聊。"
                )
            except TelegramError:
                pass
            try:
                await context.bot.ban_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    until_date=utc_now() + timedelta(minutes=1),
                )
                await context.bot.unban_chat_member(
                    chat_id=chat_id, user_id=user_id, only_if_banned=True
                )
            except TelegramError as exc:
                logger.warning(
                    "kick after max attempts failed chat=%s user=%s err=%s", chat_id, user_id, exc
                )
        else:
            remaining = max_attempts - attempts
            await query.answer(f"答案错误，还剩 {remaining} 次机会。", show_alert=True)


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
                    context, runtime_config, chat_id=chat.id, chat_title=chat.title, chat_type=chat.type, user_name=display_name
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
                        context, runtime_config, chat_id=chat.id, chat_title=chat.title, chat_type=chat.type, user_name=display_name
                    )
                    await msg.reply_text(welcome)
                continue

        # 限制发言
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=joined.id,
                permissions=_restricted_permissions(),
            )
        except TelegramError as exc:
            logger.warning(
                "restrict member failed chat=%s user=%s err=%s", chat.id, joined.id, exc
            )

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
                "attempts": 0,
                "question_id": question_data["id"],
                "answer_index": question_data["answer_index"],
                "question_type": "quiz",
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
                "attempts": 0,
                "question_id": None,
                "answer_index": None,
                "question_type": "button",
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
    msg = update.effective_message
    text = msg.text or msg.caption or ""
    if not text:
        return

    repo: BotRepository = context.application.bot_data["repo"]
    service: ModerationService = context.application.bot_data["moderation_service"]
    enforcer: Enforcer = context.application.bot_data["enforcer"]
    runtime_config: RuntimeConfig = context.application.bot_data.get("runtime_config") or RuntimeConfig()

    user = update.effective_user
    if user.is_bot:
        return
    if await is_admin(context.bot, chat.id, user.id):
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

    settings = repo.get_settings(chat.id)
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
        meta={},
    )

    redacted = redact_pii(text)
    repo.save_violation_message(message_ref, redacted)

    ai_moderator: OpenAiModerator | None = context.application.bot_data.get("ai_moderator")
    decision = await service.evaluate(message_ref, mod_context, ai_moderator)

    perms = await get_permission_snapshot(context.bot, chat.id, user.id)
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
    app = ApplicationBuilder().token(bot_token).build()
    app.bot_data["repo"] = repo
    app.bot_data["moderation_service"] = moderation_service
    app.bot_data["enforcer"] = enforcer
    app.bot_data["ai_moderator"] = ai_moderator
    app.bot_data["runtime_config"] = runtime_config or RuntimeConfig()
    app.bot_data["pending_join_verifications"] = {}

    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("config", config_cmd))
    app.add_handler(CommandHandler("ai", ai_cmd))
    app.add_handler(CommandHandler("threshold", threshold_cmd))
    app.add_handler(CommandHandler("banword", banword_cmd))
    app.add_handler(CommandHandler("whitelist", whitelist_cmd))
    app.add_handler(CommandHandler("forgive", forgive_cmd))
    app.add_handler(CommandHandler("appeal", appeal_cmd))
    app.add_handler(CallbackQueryHandler(on_join_verify_callback, pattern=f"^{VERIFY_CALLBACK_PREFIX}"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_members))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), on_group_message))
    register_inspection_job(app)
    return app
