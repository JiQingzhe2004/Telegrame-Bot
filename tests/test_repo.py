from pathlib import Path

from bot.domain.models import ChatRef, MessageRef, ModerationDecision, UserRef
from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository
from bot.utils.time import utc_now


def make_repo(path: Path) -> BotRepository:
    db = Database(path)
    migrate(db)
    return BotRepository(
        db,
        defaults={
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


def test_repo_migration_and_basic_ops(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    repo.upsert_chat_user(
        ChatRef(chat_id=1, type="supergroup", title="t"),
        UserRef(user_id=2, username="u", is_bot=False),
    )
    settings = repo.get_settings(1)
    assert settings.chat_id == 1
    assert settings.allow_admin_self_test is False
    repo.add_list_item("blacklists", 1, "word", "spam")
    assert "spam" in repo.get_blacklist_words(1)

    msg = MessageRef(chat_id=1, message_id=3, user_id=2, date=utc_now(), text="spam", meta={})
    decision = ModerationDecision(
        final_level=2,
        final_action="delete",
        reason_codes=["rule.banword"],
        rule_results=[],
        ai_used=False,
        ai_decision=None,
        confidence=1.0,
    )
    repo.save_violation_message(msg, "spam")
    repo.save_decision(msg, decision)
    audits = repo.list_audits(1)
    assert len(audits) == 1
    assert audits[0]["ai_status"] == "skipped"
    assert audits[0]["ai_error"] is None
    chats = repo.list_chats()
    assert any(int(c["chat_id"]) == 1 for c in chats)
    members = repo.list_chat_members(1)
    assert any(int(m["user_id"]) == 2 for m in members)


def test_repo_whitelist_table_and_lookup(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    repo.add_list_item("whitelists", 1, "user", "2")
    assert repo.is_whitelisted(1, 2, None) is True


def test_repo_can_update_admin_self_test_setting(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="t"))
    repo.update_settings(1, {"allow_admin_self_test": True})
    settings = repo.get_settings(1)
    assert settings.allow_admin_self_test is True


def test_repo_points_adjust_transfer_and_reward(tmp_path):
    repo = make_repo(tmp_path / "bot.db")
    repo.upsert_chat_user(
        ChatRef(chat_id=1, type="supergroup", title="积分群"),
        UserRef(user_id=2, username="alice", is_bot=False),
    )
    repo.upsert_chat_user(
        ChatRef(chat_id=1, type="supergroup", title="积分群"),
        UserRef(user_id=3, username="bob", is_bot=False),
    )
    repo.upsert_chat(ChatRef(chat_id=1, type="supergroup", title="积分群"))

    entry = repo.adjust_points(
        chat_id=1,
        user_id=2,
        amount=10,
        event_type="admin_adjust",
        operator="test",
        reason="seed",
    )
    assert entry["balance_after"] == 10

    transferred = repo.transfer_points(
        chat_id=1,
        from_user_id=2,
        to_user_id=3,
        amount=4,
        operator="test",
    )
    assert transferred["from"]["balance_after"] == 6
    assert transferred["to"]["balance_after"] == 4

    settings = repo.get_settings(1)
    reward = repo.maybe_reward_message_points(1, 2, "hello world", settings)
    assert reward["awarded"] is True
    reward_again = repo.maybe_reward_message_points(1, 2, "hello again", settings)
    assert reward_again["awarded"] is False
    assert reward_again["reason"] == "cooldown"

    leaderboard = repo.list_points_leaderboard(1)
    assert leaderboard[0]["user_id"] == 2
    ledger = repo.list_points_ledger(1)
    assert len(ledger) >= 3
