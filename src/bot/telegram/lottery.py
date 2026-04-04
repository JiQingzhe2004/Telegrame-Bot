from __future__ import annotations

from datetime import datetime
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

from bot.lottery_service import ENTRY_MODE_CONSUME, ENTRY_MODE_FREE, ENTRY_MODE_THRESHOLD, LotteryService
from bot.storage.repo import BotRepository

LOTTERY_CALLBACK_PREFIX = "lottery:"
LOTTERY_JOB_INTERVAL_SECONDS = 30
LOTTERY_CONFIRM_TTL_SECONDS = 300


def _repo(context: ContextTypes.DEFAULT_TYPE) -> BotRepository:
    return context.application.bot_data["repo"]


def _lottery_service(context: ContextTypes.DEFAULT_TYPE) -> LotteryService:
    service = context.application.bot_data.get("lottery_service")
    if not isinstance(service, LotteryService):
        service = LotteryService(_repo(context))
        context.application.bot_data["lottery_service"] = service
    return service


def _display_name(row: dict[str, Any], fallback: int) -> str:
    name = " ".join(part for part in [row.get("first_name"), row.get("last_name")] if part).strip()
    return name or row.get("username") or str(fallback)


def _format_local_time(value: str | None) -> str:
    if not value:
        return "-"
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")


async def _safe_delete_message(bot, chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=int(message_id))
    except TelegramError:
        return


async def _delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data if context.job else None
    if not isinstance(data, dict):
        return
    await _safe_delete_message(
        context.bot,
        int(data.get("chat_id", 0)),
        int(data.get("message_id", 0)),
    )


def _schedule_delete(context: ContextTypes.DEFAULT_TYPE, *, chat_id: int, message_id: int, ttl_seconds: int = LOTTERY_CONFIRM_TTL_SECONDS) -> None:
    if context.application.job_queue is None:
        return
    context.application.job_queue.run_once(
        _delete_message_job,
        when=ttl_seconds,
        data={"chat_id": chat_id, "message_id": message_id},
        name=f"lottery-cleanup-{chat_id}-{message_id}",
    )


def build_lottery_message_text(lottery: dict[str, Any], prizes: list[dict[str, Any]], *, stats: dict[str, Any] | None = None) -> str:
    mode_label = {
        ENTRY_MODE_FREE: "免费参与",
        ENTRY_MODE_CONSUME: f"参与消耗 {lottery['points_cost']} 积分",
        ENTRY_MODE_THRESHOLD: f"需余额达到 {lottery['points_threshold']} 积分",
    }.get(str(lottery["entry_mode"]), "自定义模式")
    lines = [
        f"抽奖活动：{lottery['title']}",
        lottery.get("description") or "暂无活动说明",
        "",
        f"参与方式：{mode_label}",
        f"报名时间：{_format_local_time(lottery.get('starts_at'))} 至 {_format_local_time(lottery.get('entry_deadline_at'))}",
        f"开奖时间：{_format_local_time(lottery.get('draw_at'))}",
        f"参与次数：{'可多次参与' if lottery['allow_multiple_entries'] else '每人仅一次'}（上限 {lottery['max_entries_per_user']}）",
        "",
        "奖项设置：",
    ]
    for prize in prizes:
        lines.append(f"- {prize['title']} x {prize['winner_count']}")
    if stats:
        lines.extend(
            [
                "",
                f"当前参与人数：{stats['unique_users']}",
                f"当前参与份数：{stats['total_entry_count']}",
            ]
        )
    return "\n".join(lines)


def build_lottery_message_markup(lottery_id: int, *, consume_confirm: bool = False, multi_entry: bool = False) -> InlineKeyboardMarkup:
    if consume_confirm:
        rows = [
            [InlineKeyboardButton("确认参与", callback_data=f"{LOTTERY_CALLBACK_PREFIX}confirm:{lottery_id}:1")],
            [InlineKeyboardButton("查看结果", callback_data=f"{LOTTERY_CALLBACK_PREFIX}result:{lottery_id}")],
        ]
    else:
        join_label = "再次参与" if multi_entry else "参与抽奖"
        rows = [
            [InlineKeyboardButton(join_label, callback_data=f"{LOTTERY_CALLBACK_PREFIX}join:{lottery_id}:1")],
            [InlineKeyboardButton("查看结果", callback_data=f"{LOTTERY_CALLBACK_PREFIX}result:{lottery_id}")],
        ]
    return InlineKeyboardMarkup(rows)


def build_winners_summary(lottery: dict[str, Any], winners: list[dict[str, Any]]) -> str:
    lines = [f"抽奖结果：{lottery['title']}"]
    if not winners:
        lines.append("本次没有产生中奖者。")
        return "\n".join(lines)
    for winner in winners:
        lines.append(f"- {winner['prize_title']}：{_display_name(winner, int(winner['user_id']))}")
    return "\n".join(lines)


async def send_lottery_announcement(
    *,
    bot,
    chat_id: int,
    lottery: dict[str, Any],
    prizes: list[dict[str, Any]],
    stats: dict[str, Any] | None = None,
) -> int | None:
    try:
        message = await bot.send_message(
            chat_id=chat_id,
            text=build_lottery_message_text(lottery, prizes, stats=stats),
            reply_markup=build_lottery_message_markup(int(lottery["id"]), multi_entry=bool(lottery["allow_multiple_entries"])),
        )
        return int(message.message_id)
    except TelegramError:
        return None


async def on_lottery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return
    parts = query.data.removeprefix(LOTTERY_CALLBACK_PREFIX).split(":")
    if len(parts) < 2:
        await query.answer("参数错误", show_alert=True)
        return
    action = parts[0]
    lottery_id = int(parts[1])
    repo = _repo(context)
    service = _lottery_service(context)
    lottery = repo.get_lottery(lottery_id)
    if lottery is None:
        await query.answer("活动不存在", show_alert=True)
        return

    if action == "join":
        if lottery["entry_mode"] == ENTRY_MODE_CONSUME:
            await query.answer("本活动会扣除积分，请点击确认参与。", show_alert=True)
            if query.message:
                try:
                    notice = await query.message.reply_text(
                        f"确认参与「{lottery['title']}」将消耗 {lottery['points_cost']} 积分。",
                        reply_markup=build_lottery_message_markup(lottery_id, consume_confirm=True),
                    )
                    if update.effective_chat:
                        _schedule_delete(
                            context,
                            chat_id=int(update.effective_chat.id),
                            message_id=int(notice.message_id),
                        )
                except TelegramError:
                    pass
            return
        try:
            result = service.join_lottery(lottery_id, query.from_user.id, source="telegram")
        except ValueError as exc:
            await query.answer(_translate_join_error(str(exc), lottery), show_alert=True)
            return
        await query.answer(
            f"报名成功，你当前已拥有 {result['user_stats']['total_entry_count']} 份参与资格。",
            show_alert=True,
        )
        return

    if action == "confirm":
        join_count = int(parts[2]) if len(parts) > 2 else 1
        try:
            result = service.join_lottery(lottery_id, query.from_user.id, join_count=join_count, source="telegram")
        except ValueError as exc:
            await query.answer(_translate_join_error(str(exc), lottery), show_alert=True)
            return
        await query.answer(
            f"报名成功，已参与 {result['user_stats']['total_entry_count']} 份。",
            show_alert=True,
        )
        return

    if action == "result":
        winners = repo.list_lottery_winners(lottery_id)
        if lottery["status"] != "drawn":
            stats = repo.get_lottery_stats(lottery_id)
            await query.answer(
                f"活动还未开奖。当前已有 {stats['unique_users']} 人参与，累计 {stats['total_entry_count']} 份。",
                show_alert=True,
            )
            return
        await query.answer("开奖结果已发送", show_alert=False)
        if query.message:
            try:
                await query.message.reply_text(build_winners_summary(lottery, winners))
            except TelegramError:
                pass


def _translate_join_error(code: str, lottery: dict[str, Any]) -> str:
    messages = {
        "lottery_not_found": "活动不存在。",
        "lottery_not_active": "活动当前不可参与。",
        "lottery_not_started": "活动还没开始。",
        "lottery_entry_closed": "报名已经截止。",
        "lottery_already_joined": "你已经参加过这场活动了。",
        "lottery_entry_limit_reached": f"你已达到最多 {lottery['max_entries_per_user']} 次参与上限。",
        "lottery_threshold_not_met": f"你的积分余额还没达到 {lottery['points_threshold']}。",
        "insufficient_points": "积分不足，暂时不能参与。",
    }
    return messages.get(code, "参与失败，请稍后再试。")


async def run_lottery_draw_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    service = _lottery_service(context)
    repo = _repo(context)
    drawn_lotteries = service.draw_due_lotteries()
    for detail in drawn_lotteries:
        lottery = detail
        winners = detail["winners"]
        summary = build_winners_summary(lottery, winners)
        try:
            await context.bot.send_message(chat_id=int(lottery["chat_id"]), text=summary)
        except TelegramError:
            continue
        for winner in winners:
            try:
                await context.bot.send_message(
                    chat_id=int(winner["user_id"]),
                    text=f"你在「{lottery['title']}」中获得了 {winner['prize_title']}，请留意群内公告。",
                )
            except TelegramError:
                pass
        if not winners:
            continue


def register_lottery_job(app: Application) -> None:
    if app.job_queue is None:
        return
    app.job_queue.run_repeating(run_lottery_draw_job, interval=LOTTERY_JOB_INTERVAL_SECONDS, first=30, name="lottery-draw")
