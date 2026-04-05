from pathlib import Path

from bot.points_service import PointsService
from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository


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


def test_update_shop_stock_persists_after_list(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    service = PointsService(repo)

    service.list_shop(chat_id=1)
    service.update_shop(
        chat_id=1,
        items=[
            {
                "item_key": "leaderboard_title",
                "title": "积分榜头衔",
                "description": "申请一个积分榜专属头衔，等待管理员或机器人设置。",
                "item_type": "leaderboard_title",
                "price_points": 30,
                "stock": 5,
                "enabled": True,
                "meta": {"title": "积分榜之星"},
            }
        ],
    )

    items = service.list_shop(chat_id=1)
    item = next(row for row in items if row["item_key"] == "leaderboard_title")

    assert item["stock"] == 5
    assert item["meta"]["title_mode"] == "fixed"
    assert item["meta"]["auto_approve"] is False


def test_update_task_config_persists_after_list(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    service = PointsService(repo)

    service.list_task_config(chat_id=1)
    service.update_task_config(
        chat_id=1,
        items=[
            {
                "task_key": "daily_messages",
                "title": "今日发言",
                "description": "当天完成 5 次有效发言",
                "task_type": "message_count",
                "target_value": 9,
                "reward_points": 11,
                "period": "daily",
                "enabled": True,
            }
        ],
    )

    tasks = service.list_task_config(chat_id=1)
    task = next(row for row in tasks if row["task_key"] == "daily_messages")

    assert task["target_value"] == 9
    assert task["reward_points"] == 11


def test_update_shop_title_meta_round_trip(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    service = PointsService(repo)

    items = service.update_shop(
        chat_id=1,
        items=[
            {
                "item_key": "leaderboard_title",
                "title": "积分榜头衔",
                "description": "申请头衔",
                "item_type": "leaderboard_title",
                "price_points": 30,
                "stock": None,
                "enabled": True,
                "meta": {"title_mode": "custom", "fixed_title": "积分榜之星", "auto_approve": True},
            }
        ],
    )

    item = next(row for row in items if row["item_key"] == "leaderboard_title")

    assert item["meta"]["title_mode"] == "custom"
    assert item["meta"]["fixed_title"] == "积分榜之星"
    assert item["meta"]["auto_approve"] is True


def test_redeem_title_fixed_mode_starts_pending(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    service = PointsService(repo)
    repo.adjust_points(chat_id=1, user_id=2, amount=100, event_type="admin_adjust", operator="test")

    result = service.redeem(chat_id=1, user_id=2, item_key="leaderboard_title")

    assert result["redemption"]["status"] == "pending"
    assert result["redemption"]["payload"]["title_mode"] == "fixed"
    assert result["redemption"]["payload"]["approval_status"] == "pending"


def test_redeem_title_custom_mode_starts_pending_input(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    service = PointsService(repo)
    repo.adjust_points(chat_id=1, user_id=2, amount=100, event_type="admin_adjust", operator="test")
    service.update_shop(
        chat_id=1,
        items=[
            {
                "item_key": "leaderboard_title",
                "title": "积分榜头衔",
                "description": "申请头衔",
                "item_type": "leaderboard_title",
                "price_points": 30,
                "stock": None,
                "enabled": True,
                "meta": {"title_mode": "custom", "fixed_title": "积分榜之星", "auto_approve": True},
            }
        ],
    )

    result = service.redeem(chat_id=1, user_id=2, item_key="leaderboard_title")

    assert result["redemption"]["status"] == "pending_input"
    assert result["redemption"]["payload"]["title_mode"] == "custom"
    assert result["redemption"]["payload"]["approval_status"] == "pending_input"
