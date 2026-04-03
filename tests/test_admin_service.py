import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram import ChatPermissions
from telegram.error import TelegramError

from bot.telegram.admin_service import TelegramAdminService


def make_service(can_delete_messages: bool = True):
    bot = AsyncMock()
    bot.get_me.return_value = SimpleNamespace(id=999, username="bot")
    bot.get_chat_member.return_value = SimpleNamespace(
        can_change_info=True,
        can_delete_messages=can_delete_messages,
        can_restrict_members=True,
        can_invite_users=True,
        can_pin_messages=True,
        can_promote_members=True,
        can_manage_video_chats=True,
        can_manage_chat=True,
        can_post_stories=False,
        can_edit_stories=False,
        can_delete_stories=False,
        is_anonymous=False,
    )
    repo = SimpleNamespace(save_admin_action=lambda *args, **kwargs: 1)
    return TelegramAdminService(bot=bot, repo=repo), bot


def test_delete_message_permission_denied():
    svc, _bot = make_service(can_delete_messages=False)
    result = asyncio.run(svc.delete_message(chat_id=1, message_id=2))
    assert result.permission_ok is False
    assert result.applied is False


def test_delete_message_success():
    svc, bot = make_service(can_delete_messages=True)
    result = asyncio.run(svc.delete_message(chat_id=1, message_id=2))
    assert result.permission_ok is True
    assert result.applied is True
    bot.delete_message.assert_awaited_once()


def test_delete_message_telegram_error():
    svc, bot = make_service(can_delete_messages=True)
    bot.delete_message.side_effect = TelegramError("bad request")
    result = asyncio.run(svc.delete_message(chat_id=1, message_id=2))
    assert result.permission_ok is True
    assert result.applied is False


def test_owner_bot_has_full_capabilities_for_admin_actions():
    bot = AsyncMock()
    bot.get_me.return_value = SimpleNamespace(id=999, username="bot")
    bot.get_chat_member.return_value = SimpleNamespace(
        status="creator",
        is_anonymous=False,
    )
    repo = SimpleNamespace(save_admin_action=lambda *args, **kwargs: 1)
    svc = TelegramAdminService(bot=bot, repo=repo)

    result = asyncio.run(svc.delete_message(chat_id=1, message_id=2))

    assert result.permission_ok is True
    assert result.applied is True
    bot.delete_message.assert_awaited_once_with(chat_id=1, message_id=2)


def test_mute_member_uses_no_permissions_and_independent_permissions():
    svc, bot = make_service()

    result = asyncio.run(svc.mute_member(chat_id=1, user_id=2, duration_seconds=600))

    assert result.permission_ok is True
    assert result.applied is True
    bot.restrict_chat_member.assert_awaited_once()
    kwargs = bot.restrict_chat_member.await_args.kwargs
    assert kwargs["chat_id"] == 1
    assert kwargs["user_id"] == 2
    assert kwargs["permissions"] == ChatPermissions.no_permissions()
    assert kwargs["use_independent_chat_permissions"] is True
    assert kwargs["until_date"] is not None


def test_unmute_member_uses_all_permissions_without_until_date():
    svc, bot = make_service()

    result = asyncio.run(svc.unmute_member(chat_id=1, user_id=2))

    assert result.permission_ok is True
    assert result.applied is True
    bot.restrict_chat_member.assert_awaited_once()
    kwargs = bot.restrict_chat_member.await_args.kwargs
    assert kwargs["chat_id"] == 1
    assert kwargs["user_id"] == 2
    assert kwargs["permissions"] == ChatPermissions.all_permissions()
    assert kwargs["use_independent_chat_permissions"] is True
    assert "until_date" not in kwargs


def test_ban_member_uses_can_restrict_members_permission():
    svc, bot = make_service()

    result = asyncio.run(svc.ban_member(chat_id=1, user_id=2))

    assert result.permission_ok is True
    assert result.applied is True
    assert result.permission_required == []
    bot.ban_chat_member.assert_awaited_once_with(chat_id=1, user_id=2)


def test_list_members_includes_current_status_from_telegram():
    svc, bot = make_service()
    svc.repo.list_chat_members = lambda chat_id, limit=200, query=None: [
        {
            "user_id": 2,
            "username": "alice",
            "first_name": "Alice",
            "last_name": None,
            "last_message_at": None,
            "strike_score": 1,
        }
    ]
    bot.get_chat_member.return_value = SimpleNamespace(status="restricted", until_date=None)

    rows = asyncio.run(svc.list_members(chat_id=1))

    assert len(rows) == 1
    assert rows[0]["current_status"] == "restricted"
    assert rows[0]["current_status_until_date"] is None


def test_kick_member_temporarily_bans_then_unbans():
    svc, bot = make_service()

    result = asyncio.run(svc.kick_member(chat_id=1, user_id=2))

    assert result.permission_ok is True
    assert result.applied is True
    bot.ban_chat_member.assert_awaited_once()
    bot.unban_chat_member.assert_awaited_once_with(chat_id=1, user_id=2, only_if_banned=True)
