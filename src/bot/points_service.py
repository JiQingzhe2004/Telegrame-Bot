from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from bot.domain.models import ChatSettings
from bot.storage.repo import BotRepository
from bot.utils.time import to_iso, utc_now


DEFAULT_TASKS = [
    {
        "task_key": "daily_messages",
        "title": "今日发言",
        "description": "当天完成 5 次有效发言",
        "task_type": "message_count",
        "target_value": 5,
        "reward_points": 5,
        "period": "daily",
        "enabled": True,
    },
    {
        "task_key": "daily_checkin",
        "title": "今日签到",
        "description": "完成当日签到",
        "task_type": "checkin_once",
        "target_value": 1,
        "reward_points": 2,
        "period": "daily",
        "enabled": True,
    },
    {
        "task_key": "daily_verification",
        "title": "验证成功",
        "description": "当天完成一次入群验证",
        "task_type": "verification_pass",
        "target_value": 1,
        "reward_points": 3,
        "period": "daily",
        "enabled": True,
    },
]

DEFAULT_SHOP_ITEMS = [
    {
        "item_key": "leaderboard_title",
        "title": "积分榜头衔",
        "description": "申请一个积分榜专属头衔，等待管理员或机器人设置。",
        "item_type": "leaderboard_title",
        "price_points": 30,
        "stock": None,
        "enabled": True,
        "meta_json": json.dumps({"title": "积分榜之星"}, ensure_ascii=False),
    },
    {
        "item_key": "welcome_bonus",
        "title": "欢迎语彩蛋",
        "description": "为你下一次加入群聊时的欢迎语附加彩蛋效果。",
        "item_type": "welcome_bonus",
        "price_points": 15,
        "stock": None,
        "enabled": True,
        "meta_json": json.dumps({"template": "欢迎 {user} 闪亮登场，今天也请在 {chat} 玩得开心。"}, ensure_ascii=False),
    },
]


class PointsService:
    def __init__(self, repo: BotRepository) -> None:
        self.repo = repo

    @staticmethod
    def _period_key_daily() -> str:
        return utc_now().strftime("%Y-%m-%d")

    def ensure_defaults(self, chat_id: int) -> None:
        existing_task_keys = {str(item["task_key"]) for item in self.repo.list_points_tasks(chat_id)}
        for task in DEFAULT_TASKS:
            if str(task["task_key"]) in existing_task_keys:
                continue
            self.repo.upsert_points_task(chat_id=chat_id, **task)

        existing_item_keys = {str(item["item_key"]) for item in self.repo.list_shop_items(chat_id)}
        for item in DEFAULT_SHOP_ITEMS:
            if str(item["item_key"]) in existing_item_keys:
                continue
            self.repo.upsert_shop_item(chat_id=chat_id, **item)

    def get_checkin_state(self, chat_id: int, user_id: int) -> dict[str, Any]:
        return self.repo.get_checkin_state(chat_id, user_id)

    def checkin(self, chat_id: int, user_id: int, settings: ChatSettings) -> dict[str, Any]:
        self.ensure_defaults(chat_id)
        state = self.repo.get_checkin_state(chat_id, user_id)
        today = self._period_key_daily()
        if state.get("last_checkin_date") == today:
            raise ValueError("already_checked_in_today")

        streak_days = 1
        last_date = state.get("last_checkin_date")
        if last_date:
            prev = utc_now().date() - timedelta(days=1)
            if last_date == prev.strftime("%Y-%m-%d"):
                streak_days = int(state.get("streak_days", 0)) + 1
        streak_days = min(streak_days, settings.points_checkin_streak_cap)
        reward = settings.points_checkin_base_reward + max(streak_days - 1, 0) * settings.points_checkin_streak_bonus
        account_entry = self.repo.adjust_points(
            chat_id=chat_id,
            user_id=user_id,
            amount=reward,
            event_type="checkin_reward",
            operator="system",
            reason="daily_checkin",
        )
        self.repo.save_checkin_state(chat_id, user_id, streak_days, today)
        completed = self._advance_task(chat_id, user_id, "daily_checkin", increment=1)
        return {
            "reward_points": reward,
            "streak_days": streak_days,
            "balance_after": account_entry["balance_after"],
            "task_rewards": completed,
        }

    def _advance_task(self, chat_id: int, user_id: int, task_key: str, increment: int = 1) -> list[dict[str, Any]]:
        task = self.repo.get_points_task(chat_id, task_key)
        if not task or not bool(task.get("enabled")):
            return []
        period_key = self._period_key_daily()
        progress = self.repo.get_task_progress(chat_id, user_id, int(task["id"]), period_key)
        if bool(progress.get("reward_claimed")):
            return []
        next_value = min(int(progress.get("progress_value", 0)) + increment, int(task["target_value"]))
        completed = next_value >= int(task["target_value"])
        rewards: list[dict[str, Any]] = []
        reward_claimed = bool(progress.get("reward_claimed"))
        if completed and not reward_claimed:
            entry = self.repo.adjust_points(
                chat_id=chat_id,
                user_id=user_id,
                amount=int(task["reward_points"]),
                event_type="task_reward",
                operator="system",
                reason=task_key,
            )
            rewards.append({"task_key": task_key, "reward_points": int(task["reward_points"]), "balance_after": entry["balance_after"]})
            reward_claimed = True
        self.repo.save_task_progress(
            chat_id=chat_id,
            user_id=user_id,
            task_id=int(task["id"]),
            period_key=period_key,
            progress_value=next_value,
            completed=completed,
            reward_claimed=reward_claimed,
        )
        return rewards

    def handle_message_activity(self, chat_id: int, user_id: int, text: str | None, settings: ChatSettings) -> dict[str, Any]:
        self.ensure_defaults(chat_id)
        reward = self.repo.maybe_reward_message_points(chat_id, user_id, text, settings)
        task_rewards: list[dict[str, Any]] = []
        if reward.get("awarded"):
            task_rewards = self._advance_task(chat_id, user_id, "daily_messages", increment=1)
        return {"reward": reward, "task_rewards": task_rewards}

    def handle_verification_pass(self, chat_id: int, user_id: int) -> list[dict[str, Any]]:
        self.ensure_defaults(chat_id)
        return self._advance_task(chat_id, user_id, "daily_verification", increment=1)

    def list_tasks_for_user(self, chat_id: int, user_id: int) -> list[dict[str, Any]]:
        self.ensure_defaults(chat_id)
        tasks = self.repo.list_points_tasks(chat_id)
        progress_rows = {
            row["task_id"]: row for row in self.repo.list_points_task_progress(chat_id, self._period_key_daily(), user_id=user_id)
        }
        result = []
        for task in tasks:
            progress = progress_rows.get(task["id"]) or {
                "progress_value": 0,
                "completed": 0,
                "reward_claimed": 0,
            }
            result.append({
                **task,
                "progress_value": progress["progress_value"],
                "completed": bool(progress["completed"]),
                "reward_claimed": bool(progress["reward_claimed"]),
            })
        return result

    def list_task_config(self, chat_id: int) -> list[dict[str, Any]]:
        self.ensure_defaults(chat_id)
        return self.repo.list_points_tasks(chat_id)

    def update_task_config(self, chat_id: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.ensure_defaults(chat_id)
        for item in items:
            self.repo.upsert_points_task(
                chat_id=chat_id,
                task_key=str(item["task_key"]),
                title=str(item["title"]),
                description=str(item.get("description", "")),
                task_type=str(item["task_type"]),
                target_value=int(item["target_value"]),
                reward_points=int(item["reward_points"]),
                period=str(item.get("period", "daily")),
                enabled=bool(item.get("enabled", True)),
            )
        return self.repo.list_points_tasks(chat_id)

    def list_shop(self, chat_id: int) -> list[dict[str, Any]]:
        self.ensure_defaults(chat_id)
        return self.repo.list_shop_items(chat_id)

    def update_shop(self, chat_id: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.ensure_defaults(chat_id)
        for item in items:
            self.repo.upsert_shop_item(
                chat_id=chat_id,
                item_key=str(item["item_key"]),
                title=str(item["title"]),
                description=str(item.get("description", "")),
                item_type=str(item["item_type"]),
                price_points=int(item["price_points"]),
                stock=None if item.get("stock") in {None, ""} else int(item["stock"]),
                enabled=bool(item.get("enabled", True)),
                meta_json=json.dumps(item.get("meta", {}), ensure_ascii=False),
            )
        return self.repo.list_shop_items(chat_id)

    def redeem(self, chat_id: int, user_id: int, item_key: str) -> dict[str, Any]:
        self.ensure_defaults(chat_id)
        item = self.repo.get_shop_item(chat_id, item_key)
        if not item or not bool(item.get("enabled")):
            raise ValueError("shop_item_unavailable")
        stock = item.get("stock")
        if stock is not None and int(stock) <= 0:
            raise ValueError("shop_item_out_of_stock")
        debit = self.repo.adjust_points(
            chat_id=chat_id,
            user_id=user_id,
            amount=-int(item["price_points"]),
            event_type="redeem_out",
            operator="system",
            reason=item_key,
        )
        status = "pending" if item["item_type"] == "leaderboard_title" else "active"
        expires_at = to_iso(utc_now() + timedelta(days=7)) if item["item_type"] == "welcome_bonus" else None
        reward_payload = item.get("meta_json")
        redemption = self.repo.save_redemption(
            chat_id=chat_id,
            user_id=user_id,
            item_id=int(item["id"]),
            price_points=int(item["price_points"]),
            status=status,
            reward_payload=reward_payload,
            expires_at=expires_at,
        )
        if stock is not None:
            self.repo.upsert_shop_item(
                chat_id=chat_id,
                item_key=str(item["item_key"]),
                title=str(item["title"]),
                description=str(item.get("description", "")),
                item_type=str(item["item_type"]),
                price_points=int(item["price_points"]),
                stock=max(int(stock) - 1, 0),
                enabled=bool(item.get("enabled")),
                meta_json=item.get("meta_json"),
            )
        return {"redemption": redemption, "balance_after": debit["balance_after"], "item": item}

    def list_redemptions(self, chat_id: int, user_id: int | None = None) -> list[dict[str, Any]]:
        return self.repo.list_redemptions(chat_id, user_id=user_id)

    def get_active_welcome_bonus(self, chat_id: int, user_id: int) -> dict[str, Any] | None:
        return self.repo.get_active_welcome_bonus(chat_id, user_id)

    def consume_welcome_bonus(self, redemption_id: int) -> dict[str, Any] | None:
        return self.repo.update_redemption_status(redemption_id, "consumed")

    def update_redemption_status(self, redemption_id: int, status: str) -> dict[str, Any] | None:
        return self.repo.update_redemption_status(redemption_id, status)

    def transfer_points(self, chat_id: int, from_user_id: int, to_user_id: int, amount: int, settings: ChatSettings, operator: str) -> dict[str, Any]:
        if self.repo.get_points_transfer_count_today(chat_id, from_user_id) >= settings.points_transfer_daily_limit:
            raise ValueError("transfer_daily_limit_reached")
        return self.repo.transfer_points(
            chat_id=chat_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            amount=amount,
            operator=operator,
            reason="user_transfer",
        )
