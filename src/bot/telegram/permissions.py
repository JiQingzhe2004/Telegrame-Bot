from __future__ import annotations

from bot.domain.moderation import PermissionSnapshot


async def get_permission_snapshot(bot, chat_id: int) -> PermissionSnapshot:
    me = await bot.get_me()
    member = await bot.get_chat_member(chat_id=chat_id, user_id=me.id)
    perms = getattr(member, "can_delete_messages", False), getattr(member, "can_restrict_members", False), getattr(
        member, "can_promote_members", False
    )
    return PermissionSnapshot(
        can_delete_messages=bool(perms[0]),
        can_restrict_members=bool(perms[1]),
        can_ban_users=bool(perms[2] or perms[1]),
    )


async def is_admin(bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    return member.status in {"administrator", "creator"}
