from __future__ import annotations

import json
import random
from collections import defaultdict
from typing import Any

from bot.storage.repo import BotRepository
from bot.utils.time import to_iso, utc_now

ENTRY_MODE_FREE = "free"
ENTRY_MODE_CONSUME = "consume_points"
ENTRY_MODE_THRESHOLD = "balance_threshold"
PRIZE_SOURCE_PERSONAL = "personal_points"
PRIZE_SOURCE_POOL = "group_pool"


class LotteryService:
    def __init__(self, repo: BotRepository) -> None:
        self.repo = repo

    def create_lottery(self, chat_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        prizes = list(payload.pop("prizes", []))
        payload.setdefault("prize_source", PRIZE_SOURCE_PERSONAL)
        payload.pop("chat_id", None)
        lottery = self.repo.create_lottery(chat_id=chat_id, **payload)
        self.repo.replace_lottery_prizes(int(lottery["id"]), prizes)
        return self.get_lottery_detail(int(lottery["id"]))

    def update_lottery(self, lottery_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        prizes = payload.pop("prizes", None)
        payload.setdefault("prize_source", PRIZE_SOURCE_PERSONAL)
        lottery = self.repo.update_lottery(lottery_id, payload)
        if lottery is None:
            raise ValueError("lottery_not_found")
        if prizes is not None:
            self.repo.replace_lottery_prizes(lottery_id, list(prizes))
        return self.get_lottery_detail(lottery_id)

    def get_lottery_detail(self, lottery_id: int) -> dict[str, Any]:
        lottery = self.repo.get_lottery(lottery_id)
        if lottery is None:
            raise ValueError("lottery_not_found")
        return {
            **lottery,
            "prizes": self.repo.list_lottery_prizes(lottery_id),
            "stats": self.repo.get_lottery_stats(lottery_id),
            "winners": self.repo.list_lottery_winners(lottery_id),
        }

    def list_lotteries(self, chat_id: int) -> list[dict[str, Any]]:
        rows = self.repo.list_lotteries(chat_id)
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    **row,
                    "prizes": self.repo.list_lottery_prizes(int(row["id"])),
                    "stats": self.repo.get_lottery_stats(int(row["id"])),
                    "winners": self.repo.list_lottery_winners(int(row["id"])),
                }
            )
        return result

    def join_lottery(self, lottery_id: int, user_id: int, join_count: int = 1, source: str = "telegram") -> dict[str, Any]:
        lottery = self.repo.get_lottery(lottery_id)
        if lottery is None:
            raise ValueError("lottery_not_found")
        if lottery["status"] != "active":
            raise ValueError("lottery_not_active")
        now = utc_now()
        starts_at = self.repo.parse_iso_datetime(str(lottery["starts_at"]))
        deadline_at = self.repo.parse_iso_datetime(str(lottery["entry_deadline_at"]))
        if now < starts_at:
            raise ValueError("lottery_not_started")
        if now > deadline_at:
            raise ValueError("lottery_entry_closed")
        if join_count <= 0:
            raise ValueError("invalid_join_count")

        stats = self.repo.get_lottery_user_entry_stats(lottery_id, user_id)
        allow_multiple = bool(lottery["allow_multiple_entries"])
        max_entries = max(int(lottery["max_entries_per_user"]), 1)
        current_entries = int(stats["total_entry_count"])
        if not allow_multiple and current_entries > 0:
            raise ValueError("lottery_already_joined")
        if current_entries + join_count > max_entries:
            raise ValueError("lottery_entry_limit_reached")

        points_spent = 0
        ledger_id: int | None = None
        if lottery["entry_mode"] == ENTRY_MODE_CONSUME:
            points_spent = int(lottery["points_cost"]) * join_count
            entry = self.repo.adjust_points(
                chat_id=int(lottery["chat_id"]),
                user_id=user_id,
                amount=-points_spent,
                event_type="lottery_entry_fee",
                operator="system",
                reason=f"lottery:{lottery_id}:entry",
            )
            ledger_id = int(entry["ledger_id"])
        elif lottery["entry_mode"] == ENTRY_MODE_THRESHOLD:
            balance = self.repo.get_points_balance(int(lottery["chat_id"]), user_id)
            if int(balance["balance"]) < int(lottery["points_threshold"]):
                raise ValueError("lottery_threshold_not_met")

        self.repo.create_lottery_entry(
            lottery_id=lottery_id,
            chat_id=int(lottery["chat_id"]),
            user_id=user_id,
            entry_count=join_count,
            points_spent=points_spent,
            source=source,
            ledger_id=ledger_id,
        )
        return {
            "lottery": lottery,
            "user_stats": self.repo.get_lottery_user_entry_stats(lottery_id, user_id),
            "stats": self.repo.get_lottery_stats(lottery_id),
        }

    def cancel_lottery(self, lottery_id: int, operator: str) -> dict[str, Any]:
        lottery = self.repo.get_lottery(lottery_id)
        if lottery is None:
            raise ValueError("lottery_not_found")
        if lottery["status"] == "drawn":
            raise ValueError("lottery_already_drawn")
        if lottery["status"] == "canceled":
            return self.get_lottery_detail(lottery_id)

        refunded_entries = 0
        refunded_points = 0
        for entry in self.repo.list_lottery_entries(lottery_id):
            if int(entry["points_spent"]) <= 0:
                continue
            if entry["status"] == "refunded":
                continue
            refund = self.repo.adjust_points(
                chat_id=int(entry["chat_id"]),
                user_id=int(entry["user_id"]),
                amount=int(entry["points_spent"]),
                event_type="lottery_entry_refund",
                operator=operator,
                reason=f"lottery:{lottery_id}:refund",
            )
            self.repo.mark_lottery_entry_refunded(int(entry["id"]), int(refund["ledger_id"]))
            refunded_entries += 1
            refunded_points += int(entry["points_spent"])

        summary = {"refunded_entries": refunded_entries, "refunded_points": refunded_points}
        self.repo.update_lottery_status(lottery_id, status="canceled", operator=operator, summary_json=json.dumps(summary, ensure_ascii=False))
        return self.get_lottery_detail(lottery_id)

    def draw_lottery(self, lottery_id: int, operator: str = "system") -> dict[str, Any]:
        lottery = self.repo.get_lottery(lottery_id)
        if lottery is None:
            raise ValueError("lottery_not_found")
        if lottery["status"] == "canceled":
            raise ValueError("lottery_canceled")
        if lottery["status"] == "drawn":
            return self.get_lottery_detail(lottery_id)

        prizes = self.repo.list_lottery_prizes(lottery_id)
        total_bonus_points = sum(max(int(prize.get("bonus_points", 0)), 0) * max(int(prize.get("winner_count", 0)), 0) for prize in prizes)
        if str(lottery.get("prize_source") or PRIZE_SOURCE_PERSONAL) == PRIZE_SOURCE_POOL and total_bonus_points > 0:
            pool = self.repo.get_points_pool_balance(int(lottery["chat_id"]))
            if int(pool["balance"]) < total_bonus_points:
                raise ValueError("lottery_pool_insufficient")
        entries = self.repo.list_lottery_entries(lottery_id)
        weighted_pool: list[dict[str, Any]] = []
        grouped = defaultdict(lambda: {"user_id": 0, "entry_count": 0})
        for entry in entries:
            if entry["status"] != "joined":
                continue
            grouped[int(entry["user_id"])]["user_id"] = int(entry["user_id"])
            grouped[int(entry["user_id"])]["entry_count"] += int(entry["entry_count"])
        weighted_pool = list(grouped.values())

        winners: list[dict[str, Any]] = []
        excluded_users: set[int] = set()
        for prize in prizes:
            winner_count = max(int(prize["winner_count"]), 0)
            for _ in range(winner_count):
                candidate = self._pick_weighted_winner(weighted_pool, excluded_users)
                if candidate is None:
                    break
                excluded_users.add(int(candidate["user_id"]))
                winner = self.repo.save_lottery_winner(
                    lottery_id=lottery_id,
                    prize_id=int(prize["id"]),
                    chat_id=int(lottery["chat_id"]),
                    user_id=int(candidate["user_id"]),
                    prize_title=str(prize["title"]),
                    sort_order=int(prize["sort_order"]),
                    entry_count=int(candidate["entry_count"]),
                    snapshot_json=json.dumps({"entry_count": int(candidate["entry_count"])}, ensure_ascii=False),
                )
                bonus_points = max(int(prize.get("bonus_points", 0)), 0)
                if bonus_points > 0:
                    self.repo.adjust_points(
                        chat_id=int(lottery["chat_id"]),
                        user_id=int(candidate["user_id"]),
                        amount=bonus_points,
                        event_type="lottery_prize_reward",
                        operator=operator,
                        reason=f"lottery:{lottery_id}:prize:{prize['id']}",
                    )
                winners.append(winner)

        if str(lottery.get("prize_source") or PRIZE_SOURCE_PERSONAL) == PRIZE_SOURCE_POOL and total_bonus_points > 0:
            self.repo.add_pool_ledger(
                chat_id=int(lottery["chat_id"]),
                change_amount=-total_bonus_points,
                event_type="pool_lottery_out",
                operator=operator,
                reason=f"lottery:{lottery_id}:draw",
                related_lottery_id=lottery_id,
            )
        summary = {
            "winner_count": len(winners),
            "drawn_at": to_iso(utc_now()),
            "bonus_points": total_bonus_points,
        }
        self.repo.update_lottery_status(lottery_id, status="drawn", operator=operator, summary_json=json.dumps(summary, ensure_ascii=False))
        return self.get_lottery_detail(lottery_id)

    def draw_due_lotteries(self, now=None) -> list[dict[str, Any]]:
        current = now or utc_now()
        drawn: list[dict[str, Any]] = []
        for lottery in self.repo.list_due_lotteries(to_iso(current)):
            try:
                drawn.append(self.draw_lottery(int(lottery["id"]), operator="system"))
            except ValueError:
                continue
        return drawn

    @staticmethod
    def _pick_weighted_winner(pool: list[dict[str, Any]], excluded_users: set[int]) -> dict[str, Any] | None:
        candidates = [item for item in pool if int(item["user_id"]) not in excluded_users and int(item["entry_count"]) > 0]
        if not candidates:
            return None
        total_weight = sum(int(item["entry_count"]) for item in candidates)
        hit = random.randint(1, total_weight)
        acc = 0
        for item in candidates:
            acc += int(item["entry_count"])
            if acc >= hit:
                return item
        return candidates[-1]
