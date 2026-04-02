from __future__ import annotations

from dataclasses import dataclass

from bot.domain.models import ActionType, ViolationLevel


@dataclass(frozen=True)
class ActionPlan:
    action: ActionType
    duration_seconds: int | None = None


def choose_base_action(level: ViolationLevel) -> ActionPlan:
    if level == 0:
        return ActionPlan(action="none")
    if level == 1:
        return ActionPlan(action="warn")
    if level == 2:
        return ActionPlan(action="delete")
    return ActionPlan(action="mute")


def progressive_action(level: ViolationLevel, strike_score: int, level3_mute_seconds: int) -> ActionPlan:
    if level == 0:
        return ActionPlan("none")
    if strike_score <= 0:
        return ActionPlan("delete" if level >= 2 else "warn")
    if strike_score == 1:
        return ActionPlan("mute", duration_seconds=600)
    if strike_score == 2:
        return ActionPlan("mute", duration_seconds=86400)
    if level == 3:
        return ActionPlan("mute", duration_seconds=level3_mute_seconds)
    return ActionPlan("mute", duration_seconds=86400)


def confidence_gate(action: ActionType, confidence: float, threshold: float) -> ActionType:
    if confidence >= threshold:
        return action
    if action in {"mute", "kick", "ban", "restrict"}:
        return "warn"
    return action


def downgrade_by_permissions(
    action: ActionType,
    can_delete: bool,
    can_restrict: bool,
    can_ban: bool,
) -> ActionType:
    if action == "delete" and not can_delete:
        return "warn"
    if action in {"mute", "restrict"} and not can_restrict:
        if can_delete:
            return "delete"
        return "warn"
    if action in {"kick", "ban"} and not can_ban:
        if can_restrict:
            return "mute"
        if can_delete:
            return "delete"
        return "warn"
    return action
