from __future__ import annotations

import random
from datetime import timedelta
from typing import Any

from bot.domain.models import ChatSettings
from bot.storage.repo import BotRepository
from bot.utils.time import to_iso, utc_now

PACKET_MODE_RANDOM = "random"
PACKET_MODE_EQUAL = "equal"
PACKET_STATUS_ACTIVE = "active"
PACKET_STATUS_FULLY_CLAIMED = "fully_claimed"
PACKET_STATUS_EXPIRED = "expired"
CURRENCY_LABEL = "积分"


class HongbaoService:
    def __init__(self, repo: BotRepository) -> None:
        self.repo = repo

    def create_packet(
        self,
        *,
        chat_id: int,
        sender_user_id: int,
        total_amount: int,
        packet_count: int,
        split_mode: str,
        blessing: str | None,
        settings: ChatSettings,
        operator: str,
        expires_in_seconds: int = 24 * 3600,
    ) -> dict[str, Any]:
        if not settings.points_enabled:
            raise ValueError("points_disabled")
        if total_amount <= 0:
            raise ValueError("packet_amount_invalid")
        if packet_count <= 0:
            raise ValueError("packet_count_invalid")
        if split_mode not in {PACKET_MODE_EQUAL, PACKET_MODE_RANDOM}:
            raise ValueError("packet_split_mode_invalid")
        if split_mode == PACKET_MODE_EQUAL and total_amount % packet_count != 0:
            raise ValueError("packet_equal_amount_not_divisible")
        if packet_count > total_amount:
            raise ValueError("packet_count_exceeds_amount")

        debit = self.repo.adjust_points(
            chat_id=chat_id,
            user_id=sender_user_id,
            amount=-total_amount,
            event_type="packet_send_out",
            operator=operator,
            reason=f"hongbao:{split_mode}",
        )
        packet = self.repo.create_points_packet(
            chat_id=chat_id,
            sender_user_id=sender_user_id,
            total_amount=total_amount,
            packet_count=packet_count,
            split_mode=split_mode,
            blessing=(blessing or "").strip() or None,
            expires_at=to_iso(utc_now().replace(microsecond=0)) if expires_in_seconds <= 0 else to_iso(utc_now() + timedelta(seconds=expires_in_seconds)),
        )
        return {
            "packet": packet,
            "sender_balance_after": debit["balance_after"],
            "ledger_id": debit["ledger_id"],
        }

    def claim_packet(self, packet_id: int, receiver_user_id: int, *, operator: str) -> dict[str, Any]:
        packet = self.repo.get_points_packet(packet_id)
        if packet is None:
            raise ValueError("packet_not_found")
        if packet["status"] != PACKET_STATUS_ACTIVE:
            raise ValueError("packet_not_active")
        if self.repo.parse_iso_datetime(str(packet["expires_at"])) <= utc_now():
            raise ValueError("packet_expired")
        if self.repo.get_points_packet_claim(packet_id, receiver_user_id) is not None:
            raise ValueError("packet_already_claimed")
        if int(packet["remaining_count"]) <= 0 or int(packet["remaining_amount"]) <= 0:
            raise ValueError("packet_empty")

        amount = self._allocate_amount(packet)
        credit = self.repo.adjust_points(
            chat_id=int(packet["chat_id"]),
            user_id=receiver_user_id,
            amount=amount,
            event_type="packet_claim_in",
            operator=operator,
            reason=f"hongbao:{packet_id}:claim",
            counterparty_user_id=int(packet["sender_user_id"]),
        )
        claim = self.repo.create_points_packet_claim(
            packet_id=packet_id,
            chat_id=int(packet["chat_id"]),
            receiver_user_id=receiver_user_id,
            amount=amount,
            ledger_id=int(credit["ledger_id"]),
        )
        next_remaining_amount = max(int(packet["remaining_amount"]) - amount, 0)
        next_remaining_count = max(int(packet["remaining_count"]) - 1, 0)
        next_claimed_amount = int(packet["claimed_amount"]) + amount
        next_claimed_count = int(packet["claimed_count"]) + 1
        next_status = PACKET_STATUS_FULLY_CLAIMED if next_remaining_amount == 0 or next_remaining_count == 0 else PACKET_STATUS_ACTIVE
        updated = self.repo.update_points_packet(
            packet_id,
            status=next_status,
            claimed_amount=next_claimed_amount,
            claimed_count=next_claimed_count,
            remaining_amount=next_remaining_amount,
            remaining_count=next_remaining_count,
        )
        return {
            "packet": updated,
            "claim": claim,
            "receiver_balance_after": credit["balance_after"],
        }

    def expire_due_packets(self) -> list[dict[str, Any]]:
        expired: list[dict[str, Any]] = []
        for packet in self.repo.list_due_points_packets(to_iso(utc_now())):
            if int(packet["remaining_amount"]) > 0:
                self.repo.add_pool_ledger(
                    chat_id=int(packet["chat_id"]),
                    change_amount=int(packet["remaining_amount"]),
                    event_type="packet_expired_to_pool",
                    operator="system",
                    reason=f"hongbao:{packet['id']}:expired",
                    related_packet_id=int(packet["id"]),
                )
            updated = self.repo.update_points_packet(
                int(packet["id"]),
                status=PACKET_STATUS_EXPIRED,
                remaining_amount=0,
                remaining_count=0,
            )
            if updated is not None:
                expired.append(updated)
        return expired

    def render_packet_text(self, packet: dict[str, Any], settings: ChatSettings, sender_name: str) -> str:
        packet_type = "拼手气红包" if str(packet.get("split_mode")) == PACKET_MODE_RANDOM else "普通红包"
        blessing = str(packet.get("blessing") or "").strip() or "恭喜发财，大吉大利"
        body = settings.hongbao_template.format(
            sender=sender_name,
            total_amount=packet["total_amount"],
            packet_count=packet["packet_count"],
            packet_type=packet_type,
            blessing=blessing,
            chat="当前群聊",
        )
        status_line = f"已领取 {packet['claimed_count']}/{packet['packet_count']} 份，剩余 {packet['remaining_amount']} {CURRENCY_LABEL}"
        if packet["status"] == PACKET_STATUS_FULLY_CLAIMED:
            status_line = f"已抢完，共领取 {packet['claimed_amount']} {CURRENCY_LABEL}"
        elif packet["status"] == PACKET_STATUS_EXPIRED:
            status_line = f"红包已过期，未领取金额已转入群资金池"
        return f"🧧 <b>{packet_type}</b>\n{body}\n\n{status_line}"

    def _allocate_amount(self, packet: dict[str, Any]) -> int:
        remaining_amount = int(packet["remaining_amount"])
        remaining_count = int(packet["remaining_count"])
        if remaining_count <= 1:
            return remaining_amount
        if str(packet["split_mode"]) == PACKET_MODE_EQUAL:
            return remaining_amount // remaining_count
        max_pick = remaining_amount - (remaining_count - 1)
        upper = max(1, min(max_pick, (remaining_amount // remaining_count) * 2))
        return random.randint(1, upper)
