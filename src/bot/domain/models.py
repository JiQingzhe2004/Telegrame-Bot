from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

ViolationLevel = Literal[0, 1, 2, 3]
ActionType = Literal["none", "warn", "delete", "mute", "restrict", "kick", "ban"]


@dataclass(frozen=True)
class ChatRef:
    chat_id: int
    type: str
    title: str | None = None


@dataclass(frozen=True)
class UserRef:
    user_id: int
    username: str | None
    is_bot: bool
    first_name: str | None = None
    last_name: str | None = None


@dataclass(frozen=True)
class MessageRef:
    chat_id: int
    message_id: int
    user_id: int
    date: datetime
    text: str | None
    meta: dict


@dataclass(frozen=True)
class ChatSettings:
    chat_id: int
    mode: str = "balanced"
    ai_enabled: bool = True
    ai_threshold: float = 0.75
    allow_admin_self_test: bool = False
    action_policy: str = "progressive"
    rate_limit_policy: str = "default"
    language: str = "zh"
    level3_mute_seconds: int = 604800


@dataclass(frozen=True)
class ModerationContext:
    chat: ChatRef
    user: UserRef
    settings: ChatSettings
    strike_score: int
    whitelist_hit: bool
    blacklist_words: list[str] = field(default_factory=list)
    recent_message_texts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuleResult:
    hit: bool
    level: ViolationLevel
    codes: list[str]
    details: dict


@dataclass(frozen=True)
class AiDecision:
    category: str
    level: ViolationLevel
    confidence: float
    reasons: list[str]
    suggested_action: ActionType
    should_escalate_to_admin: bool
    raw: dict


@dataclass(frozen=True)
class ModerationDecision:
    final_level: ViolationLevel
    final_action: ActionType
    reason_codes: list[str]
    rule_results: list[RuleResult]
    ai_used: bool
    ai_decision: AiDecision | None
    confidence: float
    ai_status: Literal["skipped", "success", "failed"] = "skipped"
    ai_error: str | None = None
    duration_seconds: int | None = None


@dataclass(frozen=True)
class EnforcementResult:
    attempted_action: ActionType
    applied_action: ActionType
    success: bool
    downgraded: bool
    reason: str
    duration_seconds: int | None = None


class Rule(Protocol):
    name: str

    def evaluate(self, message: MessageRef, context: ModerationContext) -> RuleResult:
        ...


class AiModerator(Protocol):
    async def classify(self, message: MessageRef, context: ModerationContext) -> AiDecision:
        ...
