from __future__ import annotations

from typing import Any

from bot.domain.moderation import PermissionSnapshot


CAPABILITY_FIELDS = (
    "can_change_info",
    "can_delete_messages",
    "can_restrict_members",
    "can_ban_users",
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
    # Telegram 当前权限模型里，can_restrict_members 同时覆盖 restrict/ban/unban。
    # 某些客户端或旧字段仍会显示“封禁用户”，这里保留兼容别名给前端/UI 展示。
    caps["can_ban_users"] = bool(caps.get("can_restrict_members", False) or caps.get("can_ban_users", False))
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
        can_ban_users=caps.get("can_ban_users", caps["can_restrict_members"]),
    )


async def is_admin(bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    return member.status in {"administrator", "creator"}
