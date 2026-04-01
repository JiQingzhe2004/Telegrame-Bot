from __future__ import annotations

from typing import Any

from bot.domain.moderation import PermissionSnapshot


CAPABILITY_FIELDS = (
    "can_change_info",
    "can_delete_messages",
    "can_restrict_members",
    "can_invite_users",
    "can_pin_messages",
    "can_promote_members",
    "can_manage_video_chats",
    "can_manage_chat",
    "can_post_stories",
    "can_edit_stories",
    "can_delete_stories",
)


def extract_chat_capabilities(member: Any) -> dict[str, bool]:
    status = str(getattr(member, "status", "") or "").lower()
    is_owner = status in {"creator", "owner"}
    caps = {
        field: (True if is_owner else bool(getattr(member, field, False)))
        for field in CAPABILITY_FIELDS
    }
    caps["is_anonymous"] = bool(getattr(member, "is_anonymous", False))
    return caps


async def get_bot_capabilities(bot, chat_id: int) -> dict[str, bool]:
    me = await bot.get_me()
    member = await bot.get_chat_member(chat_id=chat_id, user_id=me.id)
    return extract_chat_capabilities(member)


async def get_permission_snapshot(bot, chat_id: int) -> PermissionSnapshot:
    caps = await get_bot_capabilities(bot, chat_id)
    return PermissionSnapshot(
        can_delete_messages=caps["can_delete_messages"],
        can_restrict_members=caps["can_restrict_members"],
        can_ban_users=caps["can_restrict_members"],
    )


async def is_admin(bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    return member.status in {"administrator", "creator"}
