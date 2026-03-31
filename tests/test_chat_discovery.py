import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram import Chat

from bot.domain.models import ChatRef, ModerationDecision
from bot.domain.moderation import PermissionSnapshot
from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository
from bot.telegram.adapter_ptb import on_group_message, on_new_chat_members
from bot.telegram.commands import status_cmd
from bot.utils.time import utc_now


def make_repo(tmp_path) -> BotRepository:
    db = Database(tmp_path / "bot.db")
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


def test_new_chat_members_registers_chat_when_bot_itself_is_added(tmp_path):
    repo = make_repo(tmp_path)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100123, type=Chat.SUPERGROUP, title="测试群"),
        effective_message=SimpleNamespace(
            new_chat_members=[
                SimpleNamespace(
                    id=999001,
                    is_bot=True,
                    username="test_bot",
                    first_name="Test",
                    last_name="Bot",
                    full_name="Test Bot",
                )
            ]
        ),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo}),
        bot=SimpleNamespace(send_message=AsyncMock()),
    )

    asyncio.run(on_new_chat_members(update, context))

    chats = repo.list_chats()
    assert any(int(chat["chat_id"]) == -100123 for chat in chats)


def test_group_message_from_admin_still_registers_chat(tmp_path):
    repo = make_repo(tmp_path)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100456, type=Chat.SUPERGROUP, title="管理群"),
        effective_user=SimpleNamespace(id=42, is_bot=False, username="owner", first_name="Owner", last_name=None),
        effective_message=SimpleNamespace(text="hello", caption=None),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "moderation_service": object(),
                "enforcer": object(),
            }
        ),
        bot=SimpleNamespace(),
    )

    with patch("bot.telegram.adapter_ptb.is_admin", new=AsyncMock(return_value=True)):
        asyncio.run(on_group_message(update, context))

    chats = repo.list_chats()
    assert any(int(chat["chat_id"]) == -100456 for chat in chats)


def test_admin_command_registers_chat_before_permission_check(tmp_path):
    repo = make_repo(tmp_path)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100789, type=Chat.SUPERGROUP, title="命令群"),
        effective_user=SimpleNamespace(id=7, is_bot=False),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"repo": repo}),
        bot=SimpleNamespace(),
    )

    with patch("bot.telegram.commands.is_admin", new=AsyncMock(return_value=False)):
        asyncio.run(status_cmd(update, context))

    chats = repo.list_chats()
    assert any(int(chat["chat_id"]) == -100789 for chat in chats)


def test_group_message_calls_decide_and_can_reach_ai_flow(tmp_path):
    repo = make_repo(tmp_path)
    service = SimpleNamespace(
        decide=AsyncMock(
            return_value=ModerationDecision(
                final_level=0,
                final_action="none",
                reason_codes=["ok"],
                rule_results=[],
                ai_used=False,
                ai_decision=None,
                confidence=0.5,
                duration_seconds=None,
            )
        )
    )
    enforcer = SimpleNamespace(
        apply=AsyncMock(return_value=SimpleNamespace(applied_action="none")),
    )
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100990, type=Chat.SUPERGROUP, title="AI群"),
        effective_user=SimpleNamespace(id=1234, is_bot=False, username="member", first_name="Member", last_name=None),
        effective_message=SimpleNamespace(text="测试消息", caption=None, message_id=55, date=utc_now()),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "moderation_service": service,
                "enforcer": enforcer,
            }
        ),
        bot=SimpleNamespace(),
    )

    permission_snapshot = AsyncMock(return_value=PermissionSnapshot(False, False, False))
    with patch("bot.telegram.adapter_ptb.is_admin", new=AsyncMock(return_value=False)), patch(
        "bot.telegram.adapter_ptb.get_permission_snapshot",
        new=permission_snapshot,
    ):
        asyncio.run(on_group_message(update, context))

    assert service.decide.await_count == 1
    assert enforcer.apply.await_count == 1
    permission_snapshot.assert_awaited_once_with(context.bot, -100990)
    members = repo.list_chat_members(-100990)
    assert len(members) == 1
    assert members[0]["user_id"] == 1234
    audits = repo.list_audits(-100990)
    assert len(audits) == 1
    assert audits[0]["user_id"] == 1234


def test_admin_self_test_runs_audit_but_skips_enforcement(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert_chat(ChatRef(chat_id=-100991, type=Chat.SUPERGROUP, title="自测群"))
    repo.update_settings(-100991, {"allow_admin_self_test": True})
    service = SimpleNamespace(
        decide=AsyncMock(
            return_value=ModerationDecision(
                final_level=2,
                final_action="delete",
                reason_codes=["ai.other"],
                rule_results=[],
                ai_used=True,
                ai_decision=None,
                confidence=0.91,
                duration_seconds=None,
            )
        )
    )
    enforcer = SimpleNamespace(apply=AsyncMock())
    reply_text = AsyncMock()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100991, type=Chat.SUPERGROUP, title="自测群"),
        effective_user=SimpleNamespace(id=42, is_bot=False, username="owner", first_name="Owner", last_name=None),
        effective_message=SimpleNamespace(text="测试自测", caption=None, message_id=56, date=utc_now(), reply_text=reply_text),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "moderation_service": service,
                "enforcer": enforcer,
            }
        ),
        bot=SimpleNamespace(),
    )

    with patch("bot.telegram.adapter_ptb.is_admin", new=AsyncMock(return_value=True)):
        asyncio.run(on_group_message(update, context))

    assert service.decide.await_count == 1
    assert enforcer.apply.await_count == 0
    reply_text.assert_awaited_once()
    audits = repo.list_audits(-100991)
    assert len(audits) == 1
    assert audits[0]["final_level"] == 2
