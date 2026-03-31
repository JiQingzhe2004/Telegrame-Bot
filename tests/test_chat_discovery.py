import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram import Chat

from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository
from bot.telegram.adapter_ptb import on_group_message, on_new_chat_members
from bot.telegram.commands import status_cmd


def make_repo(tmp_path) -> BotRepository:
    db = Database(tmp_path / "bot.db")
    migrate(db)
    return BotRepository(
        db,
        defaults={
            "mode": "balanced",
            "ai_enabled": True,
            "ai_threshold": 0.75,
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
