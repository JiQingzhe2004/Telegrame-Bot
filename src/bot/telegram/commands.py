from __future__ import annotations

import json

from telegram import Update
from telegram.ext import ContextTypes

from bot.telegram.permissions import is_admin


def _repo(ctx: ContextTypes.DEFAULT_TYPE):
    return ctx.application.bot_data["repo"]


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    summary = _repo(context).status_summary()
    await update.message.reply_text(json.dumps(summary, ensure_ascii=False))


async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    settings = _repo(context).get_settings(update.effective_chat.id)
    await update.message.reply_text(json.dumps(settings.__dict__, ensure_ascii=False))


async def ai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("usage: /ai on|off")
        return
    enabled = context.args[0].lower() == "on"
    _repo(context).update_settings(update.effective_chat.id, {"ai_enabled": enabled})
    await update.message.reply_text(f"ai_enabled={enabled}")


async def threshold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("usage: /threshold <0-1>")
        return
    v = max(0.0, min(1.0, float(context.args[0])))
    _repo(context).update_settings(update.effective_chat.id, {"ai_threshold": v})
    await update.message.reply_text(f"ai_threshold={v}")


async def banword_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    if len(context.args) < 2 or context.args[0] not in {"add", "del"}:
        await update.message.reply_text("usage: /banword add|del <word>")
        return
    op, word = context.args[0], " ".join(context.args[1:]).strip()
    if op == "add":
        _repo(context).add_list_item("blacklists", update.effective_chat.id, "word", word)
    else:
        _repo(context).delete_list_item("blacklists", update.effective_chat.id, "word", word)
    await update.message.reply_text(f"banword {op}: {word}")


async def whitelist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    if len(context.args) < 2 or context.args[0] not in {"add", "del"}:
        await update.message.reply_text("usage: /whitelist add|del <@user|user_id>")
        return
    op, value = context.args[0], context.args[1]
    if op == "add":
        _repo(context).add_list_item("whitelists", update.effective_chat.id, "user", value)
    else:
        _repo(context).delete_list_item("whitelists", update.effective_chat.id, "user", value)
    await update.message.reply_text(f"whitelist {op}: {value}")


async def forgive_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("usage: /forgive <user_id>")
        return
    uid = int(context.args[0].replace("@", ""))
    _repo(context).forgive(update.effective_chat.id, uid)
    await update.message.reply_text(f"forgiven: {uid}")


async def appeal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    reason = " ".join(context.args).strip() if context.args else ""
    if not reason:
        await update.message.reply_text("usage: /appeal <reason>")
        return
    aid = _repo(context).add_appeal(update.effective_chat.id, update.effective_user.id, reason)
    await update.message.reply_text(f"appeal logged: {aid}")
