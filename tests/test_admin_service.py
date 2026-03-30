import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
