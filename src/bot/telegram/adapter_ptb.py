from __future__ import annotations

import logging
from datetime import timedelta
from datetime import timezone
from typing import Any

from telegram import Chat, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import MessageEntityType
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

from bot.ai.redact import redact_pii
from bot.ai.openai_client import OpenAiModerator
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


async def _build_welcome_text(
    context: ContextTypes.DEFAULT_TYPE,
    runtime_config: RuntimeConfig,
    *,
    chat_title: str | None,
    user_name: str,
) -> str:
    fallback = _render_welcome_template(runtime_config.join_welcome_template, user_name, chat_title)
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
            template=runtime_config.join_welcome_template,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai welcome generation failed: %s", exc)
        return fallback


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
    )


def _verification_lock_permissions() -> ChatPermissions:
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
    store.pop(key, None)
    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id, until_date=utc_now() + timedelta(minutes=1))
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
        await context.bot.send_message(chat_id=chat_id, text=f"用户 {user_id} 未在限时内完成入群验证，已移出群聊。")
    except TelegramError as exc:
        logger.warning("join verification timeout action failed chat=%s user=%s err=%s", chat_id, user_id, exc)


async def on_join_verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    payload = query.data.removeprefix(VERIFY_CALLBACK_PREFIX)
    parts = payload.split(":")
    if len(parts) != 2:
        await query.answer("验证参数错误", show_alert=True)
        return
    try:
        chat_id = int(parts[0])
        user_id = int(parts[1])
    except ValueError:
        await query.answer("验证参数错误", show_alert=True)
        return

    if not query.from_user or query.from_user.id != user_id:
        await query.answer("请由新成员本人点击验证。", show_alert=True)
        return

    runtime_config: RuntimeConfig = context.application.bot_data.get("runtime_config") or RuntimeConfig()
    key = f"{chat_id}:{user_id}"
    store = _pending_verifications(context.application)
    if key not in store:
        await query.answer("验证已失效，请重新入群。", show_alert=True)
        return
    store.pop(key, None)

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=_verification_release_permissions(),
        )
    except TelegramError as exc:
        logger.warning("release member after verify failed chat=%s user=%s err=%s", chat_id, user_id, exc)

    await query.answer("验证成功")
    try:
        await query.edit_message_text(f"验证通过，欢迎 {query.from_user.full_name}。")
    except TelegramError:
        pass

    if runtime_config.join_welcome_enabled:
        welcome = await _build_welcome_text(
            context,
            runtime_config,
            chat_title=update.effective_chat.title if update.effective_chat else None,
            user_name=query.from_user.full_name,
        )
        await context.bot.send_message(chat_id=chat_id, text=welcome)


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

    for joined in members:
        if joined.is_bot:
            continue
        chat_ref = ChatRef(chat_id=chat.id, type=chat.type, title=chat.title)
        user_ref = UserRef(
            user_id=joined.id,
            username=joined.username,
            is_bot=bool(joined.is_bot),
            first_name=joined.first_name,
            last_name=joined.last_name,
        )
        repo.upsert_chat_user(chat_ref, user_ref)
        display_name = joined.full_name or joined.username or str(joined.id)

        if runtime_config.join_verification_enabled:
            try:
                await context.bot.restrict_chat_member(
                    chat_id=chat.id,
                    user_id=joined.id,
                    permissions=_verification_lock_permissions(),
                )
            except TelegramError as exc:
                logger.warning("join verification lock failed chat=%s user=%s err=%s", chat.id, joined.id, exc)
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text="点击完成入群验证", callback_data=f"{VERIFY_CALLBACK_PREFIX}{chat.id}:{joined.id}")]]
            )
            verify_msg = await msg.reply_text(
                f"欢迎 {display_name}，请在 {timeout_seconds} 秒内点击下方按钮完成验证。",
                reply_markup=keyboard,
            )
            key = f"{chat.id}:{joined.id}"
            _pending_verifications(context.application)[key] = {
                "verify_message_id": verify_msg.message_id,
            }
            if context.application.job_queue:
                context.application.job_queue.run_once(
                    _verification_timeout,
                    when=timeout_seconds,
                    data={"chat_id": chat.id, "user_id": joined.id},
                    name=f"join-verify-timeout-{chat.id}-{joined.id}",
                )
            continue

        if runtime_config.join_welcome_enabled:
            welcome = await _build_welcome_text(
                context,
                runtime_config,
                chat_title=chat.title,
                user_name=display_name,
            )
            await msg.reply_text(welcome)


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

    chat_ref = ChatRef(chat_id=chat.id, type=chat.type, title=chat.title)
    user_ref = UserRef(
        user_id=update.effective_user.id,
        username=update.effective_user.username,
        is_bot=bool(update.effective_user.is_bot),
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name,
    )
    repo.upsert_chat_user(chat_ref, user_ref)

    # 管理员 @机器人 时，自动回显 Chat ID，方便前端自动选择。
    if text and msg.entities:
        me = context.application.bot_data.get("bot_me")
        if me is None:
            me = await context.bot.get_me()
            context.application.bot_data["bot_me"] = me
        mention_name = (me.username or "").lower()
        mentioned = False
        for entity in msg.entities:
            if entity.type == MessageEntityType.MENTION:
                token = text[entity.offset : entity.offset + entity.length].strip().lstrip("@").lower()
                if token == mention_name:
                    mentioned = True
                    break
        if mentioned and await is_admin(context.bot, chat.id, user_ref.user_id):
            await msg.reply_text(f"当前群 Chat ID: {chat.id}")
    settings = repo.get_settings(chat.id)
    whitelist_hit = repo.is_whitelisted(chat.id, user_ref.user_id, user_ref.username)
    strike_score = repo.get_strike_score(chat.id, user_ref.user_id)
    recent = repo.recent_texts(chat.id, user_ref.user_id, limit=6)
    if text:
        recent.insert(0, text)
    blacklist_words = repo.get_blacklist_words(chat.id)
    message_ref = MessageRef(
        chat_id=chat.id,
        message_id=msg.message_id,
        user_id=user_ref.user_id,
        date=msg.date if msg.date.tzinfo else msg.date.replace(tzinfo=timezone.utc),
        text=text,
        meta={
            "has_entities": bool(msg.entities),
            "has_photo": bool(msg.photo),
            "has_document": bool(msg.document),
            "received_at": utc_now().isoformat(),
        },
    )

    mctx = ModerationContext(
        chat=chat_ref,
        user=user_ref,
        settings=settings,
        strike_score=strike_score,
        whitelist_hit=whitelist_hit,
        blacklist_words=blacklist_words,
        recent_message_texts=recent,
    )
    decision = await service.decide(message_ref, mctx)
    repo.save_decision(message_ref, decision)

    # 默认仅保存违规样本
    if decision.final_level > 0:
        repo.save_violation_message(message_ref, redact_pii(text))
        repo.add_strike(chat.id, user_ref.user_id, inc=1)

    perms = await get_permission_snapshot(context.bot, chat.id)
    enforcement = await enforcer.apply(context.bot, message_ref, decision, perms)
    if enforcement.applied_action != "none":
        repo.save_enforcement(message_ref, enforcement)


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
    return app
