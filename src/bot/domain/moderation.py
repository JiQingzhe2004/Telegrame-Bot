from __future__ import annotations

from html import escape
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

ACTION_LABELS = {
    "warn": "警告",
    "delete": "删除消息",
    "mute": "禁言",
    "restrict": "限制发言",
    "kick": "移出群组",
    "ban": "封禁",
}

REASON_LABELS = {
    "rule.banword": "命中违禁词",
    "rule.suspicious_link": "包含可疑链接",
    "rule.flood.repeat": "重复刷屏",
    "rule.flood.burst": "短时间高频发言",
    "ai.spam": "AI 判定为垃圾信息",
    "ai.scam": "AI 判定为诈骗或引流",
    "ai.harassment": "AI 判定为辱骂或骚扰",
    "ai.sexual": "AI 判定为色情内容",
    "ai.violence": "AI 判定为暴力内容",
    "ai.personal_data": "AI 判定为泄露个人信息",
    "ai.other": "AI 判定为异常内容",
}


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
                ai_status="skipped",
                ai_error=None,
                ai_decision=None,
                confidence=1.0,
            )

        rule_results = [rule.evaluate(message, context) for rule in self.rules]
        rule_hits = [r for r in rule_results if r.hit]
        rule_level = max((r.level for r in rule_hits), default=0)
        reason_codes = [c for r in rule_hits for c in r.codes]

        ai_decision: AiDecision | None = None
        ai_used = False
        ai_status = "skipped"
        ai_error: str | None = None
        final_level = rule_level
        confidence = 1.0 if rule_level else 0.5

        should_use_ai = context.settings.ai_enabled
        if should_use_ai and self.ai_moderator:
            ai_used = True
            try:
                ai_decision = await self.ai_moderator.classify(message, context)
                ai_status = "success"
                final_level = max(final_level, ai_decision.level)
                confidence = ai_decision.confidence
                reason_codes.extend([f"ai.{ai_decision.category}"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("AI classify failed; fallback to rule-only: %s", exc)
                ai_status = "failed"
                ai_error = str(exc)
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
            ai_status=ai_status,
            ai_error=ai_error,
            ai_decision=ai_decision,
            confidence=confidence,
            duration_seconds=action_plan.duration_seconds,
        )


class Enforcer:
    def __init__(self, repo: BotRepository) -> None:
        self.repo = repo

    @staticmethod
    def _user_mention(message: MessageRef) -> str:
        username = str(message.meta.get("username", "") or "").strip()
        if username:
            return f"@{username}"
        display_name = str(message.meta.get("display_name", "") or "").strip() or "该用户"
        return f'<a href="tg://user?id={message.user_id}">{escape(display_name)}</a>'

    @staticmethod
    def _format_duration(seconds: int | None) -> str:
        if not seconds or seconds <= 0:
            return ""
        if seconds % 86400 == 0:
            return f"{seconds // 86400}天"
        if seconds % 3600 == 0:
            return f"{seconds // 3600}小时"
        if seconds % 60 == 0:
            return f"{seconds // 60}分钟"
        return f"{seconds}秒"

    @staticmethod
    def _format_reasons(decision: ModerationDecision) -> str:
        labels: list[str] = []
        for code in decision.reason_codes:
            if code in {"ok", "ai.ok", "ai.fallback", "whitelist.bypass"}:
                continue
            label = REASON_LABELS.get(code)
            if label and label not in labels:
                labels.append(label)
        return "、".join(labels) if labels else "违反群规"

    def _build_notice(self, message: MessageRef, decision: ModerationDecision, action: ActionType, downgraded: bool) -> str:
        mention = self._user_mention(message)
        reasons = self._format_reasons(decision)
        action_label = ACTION_LABELS.get(action, "处理")
        duration_text = self._format_duration(decision.duration_seconds)
        if action == "mute" and duration_text:
            action_text = f"已被禁言 {duration_text}"
        elif action == "restrict" and duration_text:
            action_text = f"已被限制发言 {duration_text}"
        elif action == "delete":
            action_text = "发送的消息已被删除"
        else:
            action_text = f"已被{action_label}"
        downgraded_text = ""
        if downgraded and decision.final_action != action:
            downgraded_text = f"（因机器人权限限制，已从{ACTION_LABELS.get(decision.final_action, decision.final_action)}降级为{action_label}）"
        return f"{mention} {action_text}。原因：{reasons}{downgraded_text}"

    async def _send_notice(self, bot: Bot, message: MessageRef, decision: ModerationDecision, action: ActionType, downgraded: bool) -> None:
        notice = self._build_notice(message, decision, action, downgraded)
        await bot.send_message(chat_id=message.chat_id, text=notice, parse_mode="HTML")

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
                await self._send_notice(bot, message, decision, action, downgraded)
            elif action == "delete":
                await bot.delete_message(chat_id=message.chat_id, message_id=message.message_id)
                await self._send_notice(bot, message, decision, action, downgraded)
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
                await self._send_notice(bot, message, decision, action, downgraded)
            elif action in {"kick", "ban"}:
                await bot.ban_chat_member(chat_id=message.chat_id, user_id=message.user_id)
                await self._send_notice(bot, message, decision, action, downgraded)
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
                await self._send_notice(bot, message, decision, action, downgraded)
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
