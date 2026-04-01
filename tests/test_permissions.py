import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.telegram.permissions import extract_chat_capabilities, get_permission_snapshot


def test_extract_chat_capabilities_treats_creator_as_full_access():
    caps = extract_chat_capabilities(SimpleNamespace(status="creator", is_anonymous=False))

    assert caps["can_delete_messages"] is True
    assert caps["can_restrict_members"] is True
    assert caps["can_invite_users"] is True
    assert caps["can_promote_members"] is True


def test_get_permission_snapshot_does_not_use_promote_as_ban_permission():
    bot = AsyncMock()
    bot.get_me.return_value = SimpleNamespace(id=999)
    bot.get_chat_member.return_value = SimpleNamespace(
        status="administrator",
        can_delete_messages=True,
        can_restrict_members=False,
        can_promote_members=True,
        is_anonymous=False,
    )

    snapshot = asyncio.run(get_permission_snapshot(bot, chat_id=1))

    assert snapshot.can_delete_messages is True
    assert snapshot.can_restrict_members is False
    assert snapshot.can_ban_users is False
