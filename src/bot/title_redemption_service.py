from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from telegram import Bot

from bot.storage.repo import BotRepository
from bot.telegram.admin_service import TelegramAdminService

TITLE_MODE_FIXED = "fixed"
TITLE_MODE_CUSTOM = "custom"
TITLE_STATUS_PENDING_INPUT = "pending_input"
TITLE_STATUS_PENDING = "pending"
TITLE_STATUS_ACTIVE = "active"
TITLE_STATUS_REJECTED = "rejected"
TITLE_STATUS_FAILED = "failed"
MAX_CUSTOM_TITLE_LENGTH = 16


def _loads_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_title_shop_meta(item: dict[str, Any] | None) -> dict[str, Any]:
    data = _loads_json(None if item is None else item.get("meta_json"))
    title_mode = str(data.get("title_mode") or TITLE_MODE_FIXED).strip().lower()
    if title_mode not in {TITLE_MODE_FIXED, TITLE_MODE_CUSTOM}:
        title_mode = TITLE_MODE_FIXED
    fixed_title = str(data.get("fixed_title") or data.get("title") or "积分榜之星").strip()
    return {
        **data,
        "title_mode": title_mode,
        "fixed_title": fixed_title,
        "auto_approve": bool(data.get("auto_approve", False)),
    }


def dump_title_shop_meta(item: dict[str, Any]) -> str:
    current = _loads_json(item.get("meta_json"))
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    title_mode = str(meta.get("title_mode") or item.get("title_mode") or current.get("title_mode") or TITLE_MODE_FIXED).strip().lower()
    if title_mode not in {TITLE_MODE_FIXED, TITLE_MODE_CUSTOM}:
        title_mode = TITLE_MODE_FIXED
    fixed_title = str(meta.get("fixed_title") or item.get("fixed_title") or current.get("fixed_title") or current.get("title") or "积分榜之星").strip()
    payload = {
        **current,
        "title_mode": title_mode,
        "fixed_title": fixed_title,
        "title": fixed_title,
        "auto_approve": bool(meta.get("auto_approve", item.get("auto_approve", current.get("auto_approve", False)))),
    }
    return json.dumps(payload, ensure_ascii=False)


def parse_redemption_payload(redemption: dict[str, Any] | None) -> dict[str, Any]:
    data = _loads_json(None if redemption is None else redemption.get("reward_payload"))
    return {
        **data,
        "requested_title": str(data.get("requested_title") or "").strip(),
        "title_mode": str(data.get("title_mode") or TITLE_MODE_FIXED).strip().lower() or TITLE_MODE_FIXED,
        "approval_status": str(data.get("approval_status") or (redemption.get("status") if redemption else TITLE_STATUS_PENDING)).strip().lower(),
        "fixed_title": str(data.get("fixed_title") or data.get("title") or "").strip(),
        "apply_error": str(data.get("apply_error") or "").strip(),
        "applied_title": str(data.get("applied_title") or "").strip(),
    }


def build_redemption_payload(
    *,
    title_mode: str,
    fixed_title: str,
    approval_status: str,
    requested_title: str = "",
    apply_error: str = "",
    applied_title: str = "",
) -> str:
    return json.dumps(
        {
            "title_mode": title_mode,
            "fixed_title": fixed_title,
            "requested_title": requested_title,
            "approval_status": approval_status,
            "apply_error": apply_error,
            "applied_title": applied_title,
        },
        ensure_ascii=False,
    )


def resolve_redemption_title(redemption: dict[str, Any]) -> str:
    payload = parse_redemption_payload(redemption)
    if payload["title_mode"] == TITLE_MODE_CUSTOM:
        return payload["requested_title"]
    return payload["fixed_title"]


def validate_custom_title(title: str) -> str:
    cleaned = str(title or "").strip()
    if not cleaned:
        raise ValueError("missing_custom_title")
    if len(cleaned) > MAX_CUSTOM_TITLE_LENGTH:
        raise ValueError("custom_title_too_long")
    return cleaned


@dataclass(frozen=True)
class TitleApplyResult:
    success: bool
    redemption: dict[str, Any] | None
    reason: str


class TitleRedemptionService:
    def __init__(self, repo: BotRepository, bot: Bot) -> None:
        self.repo = repo
        self.bot = bot

    async def apply_redemption(self, redemption_id: int) -> TitleApplyResult:
        redemption = self.repo.get_redemption(redemption_id)
        if redemption is None:
            return TitleApplyResult(False, None, "redemption_not_found")
        if str(redemption.get("item_type")) != "leaderboard_title":
            return TitleApplyResult(False, redemption, "not_title_redemption")

        title = resolve_redemption_title(redemption)
        if not title:
            updated = self._update_payload_only(redemption, status=TITLE_STATUS_PENDING_INPUT, approval_status=TITLE_STATUS_PENDING_INPUT)
            return TitleApplyResult(False, updated, "missing_custom_title")

        admin_service = TelegramAdminService(self.bot, self.repo)
        result = await admin_service.set_admin_title(int(redemption["chat_id"]), int(redemption["user_id"]), title)
        payload = parse_redemption_payload(redemption)
        if result.applied:
            updated = self.repo.update_redemption(
                redemption_id,
                status=TITLE_STATUS_ACTIVE,
                reward_payload=build_redemption_payload(
                    title_mode=payload["title_mode"],
                    fixed_title=payload["fixed_title"],
                    requested_title=payload["requested_title"],
                    approval_status=TITLE_STATUS_ACTIVE,
                    apply_error="",
                    applied_title=title,
                ),
            )
            return TitleApplyResult(True, updated, "applied")

        updated = self.repo.update_redemption(
            redemption_id,
            status=TITLE_STATUS_FAILED,
            reward_payload=build_redemption_payload(
                title_mode=payload["title_mode"],
                fixed_title=payload["fixed_title"],
                requested_title=payload["requested_title"],
                approval_status=TITLE_STATUS_FAILED,
                apply_error=str(result.reason),
                applied_title="",
            ),
        )
        return TitleApplyResult(False, updated, str(result.reason))

    def submit_custom_title(self, redemption_id: int, title: str) -> dict[str, Any] | None:
        redemption = self.repo.get_redemption(redemption_id)
        if redemption is None:
            return None
        payload = parse_redemption_payload(redemption)
        requested_title = validate_custom_title(title)
        next_status = TITLE_STATUS_PENDING
        return self.repo.update_redemption(
            redemption_id,
            status=next_status,
            reward_payload=build_redemption_payload(
                title_mode=TITLE_MODE_CUSTOM,
                fixed_title=payload["fixed_title"],
                requested_title=requested_title,
                approval_status=TITLE_STATUS_PENDING,
                apply_error="",
                applied_title="",
            ),
        )

    def _update_payload_only(self, redemption: dict[str, Any], *, status: str, approval_status: str) -> dict[str, Any] | None:
        payload = parse_redemption_payload(redemption)
        return self.repo.update_redemption(
            int(redemption["id"]),
            status=status,
            reward_payload=build_redemption_payload(
                title_mode=payload["title_mode"],
                fixed_title=payload["fixed_title"],
                requested_title=payload["requested_title"],
                approval_status=approval_status,
                apply_error=payload["apply_error"],
                applied_title=payload["applied_title"],
            ),
        )
