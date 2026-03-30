from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from telegram import Bot, ChatPermissions
from telegram.error import TelegramError

from bot.domain.models import (
    ActionType,
    AiDecision,
    EnforcementResult,
    MessageRef,
    ModerationContext,
    ModerationDecision,
    Rule,
    RuleResult,
)
from bot.domain.policy import confidence_gate, downgrade_by_permissions, progressive_action
from bot.storage.repo import BotRepository
from bot.utils.time import utc_now

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PermissionSnapshot:
    can_delete_messages: bool
    can_restrict_members: bool
    can_ban_users: bool


class ModerationService:
    def __init__(self, rules: list[Rule], ai_moderator) -> None:
        self.rules = rules
        self.ai_moderator = ai_moderator

    async def decide(self, message: MessageRef, context: ModerationContext) -> ModerationDecision:
        if context.whitelist_hit:
            return ModerationDecision(
                final_level=0,
                final_action="none",
                reason_codes=["whitelist.bypass"],
                rule_results=[],
                ai_used=False,
                ai_decision=None,
                confidence=1.0,
            )

        rule_results = [rule.evaluate(message, context) for rule in self.rules]
        rule_hits = [r for r in rule_results if r.hit]
        rule_level = max((r.level for r in rule_hits), default=0)
        reason_codes = [c for r in rule_hits for c in r.codes]

        ai_decision: AiDecision | None = None
        ai_used = False
        final_level = rule_level
        confidence = 1.0 if rule_level else 0.5

        should_use_ai = context.settings.ai_enabled and (rule_level < 2 or not rule_hits)
        if should_use_ai and self.ai_moderator:
            ai_used = True
            try:
                ai_decision = await self.ai_moderator.classify(message, context)
                final_level = max(final_level, ai_decision.level)
                confidence = ai_decision.confidence
                reason_codes.extend([f"ai.{ai_decision.category}"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("AI classify failed; fallback to rule-only: %s", exc)
                reason_codes.append("ai.fallback")

        action_plan = progressive_action(
            level=final_level,
            strike_score=context.strike_score,
            level3_mute_seconds=context.settings.level3_mute_seconds,
        )
        final_action = confidence_gate(
            action_plan.action,
            confidence=confidence,
            threshold=context.settings.ai_threshold,
        )

        return ModerationDecision(
            final_level=final_level,
            final_action=final_action,
            reason_codes=reason_codes or ["ok"],
            rule_results=rule_results,
            ai_used=ai_used,
            ai_decision=ai_decision,
            confidence=confidence,
            duration_seconds=action_plan.duration_seconds,
        )


class Enforcer:
    def __init__(self, repo: BotRepository) -> None:
        self.repo = repo

    async def apply(
        self,
        bot: Bot,
        message: MessageRef,
        decision: ModerationDecision,
        perms: PermissionSnapshot,
    ) -> EnforcementResult:
        action = downgrade_by_permissions(
            decision.final_action,
            can_delete=perms.can_delete_messages,
            can_restrict=perms.can_restrict_members,
            can_ban=perms.can_ban_users,
        )
        downgraded = action != decision.final_action
        if action == "none":
            return EnforcementResult("none", "none", True, downgraded, "no-op")

        try:
            if action == "warn":
                await bot.send_message(chat_id=message.chat_id, text=f"@{message.user_id} 请注意群规。")
            elif action == "delete":
                await bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
            elif action == "mute":
                until = utc_now() + timedelta(seconds=decision.duration_seconds or 600)
                await bot.restrict_chat_member(
                    chat_id=message.chat_id,
                    user_id=message.user_id,
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
                    until_date=until,
                )
                if perms.can_delete_messages:
                    await bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
            elif action in {"kick", "ban"}:
                await bot.ban_chat_member(chat_id=message.chat_id, user_id=message.user_id)
            elif action == "restrict":
                until = utc_now() + timedelta(seconds=decision.duration_seconds or 600)
                await bot.restrict_chat_member(
                    chat_id=message.chat_id,
                    user_id=message.user_id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
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
                    until_date=until,
                )
            return EnforcementResult(
                attempted_action=decision.final_action,
                applied_action=action,
                success=True,
                downgraded=downgraded,
                reason="applied",
                duration_seconds=decision.duration_seconds,
            )
        except TelegramError as exc:
            logger.warning("enforcement failed: %s", exc)
            return EnforcementResult(
                attempted_action=decision.final_action,
                applied_action="warn",
                success=False,
                downgraded=True,
                reason=f"telegram-error:{exc}",
            )

    async def rollback(self, bot: Bot, chat_id: int, user_id: int, action: ActionType) -> tuple[bool, str]:
        if action not in {"mute", "restrict"}:
            return False, "action-not-reversible"
        try:
            await bot.restrict_chat_member(
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
            return True, "rolled-back"
        except TelegramError as exc:
            return False, f"telegram-error:{exc}"
