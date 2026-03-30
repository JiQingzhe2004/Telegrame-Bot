from __future__ import annotations

import logging
from datetime import timezone

from telegram import Chat, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.ai.redact import redact_pii
from bot.domain.models import ChatRef, MessageRef, ModerationContext, UserRef
from bot.domain.moderation import Enforcer, ModerationService
from bot.storage.repo import BotRepository
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
from bot.telegram.permissions import get_permission_snapshot
from bot.utils.time import utc_now

logger = logging.getLogger(__name__)


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
) -> Application:
    app = ApplicationBuilder().token(bot_token).build()
    app.bot_data["repo"] = repo
    app.bot_data["moderation_service"] = moderation_service
    app.bot_data["enforcer"] = enforcer

    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("config", config_cmd))
    app.add_handler(CommandHandler("ai", ai_cmd))
    app.add_handler(CommandHandler("threshold", threshold_cmd))
    app.add_handler(CommandHandler("banword", banword_cmd))
    app.add_handler(CommandHandler("whitelist", whitelist_cmd))
    app.add_handler(CommandHandler("forgive", forgive_cmd))
    app.add_handler(CommandHandler("appeal", appeal_cmd))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), on_group_message))
    return app
