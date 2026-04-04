from __future__ import annotations

import json

from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.domain.models import ChatRef
from bot.telegram.permissions import is_admin


def _repo(ctx: ContextTypes.DEFAULT_TYPE):
    return ctx.application.bot_data["repo"]


def _remember_group_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return
    chat = update.effective_chat
    if chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        return
    _repo(context).upsert_chat(ChatRef(chat_id=chat.id, type=chat.type, title=chat.title))


POINTS_SELF_CALLBACK_PREFIX = "points:self:"


def _points_private_message(balance: dict, chat_title: str | None) -> str:
    display_name = " ".join(x for x in [balance.get("first_name"), balance.get("last_name")] if x).strip() or balance.get("username") or str(balance["user_id"])
    return (
        f"你的积分账户\n"
        f"群聊：{chat_title or balance['chat_id']}\n"
        f"用户：{display_name}\n"
        f"当前余额：{balance['balance']}\n"
        f"累计收入：{balance['total_earned']}\n"
        f"累计支出：{balance['total_spent']}\n"
        f"最近变更：{balance['last_changed_at']}"
    )


def points_entry_markup(chat_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("查看我的积分", callback_data=f"{POINTS_SELF_CALLBACK_PREFIX}{chat_id}:{user_id}")]]
    )


async def _send_private_transfer_notice(
    *,
    bot,
    chat_title: str | None,
    to_user_id: int,
    from_user_label: str,
    amount: int,
    balance_after: int,
) -> None:
    try:
        await bot.send_message(
            chat_id=to_user_id,
            text=(
                f"你收到一笔积分转账\n"
                f"群聊：{chat_title or '-'}\n"
                f"来自：{from_user_label}\n"
                f"到账积分：{amount}\n"
                f"当前余额：{balance_after}"
            ),
        )
    except TelegramError:
        # 收款方未开启私聊时，不影响主转账流程
        return


async def _send_private_points(
    *,
    bot,
    repo,
    chat_id: int,
    user_id: int,
    username: str | None,
    chat_title: str | None,
) -> tuple[bool, str]:
    balance = repo.get_points_balance(chat_id, user_id)
    try:
        await bot.send_message(chat_id=user_id, text=_points_private_message(balance, chat_title))
        return True, "已私聊发送，请查看机器人私信。"
    except TelegramError:
        hint = "请先私聊机器人并发送 /start，然后回群里再试。"
        if username:
            hint += f"\n也可以直接打开：t.me/{username}"
        return False, hint


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    await update.effective_message.reply_text(
        "欢迎使用积分机器人。\n"
        "先在群里使用 /points、/rank、/pay 等命令。\n"
        "当你需要私密查看自己的余额时，机器人会把积分详情发送到这个私聊窗口。"
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    _remember_group_chat(update, context)
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    summary = _repo(context).status_summary()
    await update.message.reply_text(json.dumps(summary, ensure_ascii=False))


async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    _remember_group_chat(update, context)
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    settings = _repo(context).get_settings(update.effective_chat.id)
    await update.message.reply_text(json.dumps(settings.__dict__, ensure_ascii=False))


async def ai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    _remember_group_chat(update, context)
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
    _remember_group_chat(update, context)
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
    _remember_group_chat(update, context)
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
    _remember_group_chat(update, context)
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
    _remember_group_chat(update, context)
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
    _remember_group_chat(update, context)
    reason = " ".join(context.args).strip() if context.args else ""
    if not reason:
        await update.message.reply_text("usage: /appeal <reason>")
        return
    aid = _repo(context).add_appeal(update.effective_chat.id, update.effective_user.id, reason)
    await update.message.reply_text(f"appeal logged: {aid}")


async def points_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if update.effective_chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        await update.message.reply_text("请在群里使用 /points，机器人会把余额私聊发给你。")
        return
    _remember_group_chat(update, context)
    success, notice = await _send_private_points(
        bot=context.bot,
        repo=_repo(context),
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id,
        username=context.bot.username if getattr(context.bot, "username", None) else None,
        chat_title=update.effective_chat.title,
    )
    if success:
        await update.message.reply_text(
            notice,
            reply_markup=points_entry_markup(update.effective_chat.id, update.effective_user.id),
        )
    else:
        await update.message.reply_text(notice)


async def rank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return
    _remember_group_chat(update, context)
    rows = _repo(context).list_points_leaderboard(update.effective_chat.id, limit=10)
    if not rows:
        await update.message.reply_text("当前还没有积分记录。")
        return
    lines = ["本群积分排行榜："]
    for idx, row in enumerate(rows, start=1):
        display_name = " ".join(x for x in [row.get("first_name"), row.get("last_name")] if x).strip() or row.get("username") or row["user_id"]
        lines.append(f"{idx}. {display_name} - {row['balance']}")
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=points_entry_markup(update.effective_chat.id, update.effective_user.id) if update.effective_user else None,
    )


async def pay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    _remember_group_chat(update, context)
    settings = _repo(context).get_settings(update.effective_chat.id)
    if not settings.points_transfer_enabled:
        await update.message.reply_text("当前群已关闭积分转账。")
        return
    if len(context.args) < 2:
        await update.message.reply_text("usage: /pay <user_id|@username> <amount>")
        return
    raw_target = context.args[0].strip()
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("amount must be integer")
        return
    if amount < settings.points_transfer_min_amount:
        await update.message.reply_text(f"最小转账金额为 {settings.points_transfer_min_amount}")
        return
    if raw_target.startswith("@"):
        target_value = raw_target
        candidates = _repo(context).list_chat_members(update.effective_chat.id, limit=50, query=raw_target.lstrip("@"))
        target_user_id = next((int(row["user_id"]) for row in candidates if row.get("username") == raw_target.lstrip("@")), None)
        if target_user_id is None:
            await update.message.reply_text(f"未找到用户：{target_value}")
            return
    else:
        try:
            target_user_id = int(raw_target)
        except ValueError:
            await update.message.reply_text("target must be user_id or @username")
            return
    try:
        result = _repo(context).transfer_points(
            chat_id=update.effective_chat.id,
            from_user_id=update.effective_user.id,
            to_user_id=target_user_id,
            amount=amount,
            operator="telegram_command",
            reason="user_transfer",
        )
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    await update.message.reply_text(
        f"转账成功：{amount}\n你的新余额：{result['from']['balance_after']}\n对方余额：{result['to']['balance_after']}",
        reply_markup=points_entry_markup(update.effective_chat.id, update.effective_user.id),
    )
    from_user_label = update.effective_user.full_name or update.effective_user.username or str(update.effective_user.id)
    await _send_private_transfer_notice(
        bot=context.bot,
        chat_title=update.effective_chat.title,
        to_user_id=target_user_id,
        from_user_label=from_user_label,
        amount=amount,
        balance_after=result["to"]["balance_after"],
    )


async def points_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    _remember_group_chat(update, context)
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("usage: /points_add <user_id> <amount>")
        return
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("user_id / amount must be integer")
        return
    if amount <= 0:
        await update.message.reply_text("amount must be positive")
        return
    result = _repo(context).adjust_points(
        chat_id=update.effective_chat.id,
        user_id=user_id,
        amount=amount,
        event_type="admin_adjust",
        operator="telegram_admin",
        reason="admin_add",
    )
    await update.message.reply_text(f"已加分：{amount}，当前余额：{result['balance_after']}")


async def points_sub_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    _remember_group_chat(update, context)
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("usage: /points_sub <user_id> <amount>")
        return
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("user_id / amount must be integer")
        return
    if amount <= 0:
        await update.message.reply_text("amount must be positive")
        return
    try:
        result = _repo(context).adjust_points(
            chat_id=update.effective_chat.id,
            user_id=user_id,
            amount=-amount,
            event_type="admin_adjust",
            operator="telegram_admin",
            reason="admin_sub",
        )
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return
    await update.message.reply_text(f"已扣分：{amount}，当前余额：{result['balance_after']}")
