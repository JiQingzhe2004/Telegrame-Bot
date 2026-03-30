from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

from telegram import Bot, ChatPermissions
from telegram.error import TelegramError

from bot.storage.repo import BotRepository
from bot.utils.time import utc_now


@dataclass(frozen=True)
class ChatCapabilityMatrix:
    can_change_info: bool
    can_delete_messages: bool
    can_restrict_members: bool
    can_invite_users: bool
    can_pin_messages: bool
    can_promote_members: bool
    can_manage_video_chats: bool
    can_manage_chat: bool
    can_post_stories: bool
    can_edit_stories: bool
    can_delete_stories: bool
    is_anonymous: bool


@dataclass(frozen=True)
class AdminActionResult:
    action_supported: bool
    permission_required: list[str]
    permission_ok: bool
    applied: bool
    reason: str
    telegram_error_code: int | None = None
    data: dict[str, Any] | None = None


class TelegramAdminService:
    def __init__(self, bot: Bot, repo: BotRepository) -> None:
        self.bot = bot
        self.repo = repo

    async def _capabilities(self, chat_id: int) -> ChatCapabilityMatrix:
        me = await self.bot.get_me()
        member = await self.bot.get_chat_member(chat_id=chat_id, user_id=me.id)
        return ChatCapabilityMatrix(
            can_change_info=bool(getattr(member, "can_change_info", False)),
            can_delete_messages=bool(getattr(member, "can_delete_messages", False)),
            can_restrict_members=bool(getattr(member, "can_restrict_members", False)),
            can_invite_users=bool(getattr(member, "can_invite_users", False)),
            can_pin_messages=bool(getattr(member, "can_pin_messages", False)),
            can_promote_members=bool(getattr(member, "can_promote_members", False)),
            can_manage_video_chats=bool(getattr(member, "can_manage_video_chats", False)),
            can_manage_chat=bool(getattr(member, "can_manage_chat", False)),
            can_post_stories=bool(getattr(member, "can_post_stories", False)),
            can_edit_stories=bool(getattr(member, "can_edit_stories", False)),
            can_delete_stories=bool(getattr(member, "can_delete_stories", False)),
            is_anonymous=bool(getattr(member, "is_anonymous", False)),
        )

    def _deny(self, required: list[str], reason: str) -> AdminActionResult:
        return AdminActionResult(
            action_supported=True,
            permission_required=required,
            permission_ok=False,
            applied=False,
            reason=reason,
        )

    def _unsupported(self, reason: str) -> AdminActionResult:
        return AdminActionResult(
            action_supported=False,
            permission_required=[],
            permission_ok=False,
            applied=False,
            reason=reason,
        )

    async def overview(self, chat_id: int) -> dict[str, Any]:
        chat = await self.bot.get_chat(chat_id=chat_id)
        count = await self.bot.get_chat_member_count(chat_id=chat_id)
        admins = await self.bot.get_chat_administrators(chat_id=chat_id)
        caps = await self._capabilities(chat_id)
        return {
            "chat": {
                "id": chat.id,
                "type": chat.type,
                "title": chat.title,
                "description": chat.description,
            },
            "member_count": count,
            "administrators": [
                {
                    "user_id": m.user.id,
                    "username": m.user.username,
                    "full_name": m.user.full_name,
                    "status": m.status,
                    "custom_title": getattr(m, "custom_title", None),
                }
                for m in admins
            ],
            "capabilities": asdict(caps),
        }

    async def get_member(self, chat_id: int, user_id: int) -> AdminActionResult:
        try:
            member = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            return AdminActionResult(
                action_supported=True,
                permission_required=[],
                permission_ok=True,
                applied=True,
                reason="ok",
                data={
                    "status": member.status,
                    "is_bot": member.user.is_bot,
                    "username": member.user.username,
                    "full_name": member.user.full_name,
                    "user_id": member.user.id,
                },
            )
        except TelegramError as exc:
            return AdminActionResult(
                action_supported=True,
                permission_required=[],
                permission_ok=True,
                applied=False,
                reason=str(exc),
                telegram_error_code=getattr(exc, "error_code", None),
            )

    async def update_profile(self, chat_id: int, title: str | None, description: str | None) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_change_info:
            return self._deny(["can_change_info"], "missing_permission")
        try:
            if title is not None and title.strip():
                await self.bot.set_chat_title(chat_id=chat_id, title=title.strip())
            if description is not None:
                await self.bot.set_chat_description(chat_id=chat_id, description=description.strip() or None)
            self.repo.save_admin_action(chat_id, "update_profile", "applied", target={"title": title, "description": description})
            return AdminActionResult(True, ["can_change_info"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_change_info"], True, False, str(exc), getattr(exc, "error_code", None))

    async def delete_message(self, chat_id: int, message_id: int) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_delete_messages:
            return self._deny(["can_delete_messages"], "missing_permission")
        try:
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            self.repo.save_admin_action(chat_id, "delete_message", "applied", target={"message_id": message_id}, message_id=message_id)
            return AdminActionResult(True, ["can_delete_messages"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_delete_messages"], True, False, str(exc), getattr(exc, "error_code", None))

    async def pin_message(self, chat_id: int, message_id: int) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_pin_messages:
            return self._deny(["can_pin_messages"], "missing_permission")
        try:
            await self.bot.pin_chat_message(chat_id=chat_id, message_id=message_id, disable_notification=True)
            self.repo.save_admin_action(chat_id, "pin_message", "applied", target={"message_id": message_id}, message_id=message_id)
            return AdminActionResult(True, ["can_pin_messages"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_pin_messages"], True, False, str(exc), getattr(exc, "error_code", None))

    async def unpin_message(self, chat_id: int) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_pin_messages:
            return self._deny(["can_pin_messages"], "missing_permission")
        try:
            await self.bot.unpin_chat_message(chat_id=chat_id)
            self.repo.save_admin_action(chat_id, "unpin_message", "applied", target={})
            return AdminActionResult(True, ["can_pin_messages"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_pin_messages"], True, False, str(exc), getattr(exc, "error_code", None))

    async def mute_member(self, chat_id: int, user_id: int, duration_seconds: int) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_restrict_members:
            return self._deny(["can_restrict_members"], "missing_permission")
        try:
            await self.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_audios=False,
                    can_send_documents=False,
                    can_send_photos=False,
                    can_send_videos=False,
                    can_send_video_notes=False,
                    can_send_voice_notes=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                    can_manage_topics=False,
                ),
                until_date=utc_now() + timedelta(seconds=duration_seconds),
            )
            self.repo.save_admin_action(
                chat_id,
                "mute_member",
                "applied",
                target={"user_id": user_id},
                user_id=user_id,
                duration_seconds=duration_seconds,
            )
            return AdminActionResult(True, ["can_restrict_members"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_restrict_members"], True, False, str(exc), getattr(exc, "error_code", None))

    async def unmute_member(self, chat_id: int, user_id: int) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_restrict_members:
            return self._deny(["can_restrict_members"], "missing_permission")
        try:
            await self.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_change_info=True,
                    can_invite_users=True,
                    can_pin_messages=True,
                    can_manage_topics=True,
                ),
                until_date=utc_now(),
            )
            self.repo.save_admin_action(chat_id, "unmute_member", "applied", target={"user_id": user_id}, user_id=user_id)
            return AdminActionResult(True, ["can_restrict_members"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_restrict_members"], True, False, str(exc), getattr(exc, "error_code", None))

    async def ban_member(self, chat_id: int, user_id: int) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_restrict_members:
            return self._deny(["can_restrict_members"], "missing_permission")
        try:
            await self.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            self.repo.save_admin_action(chat_id, "ban_member", "applied", target={"user_id": user_id}, user_id=user_id)
            return AdminActionResult(True, ["can_restrict_members"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_restrict_members"], True, False, str(exc), getattr(exc, "error_code", None))

    async def unban_member(self, chat_id: int, user_id: int) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_restrict_members:
            return self._deny(["can_restrict_members"], "missing_permission")
        try:
            await self.bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=False)
            self.repo.save_admin_action(chat_id, "unban_member", "applied", target={"user_id": user_id}, user_id=user_id)
            return AdminActionResult(True, ["can_restrict_members"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_restrict_members"], True, False, str(exc), getattr(exc, "error_code", None))

    async def create_invite_link(self, chat_id: int, name: str | None = None) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_invite_users:
            return self._deny(["can_invite_users"], "missing_permission")
        try:
            link = await self.bot.create_chat_invite_link(chat_id=chat_id, name=name or None)
            self.repo.save_admin_action(chat_id, "create_invite_link", "applied", target={"name": name, "invite_link": link.invite_link})
            return AdminActionResult(
                True,
                ["can_invite_users"],
                True,
                True,
                "applied",
                data={"invite_link": link.invite_link, "name": link.name},
            )
        except TelegramError as exc:
            return AdminActionResult(True, ["can_invite_users"], True, False, str(exc), getattr(exc, "error_code", None))

    async def revoke_invite_link(self, chat_id: int, invite_link: str) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_invite_users:
            return self._deny(["can_invite_users"], "missing_permission")
        try:
            revoked = await self.bot.revoke_chat_invite_link(chat_id=chat_id, invite_link=invite_link)
            self.repo.save_admin_action(chat_id, "revoke_invite_link", "applied", target={"invite_link": invite_link})
            return AdminActionResult(
                True,
                ["can_invite_users"],
                True,
                True,
                "applied",
                data={"invite_link": revoked.invite_link},
            )
        except TelegramError as exc:
            return AdminActionResult(True, ["can_invite_users"], True, False, str(exc), getattr(exc, "error_code", None))

    async def promote_admin(self, chat_id: int, user_id: int, promote_payload: dict[str, bool]) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_promote_members:
            return self._deny(["can_promote_members"], "missing_permission")
        try:
            await self.bot.promote_chat_member(chat_id=chat_id, user_id=user_id, **promote_payload)
            self.repo.save_admin_action(chat_id, "promote_admin", "applied", target={"user_id": user_id, "permissions": promote_payload}, user_id=user_id)
            return AdminActionResult(True, ["can_promote_members"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_promote_members"], True, False, str(exc), getattr(exc, "error_code", None))

    async def demote_admin(self, chat_id: int, user_id: int) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_promote_members:
            return self._deny(["can_promote_members"], "missing_permission")
        try:
            await self.bot.promote_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                can_manage_chat=False,
                can_change_info=False,
                can_delete_messages=False,
                can_invite_users=False,
                can_restrict_members=False,
                can_pin_messages=False,
                can_promote_members=False,
                can_manage_video_chats=False,
                can_post_stories=False,
                can_edit_stories=False,
                can_delete_stories=False,
                is_anonymous=False,
            )
            self.repo.save_admin_action(chat_id, "demote_admin", "applied", target={"user_id": user_id}, user_id=user_id)
            return AdminActionResult(True, ["can_promote_members"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_promote_members"], True, False, str(exc), getattr(exc, "error_code", None))

    async def set_admin_title(self, chat_id: int, user_id: int, title: str) -> AdminActionResult:
        caps = await self._capabilities(chat_id)
        if not caps.can_promote_members:
            return self._deny(["can_promote_members"], "missing_permission")
        try:
            await self.bot.set_chat_administrator_custom_title(chat_id=chat_id, user_id=user_id, custom_title=title)
            self.repo.save_admin_action(chat_id, "set_admin_title", "applied", target={"user_id": user_id, "title": title}, user_id=user_id)
            return AdminActionResult(True, ["can_promote_members"], True, True, "applied")
        except TelegramError as exc:
            return AdminActionResult(True, ["can_promote_members"], True, False, str(exc), getattr(exc, "error_code", None))
