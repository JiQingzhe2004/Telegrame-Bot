import asyncio
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from telegram import Chat

from bot.domain.models import ChatRef, UserRef
from bot.lottery_service import ENTRY_MODE_CONSUME, ENTRY_MODE_FREE, ENTRY_MODE_THRESHOLD, LotteryService
from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository
from bot.telegram.lottery import LOTTERY_CALLBACK_PREFIX, build_lottery_message_text, on_lottery_callback
from bot.utils.time import to_iso, utc_now


def make_repo(path: Path) -> BotRepository:
    db = Database(path)
    migrate(db)
    return BotRepository(
        db,
        defaults={
            "chat_enabled": False,
            "mode": "balanced",
            "ai_enabled": True,
            "ai_threshold": 0.75,
            "allow_admin_self_test": False,
            "action_policy": "progressive",
            "rate_limit_policy": "default",
            "language": "zh",
            "level3_mute_seconds": 604800,
        },
    )


def make_lottery(service: LotteryService, chat_id: int, *, entry_mode: str = ENTRY_MODE_FREE, allow_multiple_entries: bool = False) -> dict:
    now = utc_now()
    deadline = now + timedelta(hours=1)
    return service.create_lottery(
        chat_id,
        {
            "title": "周末抽奖",
            "description": "测试活动",
            "entry_mode": entry_mode,
            "points_cost": 5,
            "points_threshold": 10,
            "allow_multiple_entries": allow_multiple_entries,
            "max_entries_per_user": 3 if allow_multiple_entries else 1,
            "show_participants": True,
            "starts_at": to_iso(now),
            "entry_deadline_at": to_iso(deadline),
            "draw_at": to_iso(deadline),
            "created_by": 1,
            "prizes": [
                {"title": "一等奖", "winner_count": 1, "sort_order": 0},
                {"title": "二等奖", "winner_count": 1, "sort_order": 1},
            ],
        },
    )


def seed_users(repo: BotRepository, chat_id: int) -> None:
    chat = ChatRef(chat_id=chat_id, type=Chat.SUPERGROUP, title="测试群")
    repo.upsert_chat(chat)
    repo.upsert_chat_user(chat, UserRef(user_id=11, username="alice", is_bot=False, first_name="Alice"))
    repo.upsert_chat_user(chat, UserRef(user_id=12, username="bob", is_bot=False, first_name="Bob"))
    repo.upsert_chat_user(chat, UserRef(user_id=13, username="carol", is_bot=False, first_name="Carol"))


def test_free_lottery_join_does_not_spend_points(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    seed_users(repo, 1)
    service = LotteryService(repo)
    lottery = make_lottery(service, 1, entry_mode=ENTRY_MODE_FREE)

    result = service.join_lottery(int(lottery["id"]), 11)

    assert result["user_stats"]["total_entry_count"] == 1
    assert repo.get_points_balance(1, 11)["balance"] == 0
    assert repo.list_points_ledger(1) == []


def test_consume_lottery_cancel_refunds_points(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    seed_users(repo, 1)
    repo.adjust_points(chat_id=1, user_id=11, amount=20, event_type="admin_adjust", operator="test", reason="seed")
    service = LotteryService(repo)
    lottery = make_lottery(service, 1, entry_mode=ENTRY_MODE_CONSUME)

    joined = service.join_lottery(int(lottery["id"]), 11)
    assert joined["user_stats"]["total_points_spent"] == 5
    assert repo.get_points_balance(1, 11)["balance"] == 15

    canceled = service.cancel_lottery(int(lottery["id"]), operator="admin_api")
    assert canceled["status"] == "canceled"
    assert repo.get_points_balance(1, 11)["balance"] == 20
    entries = repo.list_lottery_entries(int(lottery["id"]))
    assert entries[0]["status"] == "refunded"


def test_threshold_lottery_requires_balance(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    seed_users(repo, 1)
    service = LotteryService(repo)
    lottery = make_lottery(service, 1, entry_mode=ENTRY_MODE_THRESHOLD)

    try:
        service.join_lottery(int(lottery["id"]), 11)
    except ValueError as exc:
        assert str(exc) == "lottery_threshold_not_met"
    else:
        raise AssertionError("expected threshold validation error")


def test_multi_entry_draw_picks_unique_winners(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    seed_users(repo, 1)
    repo.adjust_points(chat_id=1, user_id=11, amount=20, event_type="admin_adjust", operator="test", reason="seed")
    repo.adjust_points(chat_id=1, user_id=12, amount=20, event_type="admin_adjust", operator="test", reason="seed")
    repo.adjust_points(chat_id=1, user_id=13, amount=20, event_type="admin_adjust", operator="test", reason="seed")
    service = LotteryService(repo)
    lottery = make_lottery(service, 1, entry_mode=ENTRY_MODE_CONSUME, allow_multiple_entries=True)
    lottery_id = int(lottery["id"])
    service.join_lottery(lottery_id, 11, join_count=2)
    service.join_lottery(lottery_id, 12, join_count=1)
    service.join_lottery(lottery_id, 13, join_count=1)
    repo.update_lottery(lottery_id, {"draw_at": to_iso(utc_now())})

    with patch("bot.lottery_service.random.randint", side_effect=[1, 1]):
        drawn = service.draw_lottery(lottery_id)

    assert drawn["status"] == "drawn"
    winners = drawn["winners"]
    assert len(winners) == 2
    assert winners[0]["user_id"] != winners[1]["user_id"]
    assert winners[0]["prize_title"] == "一等奖"
    assert winners[1]["prize_title"] == "二等奖"


def test_draw_due_lotteries_only_draws_due_items(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    seed_users(repo, 1)
    service = LotteryService(repo)
    due = make_lottery(service, 1)
    future = make_lottery(service, 1)
    repo.update_lottery(int(due["id"]), {"draw_at": to_iso(utc_now())})
    repo.update_lottery(int(future["id"]), {"draw_at": to_iso(utc_now().replace(year=utc_now().year + 1))})

    drawn = service.draw_due_lotteries()

    ids = {item["id"] for item in drawn}
    assert int(due["id"]) in ids
    assert int(future["id"]) not in ids


def test_lottery_callback_join_free_activity(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    seed_users(repo, 1)
    service = LotteryService(repo)
    lottery = make_lottery(service, 1, entry_mode=ENTRY_MODE_FREE)
    query = SimpleNamespace(
        data=f"{LOTTERY_CALLBACK_PREFIX}join:{lottery['id']}:1",
        from_user=SimpleNamespace(id=11),
        answer=AsyncMock(),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo, "lottery_service": service}),
        bot=SimpleNamespace(),
    )

    asyncio.run(on_lottery_callback(update, context))

    query.answer.assert_awaited_once()
    assert "报名成功" in query.answer.await_args.args[0]


def test_lottery_message_text_formats_local_time():
    text = build_lottery_message_text(
        {
            "title": "周末抽奖",
            "description": "测试活动",
            "entry_mode": ENTRY_MODE_FREE,
            "points_cost": 0,
            "points_threshold": 0,
            "starts_at": "2026-04-05T12:30:00+00:00",
            "entry_deadline_at": "2026-04-05T13:30:00+00:00",
            "draw_at": "2026-04-05T14:30:00+00:00",
            "allow_multiple_entries": False,
            "max_entries_per_user": 1,
        },
        [{"title": "一等奖", "winner_count": 1}],
    )

    assert "T12:30:00" not in text
    assert "+00:00" not in text
    assert "开奖时间：" in text


def test_lottery_callback_consume_prompt_schedules_cleanup(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    seed_users(repo, 1)
    service = LotteryService(repo)
    lottery = make_lottery(service, 1, entry_mode=ENTRY_MODE_CONSUME)
    reply_text = AsyncMock(return_value=SimpleNamespace(message_id=222))
    query = SimpleNamespace(
        data=f"{LOTTERY_CALLBACK_PREFIX}join:{lottery['id']}:1",
        from_user=SimpleNamespace(id=11),
        answer=AsyncMock(),
        message=SimpleNamespace(reply_text=reply_text),
    )
    run_once = Mock()
    update = SimpleNamespace(
        callback_query=query,
        effective_chat=SimpleNamespace(id=-1001, type=Chat.SUPERGROUP, title="测试群"),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo, "lottery_service": service}, job_queue=SimpleNamespace(run_once=run_once)),
        bot=SimpleNamespace(),
    )

    asyncio.run(on_lottery_callback(update, context))

    reply_text.assert_awaited_once()
    run_once.assert_called_once()
    assert run_once.call_args.kwargs["when"] == 300
