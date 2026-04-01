import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram import Chat
from telegram.error import TelegramError

from bot.domain.models import ChatRef, ModerationDecision
from bot.domain.moderation import PermissionSnapshot
from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository
from bot.telegram.adapter_ptb import (
    VERIFY_CALLBACK_PREFIX,
    _verification_timeout,
    on_group_message,
    on_join_verify_callback,
    on_new_chat_members,
)
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


def test_join_verify_pass_cleans_up_messages_and_sends_welcome(tmp_path):
    repo = make_repo(tmp_path)
    query = SimpleNamespace(
        data=f"{VERIFY_CALLBACK_PREFIX}-100123:42:ok",
        from_user=SimpleNamespace(id=42, username="alice", full_name="Alice"),
        answer=AsyncMock(),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "runtime_config": SimpleNamespace(
                    join_verification_max_attempts=3,
                    join_welcome_enabled=True,
                    join_welcome_use_ai=False,
                ),
                "pending_join_verifications": {
                    "-100123:42": {
                        "verify_message_id": 200,
                        "join_message_id": 100,
                        "attempts": 0,
                        "question_type": "button",
                        "display_name": "Alice",
                    }
                },
                "ai_moderator": None,
            },
            job_queue=None,
        ),
        bot=SimpleNamespace(
            restrict_chat_member=AsyncMock(),
            delete_message=AsyncMock(),
            send_message=AsyncMock(),
        ),
    )
    update = SimpleNamespace(
        callback_query=query,
        effective_chat=SimpleNamespace(id=-100123, title="测试群", type="supergroup"),
    )

    with patch("bot.telegram.adapter_ptb._build_welcome_text", new=AsyncMock(return_value="欢迎 Alice")):
        asyncio.run(on_join_verify_callback(update, context))

    query.answer.assert_awaited_once()
    assert context.application.bot_data["pending_join_verifications"] == {}
    assert context.bot.delete_message.await_count == 2
    context.bot.send_message.assert_awaited_once_with(chat_id=-100123, text="欢迎 Alice")


def test_join_verify_timeout_cleans_up_and_kicks_member(tmp_path):
    repo = make_repo(tmp_path)
    context = SimpleNamespace(
        job=SimpleNamespace(data={"chat_id": -100124, "user_id": 43}),
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "pending_join_verifications": {
                    "-100124:43": {
                        "verify_message_id": 201,
                        "join_message_id": 101,
                        "attempts": 1,
                        "display_name": "Bob",
                    }
                },
            },
            job_queue=None,
        ),
        bot=SimpleNamespace(
            delete_message=AsyncMock(),
            ban_chat_member=AsyncMock(),
            unban_chat_member=AsyncMock(),
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=301)),
        ),
    )

    asyncio.run(_verification_timeout(context))

    assert context.application.bot_data["pending_join_verifications"] == {}
    assert context.bot.delete_message.await_count == 2
    context.bot.ban_chat_member.assert_awaited_once()
    context.bot.unban_chat_member.assert_awaited_once()
    context.bot.send_message.assert_awaited_once_with(chat_id=-100124, text="Bob 未在限时内完成入群验证，已被移出群聊。")


def test_new_chat_members_skips_verification_setup_when_restrict_fails(tmp_path):
    repo = make_repo(tmp_path)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-100125, type=Chat.SUPERGROUP, title="验证群"),
        effective_message=SimpleNamespace(
            message_id=88,
            new_chat_members=[
                SimpleNamespace(
                    id=44,
                    is_bot=False,
                    username="bob",
                    first_name="Bob",
                    last_name=None,
                    full_name="Bob",
                )
            ],
            reply_text=AsyncMock(),
        ),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": repo,
                "runtime_config": SimpleNamespace(
                    join_verification_enabled=True,
                    join_verification_timeout_seconds=180,
                    join_verification_max_attempts=3,
                    join_verification_question_type="button",
                    join_verification_whitelist_bypass=True,
                    join_welcome_enabled=False,
                ),
                "pending_join_verifications": {},
            },
            job_queue=None,
        ),
        bot=SimpleNamespace(
            restrict_chat_member=AsyncMock(side_effect=TelegramError("telegram forbid")),
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=302)),
        ),
    )

    asyncio.run(on_new_chat_members(update, context))

    assert context.application.bot_data["pending_join_verifications"] == {}
    context.bot.send_message.assert_awaited_once_with(
        chat_id=-100125,
        text="Bob 的入群验证未生效：机器人无法限制新成员发言，请检查管理员权限。",
    )
