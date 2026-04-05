from __future__ import annotations

import json
from typing import Any

from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.domain.models import ChatRef
from bot.points_service import PointsService
from bot.telegram.permissions import is_admin
from bot.title_redemption_service import (
    TITLE_MODE_CUSTOM,
    TITLE_STATUS_PENDING_INPUT,
    TitleRedemptionService,
    parse_redemption_payload,
    parse_title_shop_meta,
    validate_custom_title,
)


POINTS_SELF_CALLBACK_PREFIX = "points:self:"
USER_FLOW_CALLBACK_PREFIX = "ux:"

USER_ACTION_HOME = "home"
USER_ACTION_HELP = "help"
USER_ACTION_POINTS = "points"
USER_ACTION_TASKS = "tasks"
USER_ACTION_SHOP = "shop"
USER_ACTION_CHECKIN = "checkin"
USER_ACTION_PAY = "pay"

TRANSFER_STEP_TARGET = "target"
TRANSFER_STEP_AMOUNT = "amount"
TRANSFER_STEP_CONFIRM = "confirm"


def _repo(ctx: ContextTypes.DEFAULT_TYPE):
    return ctx.application.bot_data["repo"]


def _points_service(ctx: ContextTypes.DEFAULT_TYPE):
    service = ctx.application.bot_data.get("points_service")
    if service is None:
        service = PointsService(_repo(ctx))
        ctx.application.bot_data["points_service"] = service
    return service


def _title_service(ctx: ContextTypes.DEFAULT_TYPE) -> TitleRedemptionService:
    return TitleRedemptionService(_repo(ctx), ctx.bot)


def _reply_target(update: Update):
    effective = getattr(update, "effective_message", None)
    if effective is not None and hasattr(effective, "reply_text"):
        return effective
    return getattr(update, "message", None) or effective


def _session_store(context: ContextTypes.DEFAULT_TYPE) -> dict[str, dict[str, Any]]:
    bucket = context.application.bot_data.get("user_sessions")
    if not isinstance(bucket, dict):
        bucket = {}
        context.application.bot_data["user_sessions"] = bucket
    return bucket


def _session(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> dict[str, Any]:
    key = str(user_id)
    bucket = _session_store(context)
    if key not in bucket or not isinstance(bucket[key], dict):
        bucket[key] = {}
    return bucket[key]


def _display_name(first_name: str | None, last_name: str | None, username: str | None, fallback: str | int) -> str:
    return " ".join(x for x in [first_name, last_name] if x).strip() or username or str(fallback)


def _bot_username(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    username = getattr(context.bot, "username", None)
    if username:
        return str(username).lstrip("@")
    return None


def _deep_link(context: ContextTypes.DEFAULT_TYPE, payload: str) -> str | None:
    username = _bot_username(context)
    if not username:
        return None
    return f"https://t.me/{username}?start={payload}"


def _private_nav_markup(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for row in rows:
        keyboard.append([InlineKeyboardButton(label, callback_data=data) for label, data in row])
    return InlineKeyboardMarkup(keyboard)


def _group_entry_markup(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    primary_label: str = "打开个人中心",
    action: str = USER_ACTION_HOME,
    include_points_button: bool = False,
    user_id: int | None = None,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    payload = f"{action}_{chat_id}"
    url = _deep_link(context, payload)
    first_row: list[InlineKeyboardButton] = []
    if url:
        first_row.append(InlineKeyboardButton(primary_label, url=url))
    if include_points_button and user_id is not None:
        first_row.append(
            InlineKeyboardButton(
                "直接发积分",
                callback_data=f"{POINTS_SELF_CALLBACK_PREFIX}{chat_id}:{user_id}",
            )
        )
    if first_row:
        buttons.append(first_row)
    return InlineKeyboardMarkup(buttons) if buttons else InlineKeyboardMarkup([])


def points_entry_markup(chat_id: int, user_id: int, *, open_center: bool = False) -> InlineKeyboardMarkup:
    first_row = [InlineKeyboardButton("查看我的积分", callback_data=f"{POINTS_SELF_CALLBACK_PREFIX}{chat_id}:{user_id}")]
    if open_center:
        first_row.append(InlineKeyboardButton("个人中心", callback_data=f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{chat_id}"))
    return InlineKeyboardMarkup([first_row])


def _active_chat(session: dict[str, Any]) -> tuple[int | None, str | None]:
    chat_id = session.get("recent_chat_id")
    try:
        chat_id = int(chat_id) if chat_id is not None else None
    except (TypeError, ValueError):
        chat_id = None
    return chat_id, session.get("recent_chat_title")


def _set_active_chat(session: dict[str, Any], chat_id: int, chat_title: str | None) -> None:
    session["recent_chat_id"] = int(chat_id)
    session["recent_chat_title"] = chat_title or "当前群聊"


def _clear_transfer_state(session: dict[str, Any]) -> None:
    session.pop("transfer", None)


def _set_pending_custom_title(session: dict[str, Any], *, redemption_id: int, chat_id: int) -> None:
    session["pending_custom_title"] = {"redemption_id": int(redemption_id), "chat_id": int(chat_id)}


def _clear_pending_custom_title(session: dict[str, Any]) -> None:
    session.pop("pending_custom_title", None)


def _remember_group_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return
    chat = update.effective_chat
    if chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        return
    _repo(context).upsert_chat(ChatRef(chat_id=chat.id, type=chat.type, title=chat.title))
    if update.effective_user:
        _set_active_chat(_session(context, update.effective_user.id), chat.id, chat.title)


def _points_private_message(balance: dict, chat_title: str | None) -> str:
    display_name = _display_name(
        balance.get("first_name"),
        balance.get("last_name"),
        balance.get("username"),
        balance["user_id"],
    )
    return (
        f"我的积分\n"
        f"群聊：{chat_title or balance['chat_id']}\n"
        f"用户：{display_name}\n"
        f"当前余额：{balance['balance']}\n"
        f"累计获得：{balance['total_earned']}\n"
        f"累计支出：{balance['total_spent']}\n"
        f"最近变更：{balance['last_changed_at']}\n\n"
        f"你也可以继续查看任务、商城或发起转账。"
    )


def _render_home_text(session: dict[str, Any]) -> str:
    chat_id, chat_title = _active_chat(session)
    if chat_id is None:
        return (
            "个人中心\n"
            "先在目标群里使用一次积分相关功能，我就能把那个群设为当前操作上下文。\n\n"
            "准备好后，你可以回来继续查看积分、任务、商城和转账。"
        )
    return (
        "个人中心\n"
        f"当前群聊：{chat_title or chat_id}\n\n"
        "接下来想做什么？直接点下面的按钮就行。"
    )


def _home_markup(session: dict[str, Any]) -> InlineKeyboardMarkup:
    chat_id, _ = _active_chat(session)
    suffix = str(chat_id) if chat_id is not None else "0"
    return _private_nav_markup(
        [
            [
                ("我的积分", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_POINTS}:{suffix}"),
                ("今日任务", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_TASKS}:{suffix}"),
            ],
            [
                ("每日签到", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_CHECKIN}:{suffix}"),
                ("积分商城", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_SHOP}:{suffix}:0"),
            ],
            [
                ("转账积分", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_PAY}:start:{suffix}"),
                ("使用说明", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HELP}:{suffix}"),
            ],
        ]
    )


def _help_text() -> str:
    return (
        "使用说明\n"
        "1. 群里发 /points、/tasks、/shop、/pay 时，我会把详情引导到这里。\n"
        "2. 在这里可以直接点按钮查看积分、任务、商城，或发起转账。\n"
        "3. 如果你换了群，先在那个群里触发一次相关功能，我就会切换当前上下文。"
    )


def _help_markup(session: dict[str, Any]) -> InlineKeyboardMarkup:
    chat_id, _ = _active_chat(session)
    suffix = str(chat_id) if chat_id is not None else "0"
    return _private_nav_markup([[("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{suffix}")]])


def _task_lines(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["今日任务"]
    for row in rows:
        status = "已完成" if row["completed"] else f"{row['progress_value']}/{row['target_value']}"
        lines.append(f"- {row['title']}：{status}，奖励 {row['reward_points']} 积分")
    return lines


def _shop_list_text(items: list[dict[str, Any]], chat_title: str | None) -> str:
    lines = [f"积分商城 - {chat_title or '当前群聊'}", "选择一个商品查看详情并确认兑换。"]
    for item in items:
        if not item.get("enabled"):
            continue
        stock = "无限" if item.get("stock") in {None, ""} else item["stock"]
        lines.append(f"- {item['title']}｜{item['price_points']} 积分｜库存 {stock}")
    return "\n".join(lines)


def _shop_list_markup(chat_id: int, items: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for item in items:
        if not item.get("enabled"):
            continue
        rows.append([(item["title"], f"{USER_FLOW_CALLBACK_PREFIX}shop:item:{chat_id}:{item['item_key']}")])
    rows.append(
        [
            ("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{chat_id}"),
            ("刷新商城", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_SHOP}:{chat_id}:0"),
        ]
    )
    return _private_nav_markup(rows)


def _shop_item_text(item: dict[str, Any], balance: dict[str, Any], chat_title: str | None) -> str:
    stock = "无限" if item.get("stock") in {None, ""} else item["stock"]
    extra = ""
    if str(item.get("item_type")) == "leaderboard_title":
        meta = parse_title_shop_meta(item)
        mode_text = "用户自定义头衔" if meta["title_mode"] == TITLE_MODE_CUSTOM else f"固定头衔：{meta['fixed_title']}"
        auto_text = "自动审批" if meta["auto_approve"] else "人工审批"
        extra = f"\n头衔模式：{mode_text}\n审批方式：{auto_text}"
    return (
        f"商品详情 - {chat_title or '当前群聊'}\n"
        f"名称：{item['title']}\n"
        f"价格：{item['price_points']} 积分\n"
        f"库存：{stock}\n"
        f"说明：{item.get('description') or '暂无说明'}\n"
        f"{extra}\n"
        f"你当前余额：{balance['balance']}"
    )


def _resolve_pending_custom_title_redemption(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> dict[str, Any] | None:
    session = _session(context, user_id)
    pending = session.get("pending_custom_title")
    if isinstance(pending, dict):
        try:
            redemption_id = int(pending.get("redemption_id", 0))
        except (TypeError, ValueError):
            redemption_id = 0
        if redemption_id:
            row = _repo(context).get_redemption(redemption_id)
            if row and str(row.get("status")) == TITLE_STATUS_PENDING_INPUT:
                return row
    candidates = _repo(context).list_pending_custom_title_redemptions(user_id)
    pending_rows = [row for row in candidates if str(row.get("status")) == TITLE_STATUS_PENDING_INPUT]
    return pending_rows[0] if len(pending_rows) == 1 else None


async def _title_redeem_feedback(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: int,
    chat_id: int,
    redemption: dict[str, Any],
    item: dict[str, Any],
    balance_after: int,
) -> str:
    session = _session(context, user_id)
    meta = parse_title_shop_meta(item)
    if meta["title_mode"] == TITLE_MODE_CUSTOM:
        _set_pending_custom_title(session, redemption_id=int(redemption["id"]), chat_id=chat_id)
        return (
            f"兑换成功\n"
            f"商品：{item['title']}\n"
            f"消耗积分：{item['price_points']}\n"
            f"当前余额：{balance_after}\n\n"
            "请直接在当前私聊窗口发送你想设置的头衔文本。"
        )

    if meta["auto_approve"]:
        applied = await _title_service(context).apply_redemption(int(redemption["id"]))
        if applied.success:
            _clear_pending_custom_title(session)
            return (
                f"兑换成功\n"
                f"商品：{item['title']}\n"
                f"消耗积分：{item['price_points']}\n"
                f"当前余额：{balance_after}\n"
                f"头衔已自动设置为：{parse_title_shop_meta(item)['fixed_title']}"
            )
        return (
            f"兑换已记录\n"
            f"商品：{item['title']}\n"
            f"消耗积分：{item['price_points']}\n"
            f"当前余额：{balance_after}\n"
            f"自动设置头衔失败：{applied.reason}"
        )

    _clear_pending_custom_title(session)
    return (
        f"兑换成功\n"
        f"商品：{item['title']}\n"
        f"消耗积分：{item['price_points']}\n"
        f"当前余额：{balance_after}\n"
        "已提交管理员审批，审批通过后机器人会自动为你设置头衔。"
    )


def _shop_item_markup(chat_id: int, item_key: str) -> InlineKeyboardMarkup:
    return _private_nav_markup(
        [
            [("确认兑换", f"{USER_FLOW_CALLBACK_PREFIX}shop:redeem:{chat_id}:{item_key}")],
            [
                ("返回商城", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_SHOP}:{chat_id}:0"),
                ("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{chat_id}"),
            ],
        ]
    )


def _transfer_intro_text(chat_title: str | None) -> str:
    return (
        f"转账积分\n"
        f"当前群聊：{chat_title or '当前群聊'}\n\n"
        "先把收款人的 @用户名 或用户 ID 发给我。\n"
        "你也可以直接点下面的最近成员按钮。"
    )


def _transfer_intro_markup(chat_id: int, members: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    for row in members[:6]:
        label = _display_name(row.get("first_name"), row.get("last_name"), row.get("username"), row["user_id"])
        rows.append([(label, f"{USER_FLOW_CALLBACK_PREFIX}pay:pick:{chat_id}:{row['user_id']}")])
    rows.append([("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{chat_id}")])
    return _private_nav_markup(rows)


def _transfer_amount_text(chat_title: str | None, target_label: str, min_amount: int) -> str:
    return (
        f"转账积分\n"
        f"当前群聊：{chat_title or '当前群聊'}\n"
        f"收款人：{target_label}\n\n"
        f"现在告诉我要转多少积分。最小金额是 {min_amount}。"
    )


def _transfer_amount_markup(chat_id: int) -> InlineKeyboardMarkup:
    return _private_nav_markup(
        [
            [
                ("5 积分", f"{USER_FLOW_CALLBACK_PREFIX}pay:amount:{chat_id}:5"),
                ("10 积分", f"{USER_FLOW_CALLBACK_PREFIX}pay:amount:{chat_id}:10"),
            ],
            [
                ("20 积分", f"{USER_FLOW_CALLBACK_PREFIX}pay:amount:{chat_id}:20"),
                ("50 积分", f"{USER_FLOW_CALLBACK_PREFIX}pay:amount:{chat_id}:50"),
            ],
            [("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{chat_id}")],
        ]
    )


def _transfer_confirm_text(chat_title: str | None, target_label: str, amount: int, balance: int) -> str:
    return (
        f"确认转账\n"
        f"群聊：{chat_title or '当前群聊'}\n"
        f"收款人：{target_label}\n"
        f"转账积分：{amount}\n"
        f"你的当前余额：{balance}\n\n"
        "确认无误后点击下面的按钮完成转账。"
    )


def _transfer_confirm_markup(chat_id: int, target_user_id: int, amount: int) -> InlineKeyboardMarkup:
    return _private_nav_markup(
        [
            [("确认转账", f"{USER_FLOW_CALLBACK_PREFIX}pay:confirm:{chat_id}:{target_user_id}:{amount}")],
            [
                ("重新选择金额", f"{USER_FLOW_CALLBACK_PREFIX}pay:edit_amount:{chat_id}"),
                ("取消转账", f"{USER_FLOW_CALLBACK_PREFIX}pay:cancel:{chat_id}"),
            ],
        ]
    )


def _product_error(text: str, *, chat_id: int | None = None) -> tuple[str, InlineKeyboardMarkup | None]:
    if chat_id is None:
        return text, None
    return text, _private_nav_markup([[("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{chat_id}")]])


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
                f"积分到账通知\n"
                f"群聊：{chat_title or '-'}\n"
                f"来自：{from_user_label}\n"
                f"到账积分：{amount}\n"
                f"当前余额：{balance_after}"
            ),
        )
    except TelegramError:
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
        return True, "积分明细已私聊发送，去个人中心还能继续看任务和商城。"
    except TelegramError:
        return False, "我暂时没法主动私聊你。请先手动打开机器人私聊窗口并发送 /start，再回来继续。"


async def _send_or_edit_user_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    markup: InlineKeyboardMarkup | None,
) -> None:
    query = getattr(update, "callback_query", None)
    if query:
        try:
            await query.edit_message_text(text=text, reply_markup=markup)
            return
        except TelegramError:
            pass
        if update.effective_chat:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=markup)
            return
    target = _reply_target(update)
    if target:
        await target.reply_text(text, reply_markup=markup)


async def _send_private_page(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    text: str,
    markup: InlineKeyboardMarkup | None,
) -> bool:
    try:
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=markup)
        return True
    except TelegramError:
        return False


def _resolve_chat_context(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    explicit_chat_id: int | None = None,
) -> tuple[int | None, str | None, dict[str, Any]]:
    if not update.effective_user:
        return None, None, {}
    session = _session(context, update.effective_user.id)
    if explicit_chat_id is not None:
        chat = _repo(context).get_chat(explicit_chat_id)
        _set_active_chat(session, explicit_chat_id, chat["title"] if chat else None)
        return explicit_chat_id, session.get("recent_chat_title"), session
    if update.effective_chat and update.effective_chat.type in {Chat.GROUP, Chat.SUPERGROUP}:
        _remember_group_chat(update, context)
        return update.effective_chat.id, update.effective_chat.title, session
    chat_id, chat_title = _active_chat(session)
    return chat_id, chat_title, session


async def _render_home(update: Update, context: ContextTypes.DEFAULT_TYPE, *, chat_id: int | None = None) -> None:
    _, _, session = _resolve_chat_context(update, context, explicit_chat_id=chat_id)
    await _send_or_edit_user_view(update, context, text=_render_home_text(session), markup=_home_markup(session))


async def _render_help(update: Update, context: ContextTypes.DEFAULT_TYPE, *, chat_id: int | None = None) -> None:
    _, _, session = _resolve_chat_context(update, context, explicit_chat_id=chat_id)
    await _send_or_edit_user_view(update, context, text=_help_text(), markup=_help_markup(session))


async def _render_points_page(update: Update, context: ContextTypes.DEFAULT_TYPE, *, chat_id: int | None = None) -> None:
    resolved_chat_id, chat_title, session = _resolve_chat_context(update, context, explicit_chat_id=chat_id)
    if not resolved_chat_id or not update.effective_user:
        text, markup = _product_error("这里是机器人私聊窗口。先去群里发一次 /points，我就能把对应群聊绑定到这里。")
        await _send_or_edit_user_view(update, context, text=text, markup=markup)
        return
    balance = _repo(context).get_points_balance(resolved_chat_id, update.effective_user.id)
    await _send_or_edit_user_view(
        update,
        context,
        text=_points_private_message(balance, chat_title),
        markup=_private_nav_markup(
            [[("查看任务", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_TASKS}:{resolved_chat_id}")], [("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{resolved_chat_id}")]]
        ),
    )
    session["current_page"] = USER_ACTION_POINTS


async def _render_tasks_page(update: Update, context: ContextTypes.DEFAULT_TYPE, *, chat_id: int | None = None) -> None:
    resolved_chat_id, _, session = _resolve_chat_context(update, context, explicit_chat_id=chat_id)
    if not resolved_chat_id or not update.effective_user:
        text, markup = _product_error("还没有可用的群聊上下文。先去群里发一次 /tasks，再回来查看。")
        await _send_or_edit_user_view(update, context, text=text, markup=markup)
        return
    rows = _points_service(context).list_tasks_for_user(resolved_chat_id, update.effective_user.id)
    await _send_or_edit_user_view(
        update,
        context,
        text="\n".join(_task_lines(rows)),
        markup=_private_nav_markup(
            [
                [("去签到", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_CHECKIN}:{resolved_chat_id}")],
                [("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{resolved_chat_id}")],
            ]
        ),
    )
    session["current_page"] = USER_ACTION_TASKS


async def _render_shop_page(update: Update, context: ContextTypes.DEFAULT_TYPE, *, chat_id: int | None = None) -> None:
    resolved_chat_id, chat_title, session = _resolve_chat_context(update, context, explicit_chat_id=chat_id)
    if not resolved_chat_id:
        text, markup = _product_error("还没有可用的群聊上下文。先去群里发一次 /shop，再回来查看。")
        await _send_or_edit_user_view(update, context, text=text, markup=markup)
        return
    items = _points_service(context).list_shop(resolved_chat_id)
    enabled_items = [item for item in items if item.get("enabled")]
    if not enabled_items:
        text, markup = _product_error("这个群当前没有可兑换商品。", chat_id=resolved_chat_id)
        await _send_or_edit_user_view(update, context, text=text, markup=markup)
        return
    await _send_or_edit_user_view(
        update,
        context,
        text=_shop_list_text(enabled_items, chat_title),
        markup=_shop_list_markup(resolved_chat_id, enabled_items),
    )
    session["current_page"] = USER_ACTION_SHOP


async def _render_shop_item(update: Update, context: ContextTypes.DEFAULT_TYPE, *, chat_id: int, item_key: str) -> None:
    _, chat_title, _ = _resolve_chat_context(update, context, explicit_chat_id=chat_id)
    if not update.effective_user:
        return
    _points_service(context).ensure_defaults(chat_id)
    item = _repo(context).get_shop_item(chat_id, item_key)
    if not item or not item.get("enabled"):
        text, markup = _product_error("这个商品现在不能兑换了，你可以返回商城看看别的商品。", chat_id=chat_id)
        await _send_or_edit_user_view(update, context, text=text, markup=markup)
        return
    balance = _repo(context).get_points_balance(chat_id, update.effective_user.id)
    await _send_or_edit_user_view(
        update,
        context,
        text=_shop_item_text(item, balance, chat_title),
        markup=_shop_item_markup(chat_id, item_key),
    )


def _build_checkin_detail(result: dict[str, Any]) -> str:
    lines = [
        "签到详情",
        f"本次奖励：{result['reward_points']} 积分",
        f"连续签到：{result['streak_days']} 天",
        f"当前余额：{result['balance_after']}",
    ]
    for reward in result.get("task_rewards", []):
        lines.append(f"额外完成任务：{reward['task_key']}，再得 {reward['reward_points']} 积分")
    return "\n".join(lines)


async def _execute_checkin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int | None = None,
    from_private: bool = False,
) -> tuple[bool, str]:
    resolved_chat_id, _, _ = _resolve_chat_context(update, context, explicit_chat_id=chat_id)
    if not resolved_chat_id or not update.effective_user:
        return False, "还没有可用的群聊上下文。先去群里发一次 /checkin，再回来操作。"
    settings = _repo(context).get_settings(resolved_chat_id)
    try:
        result = _points_service(context).checkin(resolved_chat_id, update.effective_user.id, settings)
    except ValueError as exc:
        if str(exc) == "already_checked_in_today":
            return False, "你今天已经签到过了，晚点再来看看任务和商城吧。"
        return False, "签到没有成功，请稍后再试。"
    detail = _build_checkin_detail(result)
    if from_private:
        return True, detail
    try:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=detail,
            reply_markup=_private_nav_markup(
                [
                    [("查看任务", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_TASKS}:{resolved_chat_id}")],
                    [("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{resolved_chat_id}")],
                ]
            ),
        )
        return True, "签到成功，详细奖励已经发到你的私聊。"
    except TelegramError:
        return True, "签到成功。先打开机器人私聊发送 /start，下次我就能把详情直接发给你。"


def _resolve_member(repo, chat_id: int, raw_value: str, current_user_id: int) -> tuple[dict[str, Any] | None, str | None]:
    raw_value = raw_value.strip()
    if not raw_value:
        return None, "请先发送收款人的 @用户名 或用户 ID。"
    if raw_value.startswith("@"):
        query = raw_value.lstrip("@")
        candidates = repo.list_chat_members(chat_id, limit=10, query=query)
        exact = [row for row in candidates if (row.get("username") or "").lower() == query.lower()]
        if not exact:
            return None, f"我没有在当前群找到 {raw_value}。你可以重新输入更准确的 @用户名 或用户 ID。"
        if len(exact) > 1:
            return None, "这个用户名匹配到了多个人，请直接发送用户 ID。"
        member = exact[0]
    else:
        try:
            target_user_id = int(raw_value)
        except ValueError:
            return None, "收款人格式不对，请发送 @用户名 或纯数字用户 ID。"
        candidates = repo.list_chat_members(chat_id, limit=10, query=str(target_user_id))
        member = next((row for row in candidates if int(row["user_id"]) == target_user_id), None)
        if member is None:
            member = {
                "user_id": target_user_id,
                "username": None,
                "first_name": None,
                "last_name": None,
            }
    if int(member["user_id"]) == current_user_id:
        return None, "不能给自己转账，换一个收款人吧。"
    return member, None


async def _render_transfer_intro(update: Update, context: ContextTypes.DEFAULT_TYPE, *, chat_id: int | None = None) -> None:
    resolved_chat_id, chat_title, session = _resolve_chat_context(update, context, explicit_chat_id=chat_id)
    if not resolved_chat_id or not update.effective_user:
        text, markup = _product_error("还没有可用的群聊上下文。先去群里发一次 /pay，再回来发起转账。")
        await _send_or_edit_user_view(update, context, text=text, markup=markup)
        return
    settings = _repo(context).get_settings(resolved_chat_id)
    if not settings.points_transfer_enabled:
        text, markup = _product_error("这个群暂时关闭了积分转账功能。", chat_id=resolved_chat_id)
        await _send_or_edit_user_view(update, context, text=text, markup=markup)
        return
    members = [
        row
        for row in _repo(context).list_chat_members(resolved_chat_id, limit=8)
        if int(row["user_id"]) != update.effective_user.id
    ]
    session["transfer"] = {"chat_id": resolved_chat_id, "step": TRANSFER_STEP_TARGET}
    await _send_or_edit_user_view(
        update,
        context,
        text=_transfer_intro_text(chat_title),
        markup=_transfer_intro_markup(resolved_chat_id, members),
    )


async def _render_transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, *, chat_id: int, target_user_id: int) -> None:
    if not update.effective_user:
        return
    session = _session(context, update.effective_user.id)
    candidates = _repo(context).list_chat_members(chat_id, limit=10, query=str(target_user_id))
    member = next((row for row in candidates if int(row["user_id"]) == int(target_user_id)), None)
    if member is None:
        member = {
            "user_id": int(target_user_id),
            "username": None,
            "first_name": None,
            "last_name": None,
        }
    settings = _repo(context).get_settings(chat_id)
    label = _display_name(member.get("first_name"), member.get("last_name"), member.get("username"), member["user_id"])
    session["transfer"] = {
        "chat_id": chat_id,
        "step": TRANSFER_STEP_AMOUNT,
        "target_user_id": int(member["user_id"]),
        "target_label": label,
    }
    chat = _repo(context).get_chat(chat_id)
    await _send_or_edit_user_view(
        update,
        context,
        text=_transfer_amount_text(chat["title"] if chat else None, label, settings.points_transfer_min_amount),
        markup=_transfer_amount_markup(chat_id),
    )


async def _render_transfer_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, *, amount: int) -> None:
    if not update.effective_user:
        return
    session = _session(context, update.effective_user.id)
    transfer = session.get("transfer") or {}
    chat_id = transfer.get("chat_id")
    target_user_id = transfer.get("target_user_id")
    target_label = transfer.get("target_label")
    if not chat_id or not target_user_id or not target_label:
        text, markup = _product_error("转账上下文已经失效，请重新开始。")
        await _send_or_edit_user_view(update, context, text=text, markup=markup)
        _clear_transfer_state(session)
        return
    settings = _repo(context).get_settings(int(chat_id))
    if amount < settings.points_transfer_min_amount:
        await _send_or_edit_user_view(
            update,
            context,
            text=f"最小转账金额是 {settings.points_transfer_min_amount} 积分，你可以重新输入一个更大的数字。",
            markup=_transfer_amount_markup(int(chat_id)),
        )
        return
    balance = _repo(context).get_points_balance(int(chat_id), update.effective_user.id)
    if amount > int(balance["balance"]):
        await _send_or_edit_user_view(
            update,
            context,
            text=f"你当前只有 {balance['balance']} 积分，暂时不够转出 {amount} 积分。可以先签到或做任务攒一攒。",
            markup=_transfer_amount_markup(int(chat_id)),
        )
        return
    transfer["step"] = TRANSFER_STEP_CONFIRM
    transfer["amount"] = amount
    session["transfer"] = transfer
    chat = _repo(context).get_chat(int(chat_id))
    await _send_or_edit_user_view(
        update,
        context,
        text=_transfer_confirm_text(chat["title"] if chat else None, str(target_label), amount, int(balance["balance"])),
        markup=_transfer_confirm_markup(int(chat_id), int(target_user_id), amount),
    )


async def _complete_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE, *, chat_id: int, target_user_id: int, amount: int) -> None:
    if not update.effective_user:
        return
    session = _session(context, update.effective_user.id)
    settings = _repo(context).get_settings(chat_id)
    try:
        result = _points_service(context).transfer_points(
            chat_id,
            update.effective_user.id,
            target_user_id,
            amount,
            settings,
            "telegram_command",
        )
    except ValueError as exc:
        messages = {
            "transfer_amount_must_be_positive": "转账金额要大于 0。",
            "cannot_transfer_to_self": "不能给自己转账。",
            "insufficient_points": "你的积分不足，先去签到或做任务攒一攒吧。",
            "transfer_daily_limit_reached": f"你今天的转账次数已经用完了，上限是 {settings.points_transfer_daily_limit} 次。",
        }
        text, markup = _product_error(messages.get(str(exc), "转账没有成功，请稍后再试。"), chat_id=chat_id)
        await _send_or_edit_user_view(update, context, text=text, markup=markup)
        return
    from_user_label = update.effective_user.full_name or update.effective_user.username or str(update.effective_user.id)
    chat = _repo(context).get_chat(chat_id)
    await _send_private_transfer_notice(
        bot=context.bot,
        chat_title=chat["title"] if chat else None,
        to_user_id=target_user_id,
        from_user_label=from_user_label,
        amount=amount,
        balance_after=result["to"]["balance_after"],
    )
    _clear_transfer_state(session)
    await _send_or_edit_user_view(
        update,
        context,
        text=(
            f"转账成功\n"
            f"转出积分：{amount}\n"
            f"你的当前余额：{result['from']['balance_after']}\n"
            f"对方当前余额：{result['to']['balance_after']}"
        ),
        markup=_private_nav_markup(
            [
                [("继续查看积分", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_POINTS}:{chat_id}")],
                [("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{chat_id}")],
            ]
        ),
    )


def _parse_start_payload(raw_payload: str) -> tuple[str, int | None]:
    payload = raw_payload.strip()
    if "_" not in payload:
        return payload, None
    action, maybe_chat = payload.split("_", 1)
    try:
        return action, int(maybe_chat)
    except ValueError:
        return action, None


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    action = USER_ACTION_HOME
    chat_id: int | None = None
    if update.effective_chat and update.effective_chat.type == Chat.PRIVATE and context.args:
        action, chat_id = _parse_start_payload(context.args[0])
    if action == "nav":
        action = USER_ACTION_HOME
    if action == "points":
        await _render_points_page(update, context, chat_id=chat_id)
        return
    if action == "tasks":
        await _render_tasks_page(update, context, chat_id=chat_id)
        return
    if action == "shop":
        await _render_shop_page(update, context, chat_id=chat_id)
        return
    if action == "pay":
        await _render_transfer_intro(update, context, chat_id=chat_id)
        return
    await _render_home(update, context, chat_id=chat_id)


async def on_user_flow_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    payload = query.data.removeprefix(USER_FLOW_CALLBACK_PREFIX)
    parts = payload.split(":")
    if not parts:
        return
    action = parts[0]
    if action == USER_ACTION_HOME:
        chat_id = int(parts[1]) if len(parts) > 1 and parts[1] not in {"", "0"} else None
        await _render_home(update, context, chat_id=chat_id)
        return
    if action == USER_ACTION_HELP:
        chat_id = int(parts[1]) if len(parts) > 1 and parts[1] not in {"", "0"} else None
        await _render_help(update, context, chat_id=chat_id)
        return
    if action == USER_ACTION_POINTS:
        chat_id = int(parts[1]) if len(parts) > 1 and parts[1] not in {"", "0"} else None
        await _render_points_page(update, context, chat_id=chat_id)
        return
    if action == USER_ACTION_TASKS:
        chat_id = int(parts[1]) if len(parts) > 1 and parts[1] not in {"", "0"} else None
        await _render_tasks_page(update, context, chat_id=chat_id)
        return
    if action == USER_ACTION_CHECKIN:
        chat_id = int(parts[1]) if len(parts) > 1 and parts[1] not in {"", "0"} else None
        success, text = await _execute_checkin(update, context, chat_id=chat_id, from_private=True)
        resolved_chat_id, _, _ = _resolve_chat_context(update, context, explicit_chat_id=chat_id)
        markup = _private_nav_markup([[("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{resolved_chat_id or 0}")]])
        await _send_or_edit_user_view(update, context, text=text, markup=markup if success else markup)
        return
    if action == USER_ACTION_PAY:
        sub_action = parts[1] if len(parts) > 1 else "start"
        if sub_action == "start":
            chat_id = int(parts[2]) if len(parts) > 2 and parts[2] not in {"", "0"} else None
            await _render_transfer_intro(update, context, chat_id=chat_id)
            return
        if sub_action == "pick" and len(parts) >= 4:
            await _render_transfer_amount(update, context, chat_id=int(parts[2]), target_user_id=int(parts[3]))
            return
        if sub_action == "amount" and len(parts) >= 4:
            if not update.effective_user:
                return
            session = _session(context, update.effective_user.id)
            transfer = session.get("transfer") or {}
            transfer["chat_id"] = int(parts[2])
            session["transfer"] = transfer
            await _render_transfer_confirm(update, context, amount=int(parts[3]))
            return
        if sub_action == "edit_amount" and len(parts) >= 3:
            if not update.effective_user:
                return
            session = _session(context, update.effective_user.id)
            transfer = session.get("transfer") or {}
            transfer["step"] = TRANSFER_STEP_AMOUNT
            session["transfer"] = transfer
            chat_id = int(parts[2])
            label = transfer.get("target_label", "收款人")
            settings = _repo(context).get_settings(chat_id)
            chat = _repo(context).get_chat(chat_id)
            await _send_or_edit_user_view(
                update,
                context,
                text=_transfer_amount_text(chat["title"] if chat else None, str(label), settings.points_transfer_min_amount),
                markup=_transfer_amount_markup(chat_id),
            )
            return
        if sub_action == "cancel" and len(parts) >= 3:
            if update.effective_user:
                _clear_transfer_state(_session(context, update.effective_user.id))
            await _render_home(update, context, chat_id=int(parts[2]))
            return
        if sub_action == "confirm" and len(parts) >= 5:
            await _complete_transfer(
                update,
                context,
                chat_id=int(parts[2]),
                target_user_id=int(parts[3]),
                amount=int(parts[4]),
            )
            return
    if action == "shop" and len(parts) >= 4:
        sub_action = parts[1]
        chat_id = int(parts[2])
        item_key = parts[3]
        if sub_action == "item":
            await _render_shop_item(update, context, chat_id=chat_id, item_key=item_key)
            return
        if sub_action == "redeem":
            if not update.effective_user:
                return
            try:
                result = _points_service(context).redeem(chat_id, update.effective_user.id, item_key)
            except ValueError as exc:
                messages = {
                    "shop_item_unavailable": "这个商品现在不可兑换了，你可以返回商城看看别的商品。",
                    "shop_item_out_of_stock": "这个商品已经售罄了。",
                    "insufficient_points": "你的积分还不够兑换这个商品，可以先去签到或做任务。",
                }
                text, markup = _product_error(messages.get(str(exc), "兑换没有成功，请稍后再试。"), chat_id=chat_id)
                await _send_or_edit_user_view(update, context, text=text, markup=markup)
                return
            item = result["item"]
            success_text = (
                await _title_redeem_feedback(
                    context,
                    user_id=update.effective_user.id,
                    chat_id=chat_id,
                    redemption=result["redemption"],
                    item=item,
                    balance_after=result["balance_after"],
                )
                if str(item.get("item_type")) == "leaderboard_title"
                else (
                    f"兑换成功\n"
                    f"商品：{item['title']}\n"
                    f"消耗积分：{item['price_points']}\n"
                    f"当前余额：{result['balance_after']}"
                )
            )
            await _send_or_edit_user_view(
                update,
                context,
                text=success_text,
                markup=_private_nav_markup(
                    [
                        [("继续逛商城", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_SHOP}:{chat_id}:0")],
                        [("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{chat_id}")],
                    ]
                ),
            )
        return
    if action == USER_ACTION_SHOP:
        chat_id = int(parts[1]) if len(parts) > 1 and parts[1] not in {"", "0"} else None
        await _render_shop_page(update, context, chat_id=chat_id)


async def on_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_chat or update.effective_chat.type != Chat.PRIVATE:
        return
    message = _reply_target(update)
    text = (getattr(update.effective_message, "text", None) or "").strip()
    if not text or message is None:
        return
    session = _session(context, update.effective_user.id)
    transfer = session.get("transfer") or {}
    step = transfer.get("step")
    if step == TRANSFER_STEP_TARGET:
        chat_id = transfer.get("chat_id")
        if not chat_id:
            await message.reply_text("转账上下文已经失效了，请重新点一次“转账积分”。")
            return
        member, error = _resolve_member(_repo(context), int(chat_id), text, update.effective_user.id)
        if error:
            members = [row for row in _repo(context).list_chat_members(int(chat_id), limit=6) if int(row["user_id"]) != update.effective_user.id]
            await message.reply_text(error, reply_markup=_transfer_intro_markup(int(chat_id), members))
            return
        await _render_transfer_amount(update, context, chat_id=int(chat_id), target_user_id=int(member["user_id"]))
        return
    pending_candidates = [
        row for row in _repo(context).list_pending_custom_title_redemptions(update.effective_user.id) if str(row.get("status")) == TITLE_STATUS_PENDING_INPUT
    ]
    if len(pending_candidates) > 1:
        await message.reply_text("你有多条待填写的头衔兑换，请回到对应商品兑换入口后再继续填写。")
        return
    pending_title = pending_candidates[0] if pending_candidates else _resolve_pending_custom_title_redemption(context, update.effective_user.id)
    if pending_title is not None:
        try:
            requested = validate_custom_title(text)
        except ValueError as exc:
            messages = {
                "missing_custom_title": "头衔不能为空，请重新发送。",
                "custom_title_too_long": "头衔长度不能超过 16 个字符，请重新发送。",
            }
            await message.reply_text(messages.get(str(exc), "头衔格式不正确，请重新发送。"))
            return
        updated = _title_service(context).submit_custom_title(int(pending_title["id"]), requested)
        if updated is None:
            await message.reply_text("这条头衔兑换记录已经失效了，请重新购买。")
            return
        payload = parse_redemption_payload(updated)
        meta = parse_title_shop_meta(pending_title)
        if bool(meta["auto_approve"]):
            applied = await _title_service(context).apply_redemption(int(updated["id"]))
            _clear_pending_custom_title(_session(context, update.effective_user.id))
            if applied.success:
                await message.reply_text(f"头衔已提交并自动生效：{requested}")
            else:
                await message.reply_text(f"头衔已提交，但自动设置失败：{applied.reason}")
            return
        _clear_pending_custom_title(_session(context, update.effective_user.id))
        await message.reply_text(
            f"头衔申请已提交：{payload['requested_title']}\n管理员审批通过后，机器人会自动为你设置头衔。"
        )
        return
    if step == TRANSFER_STEP_AMOUNT:
        try:
            amount = int(text)
        except ValueError:
            await message.reply_text("金额要填整数，比如 5、10、20。", reply_markup=_transfer_amount_markup(int(transfer.get("chat_id", 0))))
            return
        await _render_transfer_confirm(update, context, amount=amount)
        return
    await _render_home(update, context)


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
        await update.message.reply_text("用法：/ai on|off")
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
        await update.message.reply_text("用法：/threshold <0-1>")
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
        await update.message.reply_text("用法：/banword add|del <词>")
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
        await update.message.reply_text("用法：/whitelist add|del <@用户名|用户ID>")
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
        await update.message.reply_text("用法：/forgive <用户ID>")
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
        await update.message.reply_text("用法：/appeal <申诉理由>")
        return
    aid = _repo(context).add_appeal(update.effective_chat.id, update.effective_user.id, reason)
    await update.message.reply_text(f"appeal logged: {aid}")


async def points_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if update.effective_chat.type == Chat.PRIVATE:
        await _render_points_page(update, context)
        return
    if update.effective_chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        return
    _remember_group_chat(update, context)
    success, notice = await _send_private_points(
        bot=context.bot,
        repo=_repo(context),
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id,
        username=_bot_username(context),
        chat_title=update.effective_chat.title,
    )
    markup = _group_entry_markup(
        context,
        chat_id=update.effective_chat.id,
        primary_label="打开个人中心",
        action=USER_ACTION_POINTS,
        include_points_button=not success,
        user_id=update.effective_user.id,
    )
    await update.message.reply_text(notice, reply_markup=markup)


async def rank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return
    _remember_group_chat(update, context)
    rows = _repo(context).list_points_leaderboard(update.effective_chat.id, limit=10)
    if not rows:
        await update.message.reply_text("这个群还没有积分记录，先去签到或发言试试看。")
        return
    lines = ["积分排行榜（前 10）"]
    for idx, row in enumerate(rows, start=1):
        display_name = _display_name(row.get("first_name"), row.get("last_name"), row.get("username"), row["user_id"])
        lines.append(f"{idx}. {display_name}：{row['balance']}")
    lines.append("")
    lines.append("想看你自己的明细，可以点下面的按钮。")
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=_group_entry_markup(
            context,
            chat_id=update.effective_chat.id,
            primary_label="打开个人中心",
            action=USER_ACTION_HOME,
            include_points_button=bool(update.effective_user),
            user_id=update.effective_user.id if update.effective_user else None,
        ),
    )


async def pay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if update.effective_chat.type == Chat.PRIVATE:
        if len(context.args) >= 2:
            chat_id, _, session = _resolve_chat_context(update, context)
            if not chat_id:
                await update.message.reply_text("还没有可用的群聊上下文。先去群里发一次 /pay，再回来继续。")
                return
            member, error = _resolve_member(_repo(context), chat_id, context.args[0], update.effective_user.id)
            if error or member is None:
                await update.message.reply_text(error or "没有找到这个收款人。")
                return
            session["transfer"] = {
                "chat_id": chat_id,
                "target_user_id": int(member["user_id"]),
                "target_label": _display_name(member.get("first_name"), member.get("last_name"), member.get("username"), member["user_id"]),
                "step": TRANSFER_STEP_CONFIRM,
            }
            try:
                amount = int(context.args[1])
            except ValueError:
                await update.message.reply_text("金额要填整数，比如 5、10、20。")
                return
            await _render_transfer_confirm(update, context, amount=amount)
            return
        await _render_transfer_intro(update, context)
        return
    _remember_group_chat(update, context)
    if len(context.args) >= 2:
        raw_target = context.args[0].strip()
        try:
            amount = int(context.args[1])
        except ValueError:
            await update.message.reply_text("金额要填整数，比如 /pay 123456 10。")
            return
        settings = _repo(context).get_settings(update.effective_chat.id)
        if not settings.points_transfer_enabled:
            await update.message.reply_text("这个群暂时关闭了积分转账功能。")
            return
        member, error = _resolve_member(_repo(context), update.effective_chat.id, raw_target, update.effective_user.id)
        if error or member is None:
            await update.message.reply_text(error or "没有找到这个收款人。")
            return
        try:
            result = _points_service(context).transfer_points(
                update.effective_chat.id,
                update.effective_user.id,
                int(member["user_id"]),
                amount,
                settings,
                "telegram_command",
            )
        except ValueError as exc:
            messages = {
                "transfer_amount_must_be_positive": "转账金额要大于 0。",
                "cannot_transfer_to_self": "不能给自己转账。",
                "insufficient_points": "你的积分不足，先去签到或做任务攒一攒吧。",
                "transfer_daily_limit_reached": f"你今天的转账次数已经用完了，上限是 {settings.points_transfer_daily_limit} 次。",
            }
            await update.message.reply_text(messages.get(str(exc), "转账没有成功，请稍后再试。"))
            return
        from_user_label = update.effective_user.full_name or update.effective_user.username or str(update.effective_user.id)
        await _send_private_transfer_notice(
            bot=context.bot,
            chat_title=update.effective_chat.title,
            to_user_id=int(member["user_id"]),
            from_user_label=from_user_label,
            amount=amount,
            balance_after=result["to"]["balance_after"],
        )
        await update.message.reply_text(
            f"转账成功，已转出 {amount} 积分。你的当前余额：{result['from']['balance_after']}。",
            reply_markup=_group_entry_markup(
                context,
                chat_id=update.effective_chat.id,
                primary_label="继续在私聊操作",
                action=USER_ACTION_PAY,
            ),
        )
        return
    await update.message.reply_text(
        "转账我已经切到私聊里处理了，点下面按钮就能一步步完成。",
        reply_markup=_group_entry_markup(
            context,
            chat_id=update.effective_chat.id,
            primary_label="打开转账向导",
            action=USER_ACTION_PAY,
        ),
    )


async def points_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    _remember_group_chat(update, context)
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("用法：/points_add <用户ID> <积分数量>")
        return
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("用户 ID 和积分数量都必须是整数。")
        return
    if amount <= 0:
        await update.message.reply_text("加分数量必须大于 0。")
        return
    result = _repo(context).adjust_points(
        chat_id=update.effective_chat.id,
        user_id=user_id,
        amount=amount,
        event_type="admin_adjust",
        operator="telegram_admin",
        reason="admin_add",
    )
    await update.message.reply_text(f"加分成功\n调整积分：+{amount}\n当前余额：{result['balance_after']}")


async def points_sub_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    _remember_group_chat(update, context)
    if not await is_admin(context.bot, update.effective_chat.id, update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("用法：/points_sub <用户ID> <积分数量>")
        return
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("用户 ID 和积分数量都必须是整数。")
        return
    if amount <= 0:
        await update.message.reply_text("扣分数量必须大于 0。")
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
        if str(exc) == "insufficient_points":
            await update.message.reply_text("积分不足，无法继续扣减。")
        else:
            await update.message.reply_text("扣分失败，请稍后重试。")
        return
    await update.message.reply_text(f"扣分成功\n调整积分：-{amount}\n当前余额：{result['balance_after']}")


async def checkin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if update.effective_chat.type == Chat.PRIVATE:
        success, text = await _execute_checkin(update, context, from_private=True)
        chat_id, _, _ = _resolve_chat_context(update, context)
        markup = _private_nav_markup([[("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{chat_id or 0}")]]) if success else None
        await update.message.reply_text(text, reply_markup=markup)
        return
    if update.effective_chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        await update.message.reply_text("请在群里使用 /checkin 完成签到。")
        return
    _remember_group_chat(update, context)
    success, text = await _execute_checkin(update, context, chat_id=update.effective_chat.id)
    await update.message.reply_text(
        text,
        reply_markup=_group_entry_markup(
            context,
            chat_id=update.effective_chat.id,
            primary_label="打开个人中心",
            action=USER_ACTION_HOME,
        ),
    )


async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if update.effective_chat.type == Chat.PRIVATE:
        await _render_tasks_page(update, context)
        return
    if update.effective_chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        await update.message.reply_text("请在群里使用 /tasks 查看今日任务。")
        return
    _remember_group_chat(update, context)
    rows = _points_service(context).list_tasks_for_user(update.effective_chat.id, update.effective_user.id)
    sent = await _send_private_page(
        context=context,
        user_id=update.effective_user.id,
        text="\n".join(_task_lines(rows)),
        markup=_private_nav_markup(
            [
                [("返回首页", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_HOME}:{update.effective_chat.id}")],
                [("去签到", f"{USER_FLOW_CALLBACK_PREFIX}{USER_ACTION_CHECKIN}:{update.effective_chat.id}")],
            ]
        ),
    )
    notice = "任务详情已经发到你的私聊。" if sent else "先打开机器人私聊发送 /start，我就能把任务详情发给你。"
    await update.message.reply_text(
        notice,
        reply_markup=_group_entry_markup(
            context,
            chat_id=update.effective_chat.id,
            primary_label="打开任务中心",
            action=USER_ACTION_TASKS,
        ),
    )


async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if update.effective_chat.type == Chat.PRIVATE:
        await _render_shop_page(update, context)
        return
    if update.effective_chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        await update.message.reply_text("请在群里使用 /shop 查看可兑换商品。")
        return
    _remember_group_chat(update, context)
    items = [item for item in _points_service(context).list_shop(update.effective_chat.id) if item.get("enabled")]
    if not items:
        await update.message.reply_text("这个群当前没有可兑换商品。")
        return
    sent = await _send_private_page(
        context=context,
        user_id=update.effective_user.id,
        text=_shop_list_text(items, update.effective_chat.title),
        markup=_shop_list_markup(update.effective_chat.id, items),
    )
    notice = "商城已经发到你的私聊，你可以点商品查看详情后再兑换。" if sent else "先打开机器人私聊发送 /start，我就能把商城发给你。"
    await update.message.reply_text(
        notice,
        reply_markup=_group_entry_markup(
            context,
            chat_id=update.effective_chat.id,
            primary_label="打开积分商城",
            action=USER_ACTION_SHOP,
        ),
    )


async def redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.effective_user:
        return
    if update.effective_chat.type == Chat.PRIVATE:
        if not context.args:
            await _render_shop_page(update, context)
            return
        chat_id, _, _ = _resolve_chat_context(update, context)
        if not chat_id:
            await update.message.reply_text("还没有可用的群聊上下文。先去群里发一次 /shop，再回来兑换。")
            return
        await _render_shop_item(update, context, chat_id=chat_id, item_key=context.args[0].strip())
        return
    if update.effective_chat.type not in {Chat.GROUP, Chat.SUPERGROUP}:
        await update.message.reply_text("请在群里使用 /redeem 兑换商品。")
        return
    _remember_group_chat(update, context)
    if not context.args:
        await update.message.reply_text(
            "兑换我已经切到私聊里处理了，点下面按钮后选商品就行。",
            reply_markup=_group_entry_markup(
                context,
                chat_id=update.effective_chat.id,
                primary_label="打开积分商城",
                action=USER_ACTION_SHOP,
            ),
        )
        return
    item_key = context.args[0].strip()
    try:
        result = _points_service(context).redeem(update.effective_chat.id, update.effective_user.id, item_key)
    except ValueError as exc:
        messages = {
            "shop_item_unavailable": "这个商品现在不可兑换了。",
            "shop_item_out_of_stock": "这个商品已经售罄了。",
            "insufficient_points": "你的积分还不够兑换这个商品。",
        }
        await update.message.reply_text(messages.get(str(exc), "兑换没有成功，请稍后再试。"))
        return
    item = result["item"]
    if str(item.get("item_type")) == "leaderboard_title":
        meta = parse_title_shop_meta(item)
        if meta["title_mode"] == TITLE_MODE_CUSTOM:
            _set_pending_custom_title(_session(context, update.effective_user.id), redemption_id=int(result["redemption"]["id"]), chat_id=update.effective_chat.id)
            text = (
                f"兑换成功，已兑换 {item['title']}，当前余额：{result['balance_after']}。\n"
                "请立即打开机器人私聊并发送你想设置的头衔文本。"
            )
        elif meta["auto_approve"]:
            applied = await _title_service(context).apply_redemption(int(result["redemption"]["id"]))
            text = (
                f"兑换成功，已兑换 {item['title']}，当前余额：{result['balance_after']}。\n头衔已自动生效。"
                if applied.success
                else f"兑换已记录，当前余额：{result['balance_after']}。\n自动设置头衔失败：{applied.reason}"
            )
        else:
            text = (
                f"兑换成功，已兑换 {item['title']}，当前余额：{result['balance_after']}。\n"
                "已提交管理员审批，审批通过后机器人会自动设置头衔。"
            )
    else:
        text = f"兑换成功，已兑换 {item['title']}，当前余额：{result['balance_after']}。"
    await update.message.reply_text(
        text,
        reply_markup=_group_entry_markup(
            context,
            chat_id=update.effective_chat.id,
            primary_label="继续逛商城",
            action=USER_ACTION_SHOP,
        ),
    )
