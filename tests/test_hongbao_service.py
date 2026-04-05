from pathlib import Path

from bot.domain.models import ChatSettings
from bot.hongbao_service import HongbaoService, PACKET_MODE_EQUAL, PACKET_MODE_RANDOM, PACKET_STATUS_EXPIRED, PACKET_STATUS_FULLY_CLAIMED
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
            "hongbao_template": "{sender} 发了一个{packet_type}，共 {total_amount} 积分 / {packet_count} 份。{blessing}",
        },
    )


def test_create_equal_packet_requires_divisible_amount(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    service = HongbaoService(repo)
    repo.adjust_points(chat_id=1, user_id=2, amount=100, event_type="admin_adjust", operator="test")
    settings = ChatSettings(chat_id=1)

    try:
        service.create_packet(chat_id=1, sender_user_id=2, total_amount=10, packet_count=3, split_mode=PACKET_MODE_EQUAL, blessing="", settings=settings, operator="test")
    except ValueError as exc:
        assert str(exc) == "packet_equal_amount_not_divisible"
    else:
        raise AssertionError("expected divisibility validation")


def test_claim_random_packet_updates_balances_and_status(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    service = HongbaoService(repo)
    repo.adjust_points(chat_id=1, user_id=2, amount=100, event_type="admin_adjust", operator="test")
    settings = ChatSettings(chat_id=1)
    created = service.create_packet(
        chat_id=1,
        sender_user_id=2,
        total_amount=10,
        packet_count=2,
        split_mode=PACKET_MODE_RANDOM,
        blessing="恭喜发财",
        settings=settings,
        operator="test",
    )

    first = service.claim_packet(created["packet"]["id"], 2, operator="claim")
    second = service.claim_packet(created["packet"]["id"], 3, operator="claim")

    assert first["claim"]["amount"] > 0
    assert second["claim"]["amount"] > 0
    assert first["claim"]["amount"] + second["claim"]["amount"] == 10
    assert second["packet"]["status"] == PACKET_STATUS_FULLY_CLAIMED


def test_expired_packet_moves_remaining_to_pool(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    service = HongbaoService(repo)
    repo.adjust_points(chat_id=1, user_id=2, amount=100, event_type="admin_adjust", operator="test")
    settings = ChatSettings(chat_id=1)
    created = service.create_packet(
        chat_id=1,
        sender_user_id=2,
        total_amount=12,
        packet_count=3,
        split_mode=PACKET_MODE_EQUAL,
        blessing="恭喜发财",
        settings=settings,
        operator="test",
        expires_in_seconds=0,
    )

    expired = service.expire_due_packets()

    assert expired[0]["status"] == PACKET_STATUS_EXPIRED
    assert repo.get_points_pool_balance(1)["balance"] == 12
