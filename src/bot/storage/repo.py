from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from bot.domain.models import (
    ChatRef,
    ChatSettings,
    EnforcementResult,
    MessageRef,
    ModerationDecision,
    UserRef,
)
from bot.storage.db import Database
from bot.utils.time import to_iso, utc_now


class BotRepository:
    def __init__(self, db: Database, defaults: dict[str, Any]) -> None:
        self.db = db
        self.defaults = defaults

    def upsert_chat(self, chat: ChatRef) -> None:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO chats(chat_id, title, type, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title, type=excluded.type, updated_at=excluded.updated_at
                """,
                (chat.chat_id, chat.title, chat.type, now, now),
            )
            conn.execute(
                """
                INSERT INTO chat_settings(chat_id, mode, ai_enabled, ai_threshold, allow_admin_self_test, action_policy, rate_limit_policy, language, level3_mute_seconds, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO NOTHING
                """,
                (
                    chat.chat_id,
                    self.defaults["mode"],
                    1 if self.defaults["ai_enabled"] else 0,
                    self.defaults["ai_threshold"],
                    1 if self.defaults.get("allow_admin_self_test", False) else 0,
                    self.defaults["action_policy"],
                    self.defaults["rate_limit_policy"],
                    self.defaults["language"],
                    self.defaults["level3_mute_seconds"],
                    now,
                ),
            )

    def upsert_chat_user(self, chat: ChatRef, user: UserRef) -> None:
        self.upsert_chat(chat)
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO users(user_id, username, first_name, last_name, is_bot, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name, last_name=excluded.last_name, is_bot=excluded.is_bot, updated_at=excluded.updated_at
                """,
                (user.user_id, user.username, user.first_name, user.last_name, 1 if user.is_bot else 0, now),
            )

    def get_chat(self, chat_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT chat_id, title, type, created_at, updated_at FROM chats WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_settings(self, chat_id: int) -> ChatSettings:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM chat_settings WHERE chat_id = ?", (chat_id,)).fetchone()
        if not row:
            return ChatSettings(chat_id=chat_id, **self.defaults)
        return ChatSettings(
            chat_id=chat_id,
            mode=row["mode"],
            ai_enabled=bool(row["ai_enabled"]),
            ai_threshold=float(row["ai_threshold"]),
            allow_admin_self_test=bool(row["allow_admin_self_test"]),
            action_policy=row["action_policy"],
            rate_limit_policy=row["rate_limit_policy"],
            language=row["language"],
            level3_mute_seconds=int(row["level3_mute_seconds"]),
            points_enabled=bool(row["points_enabled"]),
            points_message_reward=int(row["points_message_reward"]),
            points_message_cooldown_seconds=int(row["points_message_cooldown_seconds"]),
            points_daily_cap=int(row["points_daily_cap"]),
            points_transfer_enabled=bool(row["points_transfer_enabled"]),
            points_transfer_min_amount=int(row["points_transfer_min_amount"]),
            points_transfer_daily_limit=int(row["points_transfer_daily_limit"]),
            points_checkin_base_reward=int(row["points_checkin_base_reward"]),
            points_checkin_streak_bonus=int(row["points_checkin_streak_bonus"]),
            points_checkin_streak_cap=int(row["points_checkin_streak_cap"]),
        )

    def update_settings(self, chat_id: int, payload: dict[str, Any]) -> None:
        current = self.get_settings(chat_id)
        new = asdict(current) | payload
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_settings(
                  chat_id, mode, ai_enabled, ai_threshold, allow_admin_self_test, action_policy, rate_limit_policy, language,
                  level3_mute_seconds, points_enabled, points_message_reward, points_message_cooldown_seconds, points_daily_cap,
                  points_transfer_enabled, points_transfer_min_amount, points_transfer_daily_limit,
                  points_checkin_base_reward, points_checkin_streak_bonus, points_checkin_streak_cap, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                  mode=excluded.mode,
                  ai_enabled=excluded.ai_enabled,
                  ai_threshold=excluded.ai_threshold,
                  allow_admin_self_test=excluded.allow_admin_self_test,
                  action_policy=excluded.action_policy,
                  rate_limit_policy=excluded.rate_limit_policy,
                  language=excluded.language,
                  level3_mute_seconds=excluded.level3_mute_seconds,
                  points_enabled=excluded.points_enabled,
                  points_message_reward=excluded.points_message_reward,
                  points_message_cooldown_seconds=excluded.points_message_cooldown_seconds,
                  points_daily_cap=excluded.points_daily_cap,
                  points_transfer_enabled=excluded.points_transfer_enabled,
                  points_transfer_min_amount=excluded.points_transfer_min_amount,
                  points_transfer_daily_limit=excluded.points_transfer_daily_limit,
                  points_checkin_base_reward=excluded.points_checkin_base_reward,
                  points_checkin_streak_bonus=excluded.points_checkin_streak_bonus,
                  points_checkin_streak_cap=excluded.points_checkin_streak_cap,
                  updated_at=excluded.updated_at
                """,
                (
                    chat_id,
                    new["mode"],
                    1 if new["ai_enabled"] else 0,
                    float(new["ai_threshold"]),
                    1 if new["allow_admin_self_test"] else 0,
                    new["action_policy"],
                    new["rate_limit_policy"],
                    new["language"],
                    int(new["level3_mute_seconds"]),
                    1 if new["points_enabled"] else 0,
                    int(new["points_message_reward"]),
                    int(new["points_message_cooldown_seconds"]),
                    int(new["points_daily_cap"]),
                    1 if new["points_transfer_enabled"] else 0,
                    int(new["points_transfer_min_amount"]),
                    int(new["points_transfer_daily_limit"]),
                    int(new["points_checkin_base_reward"]),
                    int(new["points_checkin_streak_bonus"]),
                    int(new["points_checkin_streak_cap"]),
                    to_iso(utc_now()),
                ),
            )

    @staticmethod
    def parse_iso_datetime(value: str) -> datetime:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    def get_blacklist_words(self, chat_id: int) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT value FROM blacklists WHERE chat_id = ? AND type = 'word' ORDER BY id DESC",
                (chat_id,),
            ).fetchall()
        return [r["value"] for r in rows]

    def add_list_item(self, table: str, chat_id: int, item_type: str, value: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                f"INSERT INTO {table}(chat_id, type, value, created_at) VALUES(?, ?, ?, ?)",
                (chat_id, item_type, value, to_iso(utc_now())),
            )

    def delete_list_item(self, table: str, chat_id: int, item_type: str, value: str) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                f"DELETE FROM {table} WHERE chat_id = ? AND type = ? AND value = ?",
                (chat_id, item_type, value),
            )
            return cur.rowcount

    def list_items(self, table: str, chat_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT id, type, value, created_at FROM {table} WHERE chat_id = ? ORDER BY id DESC",
                (chat_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def is_whitelisted(self, chat_id: int, user_id: int, username: str | None) -> bool:
        values = {str(user_id)}
        if username:
            values.add(f"@{username}")
            values.add(username)
        with self.db.connect() as conn:
            q = ",".join("?" for _ in values)
            row = conn.execute(
                f"SELECT 1 FROM whitelists WHERE chat_id = ? AND type = 'user' AND value IN ({q}) LIMIT 1",
                (chat_id, *values),
            ).fetchone()
            return bool(row)

    def recent_texts(self, chat_id: int, user_id: int, limit: int = 6) -> list[str]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT text FROM messages
                WHERE chat_id = ? AND user_id = ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (chat_id, user_id, limit),
            ).fetchall()
        return [r["text"] for r in rows if r["text"]]

    def save_violation_message(self, message: MessageRef, redacted_text: str | None = None) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO messages(chat_id, message_id, user_id, date, text, meta)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    message.chat_id,
                    message.message_id,
                    message.user_id,
                    to_iso(message.date),
                    redacted_text or "",
                    json.dumps(message.meta, ensure_ascii=False),
                ),
            )

    def save_decision(self, message: MessageRef, decision: ModerationDecision, ai_model: str | None = None) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO moderation_decisions(
                  chat_id,
                  message_id,
                  user_id,
                  rule_hit,
                  ai_used,
                  ai_status,
                  ai_error,
                  ai_model,
                  ai_input_ref,
                  ai_output,
                  final_level,
                  confidence,
                  created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.chat_id,
                    message.message_id,
                    message.user_id,
                    ",".join(decision.reason_codes),
                    1 if decision.ai_used else 0,
                    decision.ai_status,
                    decision.ai_error,
                    ai_model,
                    None,
                    json.dumps(decision.ai_decision.raw, ensure_ascii=False) if decision.ai_decision else None,
                    decision.final_level,
                    decision.confidence,
                    to_iso(utc_now()),
                ),
            )
            return int(cur.lastrowid)

    def save_enforcement(
        self,
        message: MessageRef,
        enforcement: EnforcementResult,
        operator: str = "bot",
    ) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO enforcements(chat_id, user_id, message_id, action, duration_seconds, reason, operator, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.chat_id,
                    message.user_id,
                    message.message_id,
                    enforcement.applied_action,
                    enforcement.duration_seconds,
                    enforcement.reason,
                    operator,
                    to_iso(utc_now()),
                ),
            )
            return int(cur.lastrowid)

    def get_strike_score(self, chat_id: int, user_id: int) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT score FROM user_strikes WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            ).fetchone()
        return int(row["score"]) if row else 0

    def add_strike(self, chat_id: int, user_id: int, inc: int = 1) -> int:
        score = self.get_strike_score(chat_id, user_id) + inc
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_strikes(chat_id, user_id, score, last_violation_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                  score=excluded.score, last_violation_at=excluded.last_violation_at
                """,
                (chat_id, user_id, score, to_iso(utc_now())),
            )
        return score

    def forgive(self, chat_id: int, user_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "DELETE FROM user_strikes WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )

    def add_appeal(self, chat_id: int, user_id: int, message: str) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO appeals(chat_id, user_id, message, created_at) VALUES(?, ?, ?, ?)",
                (chat_id, user_id, message, to_iso(utc_now())),
            )
            return int(cur.lastrowid)

    def list_appeals(self, chat_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT id, chat_id, user_id, message, created_at FROM appeals WHERE chat_id = ? ORDER BY id DESC",
                (chat_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_audits(self, chat_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  id,
                  chat_id,
                  message_id,
                  user_id,
                  rule_hit,
                  ai_used,
                  ai_status,
                  ai_error,
                  ai_model,
                  final_level,
                  confidence,
                  created_at
                FROM moderation_decisions
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_enforcements(self, chat_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, chat_id, user_id, message_id, action, duration_seconds, reason, operator, created_at
                FROM enforcements
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_enforcement(self, enforcement_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, chat_id, user_id, action FROM enforcements WHERE id = ?",
                (enforcement_id,),
            ).fetchone()
        return dict(row) if row else None

    def add_rollback(self, enforcement_id: int, chat_id: int, user_id: int, status: str, reason: str) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO enforcement_rollbacks(enforcement_id, chat_id, user_id, status, reason, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (enforcement_id, chat_id, user_id, status, reason, to_iso(utc_now())),
            )
            return int(cur.lastrowid)

    def status_summary(self) -> dict[str, Any]:
        with self.db.connect() as conn:
            decisions = conn.execute("SELECT COUNT(*) AS c FROM moderation_decisions").fetchone()["c"]
            enforcements = conn.execute("SELECT COUNT(*) AS c FROM enforcements").fetchone()["c"]
            ai_used = conn.execute("SELECT COUNT(*) AS c FROM moderation_decisions WHERE ai_used = 1").fetchone()["c"]
            point_accounts = conn.execute("SELECT COUNT(*) AS c FROM chat_points_accounts").fetchone()["c"]
            point_ledger = conn.execute("SELECT COUNT(*) AS c FROM chat_points_ledger").fetchone()["c"]
            latest = conn.execute(
                "SELECT created_at FROM moderation_decisions ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return {
            "decisions_total": int(decisions),
            "enforcements_total": int(enforcements),
            "ai_used_total": int(ai_used),
            "points_accounts_total": int(point_accounts),
            "points_ledger_total": int(point_ledger),
            "latest_decision_at": latest["created_at"] if latest else None,
        }

    def _get_points_account_row(self, chat_id: int, user_id: int) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT chat_id, user_id, balance, total_earned, total_spent, last_changed_at
                FROM chat_points_accounts
                WHERE chat_id = ? AND user_id = ?
                """,
                (chat_id, user_id),
            ).fetchone()
            if row is None:
                now = to_iso(utc_now())
                conn.execute(
                    """
                    INSERT INTO chat_points_accounts(chat_id, user_id, balance, total_earned, total_spent, last_changed_at)
                    VALUES(?, ?, 0, 0, 0, ?)
                    """,
                    (chat_id, user_id, now),
                )
                row = conn.execute(
                    """
                    SELECT chat_id, user_id, balance, total_earned, total_spent, last_changed_at
                    FROM chat_points_accounts
                    WHERE chat_id = ? AND user_id = ?
                    """,
                    (chat_id, user_id),
                ).fetchone()
        return dict(row)

    def get_points_balance(self, chat_id: int, user_id: int) -> dict[str, Any]:
        account = self._get_points_account_row(chat_id, user_id)
        with self.db.connect() as conn:
            user = conn.execute(
                "SELECT username, first_name, last_name FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return {
            **account,
            "username": user["username"] if user else None,
            "first_name": user["first_name"] if user else None,
            "last_name": user["last_name"] if user else None,
        }

    def list_points_leaderboard(self, chat_id: int, limit: int = 20) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  a.chat_id,
                  a.user_id,
                  a.balance,
                  a.total_earned,
                  a.total_spent,
                  a.last_changed_at,
                  u.username,
                  u.first_name,
                  u.last_name
                FROM chat_points_accounts a
                LEFT JOIN users u ON u.user_id = a.user_id
                WHERE a.chat_id = ?
                ORDER BY a.balance DESC, a.total_earned DESC, a.user_id ASC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_points_transfer_count_today(self, chat_id: int, user_id: int) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM chat_points_ledger
                WHERE chat_id = ?
                  AND user_id = ?
                  AND event_type = 'transfer_out'
                  AND date(created_at) = date('now')
                """,
                (chat_id, user_id),
            ).fetchone()
        return int(row["c"]) if row else 0

    def list_points_ledger(self, chat_id: int, limit: int = 100, user_id: int | None = None) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            if user_id is None:
                rows = conn.execute(
                    """
                    SELECT id, chat_id, user_id, counterparty_user_id, change_amount, balance_after, event_type, reason, operator, created_at
                    FROM chat_points_ledger
                    WHERE chat_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (chat_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, chat_id, user_id, counterparty_user_id, change_amount, balance_after, event_type, reason, operator, created_at
                    FROM chat_points_ledger
                    WHERE chat_id = ? AND user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (chat_id, user_id, limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def _today_points_earned(self, chat_id: int, user_id: int) -> int:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(change_amount), 0) AS earned
                FROM chat_points_ledger
                WHERE chat_id = ?
                  AND user_id = ?
                  AND event_type = 'message_reward'
                  AND change_amount > 0
                  AND date(created_at) = date('now')
                """,
                (chat_id, user_id),
            ).fetchone()
        return int(row["earned"]) if row else 0

    def _last_message_reward_at(self, chat_id: int, user_id: int) -> datetime | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT created_at
                FROM chat_points_ledger
                WHERE chat_id = ? AND user_id = ? AND event_type = 'message_reward'
                ORDER BY id DESC
                LIMIT 1
                """,
                (chat_id, user_id),
            ).fetchone()
        if not row or not row["created_at"]:
            return None
        return datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))

    def adjust_points(
        self,
        *,
        chat_id: int,
        user_id: int,
        amount: int,
        event_type: str,
        operator: str,
        reason: str | None = None,
        counterparty_user_id: int | None = None,
    ) -> dict[str, Any]:
        if amount == 0:
            raise ValueError("points_amount_must_not_be_zero")
        now = to_iso(utc_now())
        account = self._get_points_account_row(chat_id, user_id)
        current_balance = int(account["balance"])
        next_balance = current_balance + amount
        if next_balance < 0:
            raise ValueError("insufficient_points")
        total_earned = int(account["total_earned"]) + max(amount, 0)
        total_spent = int(account["total_spent"]) + max(-amount, 0)
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE chat_points_accounts
                SET balance = ?, total_earned = ?, total_spent = ?, last_changed_at = ?
                WHERE chat_id = ? AND user_id = ?
                """,
                (next_balance, total_earned, total_spent, now, chat_id, user_id),
            )
            cur = conn.execute(
                """
                INSERT INTO chat_points_ledger(chat_id, user_id, counterparty_user_id, change_amount, balance_after, event_type, reason, operator, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (chat_id, user_id, counterparty_user_id, amount, next_balance, event_type, reason, operator, now),
            )
        return {
            "ledger_id": int(cur.lastrowid),
            "chat_id": chat_id,
            "user_id": user_id,
            "counterparty_user_id": counterparty_user_id,
            "change_amount": amount,
            "balance_after": next_balance,
            "event_type": event_type,
            "reason": reason,
            "operator": operator,
            "created_at": now,
        }

    def maybe_reward_message_points(self, chat_id: int, user_id: int, text: str | None, settings: ChatSettings) -> dict[str, Any]:
        normalized = (text or "").strip()
        if not settings.points_enabled:
            return {"awarded": False, "reason": "points_disabled"}
        if not normalized:
            return {"awarded": False, "reason": "empty_message"}
        if settings.points_message_reward <= 0:
            return {"awarded": False, "reason": "reward_disabled"}
        now = utc_now()
        last_award = self._last_message_reward_at(chat_id, user_id)
        if last_award is not None:
            elapsed = (now - last_award.astimezone(now.tzinfo)).total_seconds()
            if elapsed < settings.points_message_cooldown_seconds:
                return {"awarded": False, "reason": "cooldown"}
        earned_today = self._today_points_earned(chat_id, user_id)
        if earned_today >= settings.points_daily_cap:
            return {"awarded": False, "reason": "daily_cap"}
        remaining_today = settings.points_daily_cap - earned_today
        award = min(settings.points_message_reward, remaining_today)
        if award <= 0:
            return {"awarded": False, "reason": "daily_cap"}
        entry = self.adjust_points(
            chat_id=chat_id,
            user_id=user_id,
            amount=award,
            event_type="message_reward",
            operator="system",
            reason="message_reward",
        )
        return {"awarded": True, "amount": award, "entry": entry}

    def transfer_points(
        self,
        *,
        chat_id: int,
        from_user_id: int,
        to_user_id: int,
        amount: int,
        operator: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("transfer_amount_must_be_positive")
        if from_user_id == to_user_id:
            raise ValueError("cannot_transfer_to_self")
        debit = self.adjust_points(
            chat_id=chat_id,
            user_id=from_user_id,
            amount=-amount,
            event_type="transfer_out",
            operator=operator,
            reason=reason or "points_transfer",
            counterparty_user_id=to_user_id,
        )
        credit = self.adjust_points(
            chat_id=chat_id,
            user_id=to_user_id,
            amount=amount,
            event_type="transfer_in",
            operator=operator,
            reason=reason or "points_transfer",
            counterparty_user_id=from_user_id,
        )
        return {"from": debit, "to": credit}

    def get_checkin_state(self, chat_id: int, user_id: int) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT chat_id, user_id, streak_days, last_checkin_date, created_at, updated_at
                FROM chat_points_checkins
                WHERE chat_id = ? AND user_id = ?
                """,
                (chat_id, user_id),
            ).fetchone()
        if row:
            return dict(row)
        now = to_iso(utc_now())
        return {
            "chat_id": chat_id,
            "user_id": user_id,
            "streak_days": 0,
            "last_checkin_date": None,
            "created_at": now,
            "updated_at": now,
        }

    def save_checkin_state(self, chat_id: int, user_id: int, streak_days: int, last_checkin_date: str) -> dict[str, Any]:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_points_checkins(chat_id, user_id, streak_days, last_checkin_date, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                  streak_days=excluded.streak_days,
                  last_checkin_date=excluded.last_checkin_date,
                  updated_at=excluded.updated_at
                """,
                (chat_id, user_id, streak_days, last_checkin_date, now, now),
            )
        return self.get_checkin_state(chat_id, user_id)

    def upsert_points_task(
        self,
        *,
        chat_id: int,
        task_key: str,
        title: str,
        description: str,
        task_type: str,
        target_value: int,
        reward_points: int,
        period: str = "daily",
        enabled: bool = True,
    ) -> None:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_points_tasks(chat_id, task_key, title, description, task_type, target_value, reward_points, period, enabled, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, task_key) DO UPDATE SET
                  title=excluded.title,
                  description=excluded.description,
                  task_type=excluded.task_type,
                  target_value=excluded.target_value,
                  reward_points=excluded.reward_points,
                  period=excluded.period,
                  enabled=excluded.enabled,
                  updated_at=excluded.updated_at
                """,
                (chat_id, task_key, title, description, task_type, target_value, reward_points, period, 1 if enabled else 0, now, now),
            )

    def list_points_tasks(self, chat_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, chat_id, task_key, title, description, task_type, target_value, reward_points, period, enabled, created_at, updated_at
                FROM chat_points_tasks
                WHERE chat_id = ?
                ORDER BY id ASC
                """,
                (chat_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_points_task(self, chat_id: int, task_key: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, chat_id, task_key, title, description, task_type, target_value, reward_points, period, enabled, created_at, updated_at
                FROM chat_points_tasks
                WHERE chat_id = ? AND task_key = ?
                """,
                (chat_id, task_key),
            ).fetchone()
        return dict(row) if row else None

    def get_task_progress(self, chat_id: int, user_id: int, task_id: int, period_key: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT chat_id, user_id, task_id, period_key, progress_value, completed, reward_claimed, updated_at
                FROM chat_points_task_progress
                WHERE chat_id = ? AND user_id = ? AND task_id = ? AND period_key = ?
                """,
                (chat_id, user_id, task_id, period_key),
            ).fetchone()
        if row:
            return dict(row)
        return {
            "chat_id": chat_id,
            "user_id": user_id,
            "task_id": task_id,
            "period_key": period_key,
            "progress_value": 0,
            "completed": 0,
            "reward_claimed": 0,
            "updated_at": to_iso(utc_now()),
        }

    def save_task_progress(
        self,
        *,
        chat_id: int,
        user_id: int,
        task_id: int,
        period_key: str,
        progress_value: int,
        completed: bool,
        reward_claimed: bool,
    ) -> dict[str, Any]:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_points_task_progress(chat_id, user_id, task_id, period_key, progress_value, completed, reward_claimed, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id, task_id, period_key) DO UPDATE SET
                  progress_value=excluded.progress_value,
                  completed=excluded.completed,
                  reward_claimed=excluded.reward_claimed,
                  updated_at=excluded.updated_at
                """,
                (chat_id, user_id, task_id, period_key, progress_value, 1 if completed else 0, 1 if reward_claimed else 0, now),
            )
        return self.get_task_progress(chat_id, user_id, task_id, period_key)

    def list_points_task_progress(self, chat_id: int, period_key: str, user_id: int | None = None) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            if user_id is None:
                rows = conn.execute(
                    """
                    SELECT chat_id, user_id, task_id, period_key, progress_value, completed, reward_claimed, updated_at
                    FROM chat_points_task_progress
                    WHERE chat_id = ? AND period_key = ?
                    ORDER BY updated_at DESC
                    """,
                    (chat_id, period_key),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT chat_id, user_id, task_id, period_key, progress_value, completed, reward_claimed, updated_at
                    FROM chat_points_task_progress
                    WHERE chat_id = ? AND user_id = ? AND period_key = ?
                    ORDER BY updated_at DESC
                    """,
                    (chat_id, user_id, period_key),
                ).fetchall()
        return [dict(r) for r in rows]

    def upsert_shop_item(
        self,
        *,
        chat_id: int,
        item_key: str,
        title: str,
        description: str,
        item_type: str,
        price_points: int,
        stock: int | None,
        enabled: bool,
        meta_json: str | None,
    ) -> None:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_points_shop_items(chat_id, item_key, title, description, item_type, price_points, stock, enabled, meta_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, item_key) DO UPDATE SET
                  title=excluded.title,
                  description=excluded.description,
                  item_type=excluded.item_type,
                  price_points=excluded.price_points,
                  stock=excluded.stock,
                  enabled=excluded.enabled,
                  meta_json=excluded.meta_json,
                  updated_at=excluded.updated_at
                """,
                (chat_id, item_key, title, description, item_type, price_points, stock, 1 if enabled else 0, meta_json, now, now),
            )

    def list_shop_items(self, chat_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, chat_id, item_key, title, description, item_type, price_points, stock, enabled, meta_json, created_at, updated_at
                FROM chat_points_shop_items
                WHERE chat_id = ?
                ORDER BY id ASC
                """,
                (chat_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_shop_item(self, chat_id: int, item_key: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, chat_id, item_key, title, description, item_type, price_points, stock, enabled, meta_json, created_at, updated_at
                FROM chat_points_shop_items
                WHERE chat_id = ? AND item_key = ?
                """,
                (chat_id, item_key),
            ).fetchone()
        return dict(row) if row else None

    def save_redemption(
        self,
        *,
        chat_id: int,
        user_id: int,
        item_id: int,
        price_points: int,
        status: str,
        reward_payload: str | None,
        expires_at: str | None,
    ) -> dict[str, Any]:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO chat_points_redemptions(chat_id, user_id, item_id, price_points, status, reward_payload, expires_at, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (chat_id, user_id, item_id, price_points, status, reward_payload, expires_at, now),
            )
            row = conn.execute(
                """
                SELECT id, chat_id, user_id, item_id, price_points, status, reward_payload, expires_at, created_at
                FROM chat_points_redemptions
                WHERE id = ?
                """,
                (int(cur.lastrowid),),
            ).fetchone()
        return dict(row)

    def list_redemptions(self, chat_id: int, user_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            if user_id is None:
                rows = conn.execute(
                    """
                    SELECT id, chat_id, user_id, item_id, price_points, status, reward_payload, expires_at, created_at
                    FROM chat_points_redemptions
                    WHERE chat_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (chat_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, chat_id, user_id, item_id, price_points, status, reward_payload, expires_at, created_at
                    FROM chat_points_redemptions
                    WHERE chat_id = ? AND user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (chat_id, user_id, limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def update_redemption_status(self, redemption_id: int, status: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE chat_points_redemptions SET status = ? WHERE id = ?",
                (status, redemption_id),
            )
            row = conn.execute(
                """
                SELECT id, chat_id, user_id, item_id, price_points, status, reward_payload, expires_at, created_at
                FROM chat_points_redemptions
                WHERE id = ?
                """,
                (redemption_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_lottery(
        self,
        *,
        chat_id: int,
        title: str,
        description: str,
        entry_mode: str,
        points_cost: int,
        points_threshold: int,
        allow_multiple_entries: bool,
        max_entries_per_user: int,
        show_participants: bool,
        starts_at: str,
        entry_deadline_at: str,
        draw_at: str,
        created_by: int | None,
    ) -> dict[str, Any]:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO chat_lotteries(
                  chat_id, title, description, status, entry_mode, points_cost, points_threshold,
                  allow_multiple_entries, max_entries_per_user, show_participants,
                  starts_at, entry_deadline_at, draw_at, created_by, created_at, updated_at
                )
                VALUES(?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    title,
                    description,
                    entry_mode,
                    points_cost,
                    points_threshold,
                    1 if allow_multiple_entries else 0,
                    max_entries_per_user,
                    1 if show_participants else 0,
                    starts_at,
                    entry_deadline_at,
                    draw_at,
                    created_by,
                    now,
                    now,
                ),
            )
        return self.get_lottery(int(cur.lastrowid)) or {}

    def update_lottery(self, lottery_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        current = self.get_lottery(lottery_id)
        if current is None:
            return None
        merged = {**current, **payload, "updated_at": to_iso(utc_now())}
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE chat_lotteries
                SET title = ?, description = ?, status = ?, entry_mode = ?, points_cost = ?, points_threshold = ?,
                    allow_multiple_entries = ?, max_entries_per_user = ?, show_participants = ?,
                    starts_at = ?, entry_deadline_at = ?, draw_at = ?, announcement_message_id = ?, summary_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    merged["title"],
                    merged.get("description"),
                    merged["status"],
                    merged["entry_mode"],
                    int(merged["points_cost"]),
                    int(merged["points_threshold"]),
                    1 if bool(merged["allow_multiple_entries"]) else 0,
                    int(merged["max_entries_per_user"]),
                    1 if bool(merged["show_participants"]) else 0,
                    merged["starts_at"],
                    merged["entry_deadline_at"],
                    merged["draw_at"],
                    merged.get("announcement_message_id"),
                    merged.get("summary_json"),
                    merged["updated_at"],
                    lottery_id,
                ),
            )
        return self.get_lottery(lottery_id)

    def get_lottery(self, lottery_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, chat_id, title, description, status, entry_mode, points_cost, points_threshold,
                       allow_multiple_entries, max_entries_per_user, show_participants,
                       starts_at, entry_deadline_at, draw_at, announcement_message_id, created_by,
                       summary_json, canceled_at, drawn_at, created_at, updated_at
                FROM chat_lotteries
                WHERE id = ?
                """,
                (lottery_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_lotteries(self, chat_id: int, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, chat_id, title, description, status, entry_mode, points_cost, points_threshold,
                       allow_multiple_entries, max_entries_per_user, show_participants,
                       starts_at, entry_deadline_at, draw_at, announcement_message_id, created_by,
                       summary_json, canceled_at, drawn_at, created_at, updated_at
                FROM chat_lotteries
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def replace_lottery_prizes(self, lottery_id: int, prizes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            conn.execute("DELETE FROM chat_lottery_prizes WHERE lottery_id = ?", (lottery_id,))
            for idx, prize in enumerate(prizes):
                conn.execute(
                    """
                    INSERT INTO chat_lottery_prizes(lottery_id, title, winner_count, sort_order, created_at)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (
                        lottery_id,
                        str(prize.get("title", "")).strip(),
                        max(int(prize.get("winner_count", 1)), 0),
                        int(prize.get("sort_order", idx)),
                        now,
                    ),
                )
        return self.list_lottery_prizes(lottery_id)

    def list_lottery_prizes(self, lottery_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, lottery_id, title, winner_count, sort_order, created_at
                FROM chat_lottery_prizes
                WHERE lottery_id = ?
                ORDER BY sort_order ASC, id ASC
                """,
                (lottery_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def create_lottery_entry(
        self,
        *,
        lottery_id: int,
        chat_id: int,
        user_id: int,
        entry_count: int,
        points_spent: int,
        source: str,
        ledger_id: int | None,
    ) -> dict[str, Any]:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO chat_lottery_entries(
                  lottery_id, chat_id, user_id, entry_count, points_spent, source, status, ledger_id, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, 'joined', ?, ?, ?)
                """,
                (lottery_id, chat_id, user_id, entry_count, points_spent, source, ledger_id, now, now),
            )
        return self.get_lottery_entry(int(cur.lastrowid)) or {}

    def get_lottery_entry(self, entry_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, lottery_id, chat_id, user_id, entry_count, points_spent, source, status, ledger_id, refund_ledger_id, created_at, updated_at
                FROM chat_lottery_entries
                WHERE id = ?
                """,
                (entry_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_lottery_entries(self, lottery_id: int, user_id: int | None = None) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            if user_id is None:
                rows = conn.execute(
                    """
                    SELECT e.id, e.lottery_id, e.chat_id, e.user_id, e.entry_count, e.points_spent, e.source, e.status,
                           e.ledger_id, e.refund_ledger_id, e.created_at, e.updated_at,
                           u.username, u.first_name, u.last_name
                    FROM chat_lottery_entries e
                    LEFT JOIN users u ON u.user_id = e.user_id
                    WHERE e.lottery_id = ?
                    ORDER BY e.id DESC
                    """,
                    (lottery_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT e.id, e.lottery_id, e.chat_id, e.user_id, e.entry_count, e.points_spent, e.source, e.status,
                           e.ledger_id, e.refund_ledger_id, e.created_at, e.updated_at,
                           u.username, u.first_name, u.last_name
                    FROM chat_lottery_entries e
                    LEFT JOIN users u ON u.user_id = e.user_id
                    WHERE e.lottery_id = ? AND e.user_id = ?
                    ORDER BY e.id DESC
                    """,
                    (lottery_id, user_id),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_lottery_user_entry_stats(self, lottery_id: int, user_id: int) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT
                  COALESCE(SUM(entry_count), 0) AS total_entry_count,
                  COUNT(*) AS join_times,
                  COALESCE(SUM(points_spent), 0) AS total_points_spent
                FROM chat_lottery_entries
                WHERE lottery_id = ? AND user_id = ? AND status = 'joined'
                """,
                (lottery_id, user_id),
            ).fetchone()
        return dict(row) if row else {"total_entry_count": 0, "join_times": 0, "total_points_spent": 0}

    def get_lottery_stats(self, lottery_id: int) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT
                  COUNT(*) AS join_records,
                  COUNT(DISTINCT user_id) AS unique_users,
                  COALESCE(SUM(entry_count), 0) AS total_entry_count,
                  COALESCE(SUM(points_spent), 0) AS total_points_spent
                FROM chat_lottery_entries
                WHERE lottery_id = ? AND status = 'joined'
                """,
                (lottery_id,),
            ).fetchone()
        stats = dict(row) if row else {"join_records": 0, "unique_users": 0, "total_entry_count": 0, "total_points_spent": 0}
        stats["winner_count"] = len(self.list_lottery_winners(lottery_id))
        return stats

    def mark_lottery_entry_refunded(self, entry_id: int, refund_ledger_id: int) -> dict[str, Any] | None:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE chat_lottery_entries
                SET status = 'refunded', refund_ledger_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (refund_ledger_id, now, entry_id),
            )
        return self.get_lottery_entry(entry_id)

    def save_lottery_winner(
        self,
        *,
        lottery_id: int,
        prize_id: int,
        chat_id: int,
        user_id: int,
        prize_title: str,
        sort_order: int,
        entry_count: int,
        snapshot_json: str | None,
    ) -> dict[str, Any]:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO chat_lottery_winners(
                  lottery_id, prize_id, chat_id, user_id, prize_title, sort_order, entry_count, snapshot_json, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (lottery_id, prize_id, chat_id, user_id, prize_title, sort_order, entry_count, snapshot_json, now),
            )
        return self.get_lottery_winner(int(cur.lastrowid)) or {}

    def get_lottery_winner(self, winner_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT w.id, w.lottery_id, w.prize_id, w.chat_id, w.user_id, w.prize_title, w.sort_order, w.entry_count, w.snapshot_json, w.created_at,
                       u.username, u.first_name, u.last_name
                FROM chat_lottery_winners w
                LEFT JOIN users u ON u.user_id = w.user_id
                WHERE w.id = ?
                """,
                (winner_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_lottery_winners(self, lottery_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT w.id, w.lottery_id, w.prize_id, w.chat_id, w.user_id, w.prize_title, w.sort_order, w.entry_count, w.snapshot_json, w.created_at,
                       u.username, u.first_name, u.last_name
                FROM chat_lottery_winners w
                LEFT JOIN users u ON u.user_id = w.user_id
                WHERE w.lottery_id = ?
                ORDER BY w.sort_order ASC, w.id ASC
                """,
                (lottery_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_lottery_status(
        self,
        lottery_id: int,
        *,
        status: str,
        operator: str,
        summary_json: str | None = None,
        announcement_message_id: int | None = None,
    ) -> dict[str, Any] | None:
        lottery = self.get_lottery(lottery_id)
        if lottery is None:
            return None
        now = to_iso(utc_now())
        canceled_at = now if status == "canceled" else lottery.get("canceled_at")
        drawn_at = now if status == "drawn" else lottery.get("drawn_at")
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE chat_lotteries
                SET status = ?, summary_json = ?, announcement_message_id = ?, canceled_at = ?, drawn_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    summary_json if summary_json is not None else lottery.get("summary_json"),
                    announcement_message_id if announcement_message_id is not None else lottery.get("announcement_message_id"),
                    canceled_at,
                    drawn_at,
                    now,
                    lottery_id,
                ),
            )
        return self.get_lottery(lottery_id)

    def list_due_lotteries(self, draw_at_iso: str) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, chat_id, title, description, status, entry_mode, points_cost, points_threshold,
                       allow_multiple_entries, max_entries_per_user, show_participants,
                       starts_at, entry_deadline_at, draw_at, announcement_message_id, created_by,
                       summary_json, canceled_at, drawn_at, created_at, updated_at
                FROM chat_lotteries
                WHERE status = 'active' AND draw_at <= ?
                ORDER BY draw_at ASC, id ASC
                """,
                (draw_at_iso,),
            ).fetchall()
        return [dict(r) for r in rows]

    def set_lottery_announcement_message(self, lottery_id: int, message_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE chat_lotteries SET announcement_message_id = ?, updated_at = ? WHERE id = ?",
                (message_id, to_iso(utc_now()), lottery_id),
            )
        return self.get_lottery(lottery_id)

    def get_active_welcome_bonus(self, chat_id: int, user_id: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT r.id, r.reward_payload, r.expires_at, s.item_key, s.item_type
                FROM chat_points_redemptions r
                JOIN chat_points_shop_items s ON s.id = r.item_id
                WHERE r.chat_id = ?
                  AND r.user_id = ?
                  AND r.status = 'active'
                  AND s.item_type = 'welcome_bonus'
                  AND (r.expires_at IS NULL OR r.expires_at > ?)
                ORDER BY r.id DESC
                LIMIT 1
                """,
                (chat_id, user_id, to_iso(utc_now())),
            ).fetchone()
        return dict(row) if row else None

    def list_chats(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT chat_id, title, type, created_at, updated_at
                FROM chats
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_chat_members(self, chat_id: int, limit: int = 200, query: str | None = None) -> list[dict[str, Any]]:
        q = (query or "").strip()
        where_sql = ""
        params: list[Any] = [chat_id, chat_id, chat_id, chat_id]
        if q:
            where_sql = """
            WHERE
              CAST(ids.user_id AS TEXT) LIKE ? OR
              COALESCE(u.username, '') LIKE ? OR
              COALESCE(u.first_name, '') LIKE ? OR
              COALESCE(u.last_name, '') LIKE ?
            """
            like = f"%{q}%"
            params.extend([like, like, like, like])
        params.append(limit)
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""
                WITH ids AS (
                  SELECT DISTINCT user_id FROM messages WHERE chat_id = ?
                  UNION
                  SELECT DISTINCT user_id FROM enforcements WHERE chat_id = ? AND user_id IS NOT NULL
                ),
                latest_msg AS (
                  SELECT user_id, MAX(date) AS last_message_at
                  FROM messages
                  WHERE chat_id = ?
                  GROUP BY user_id
                )
                SELECT
                  ids.user_id AS user_id,
                  u.username AS username,
                  u.first_name AS first_name,
                  u.last_name AS last_name,
                  lm.last_message_at AS last_message_at,
                  COALESCE(us.score, 0) AS strike_score
                FROM ids
                LEFT JOIN users u ON u.user_id = ids.user_id
                LEFT JOIN latest_msg lm ON lm.user_id = ids.user_id
                LEFT JOIN user_strikes us ON us.chat_id = ? AND us.user_id = ids.user_id
                {where_sql}
                ORDER BY
                  CASE WHEN lm.last_message_at IS NULL THEN 1 ELSE 0 END,
                  lm.last_message_at DESC,
                  ids.user_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def save_admin_action(
        self,
        chat_id: int,
        action: str,
        reason: str,
        target: dict[str, Any] | None = None,
        user_id: int | None = None,
        message_id: int | None = None,
        duration_seconds: int | None = None,
    ) -> int:
        payload = {"reason": reason, "target": target or {}}
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO enforcements(chat_id, user_id, message_id, action, duration_seconds, reason, operator, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    user_id,
                    message_id,
                    action,
                    duration_seconds,
                    json.dumps(payload, ensure_ascii=False),
                    "admin_api",
                    to_iso(utc_now()),
                ),
            )
            return int(cur.lastrowid)

    @staticmethod
    def _serialize_verification_question_row(row: Any) -> dict[str, Any]:
        data = dict(row)
        raw_options = data.get("options")
        if isinstance(raw_options, str):
            try:
                options = json.loads(raw_options)
            except json.JSONDecodeError:
                options = []
        else:
            options = raw_options or []
        cleaned_options = [str(item).strip() for item in options if str(item).strip()]
        answer_index = int(data.get("answer_index", 0))
        data["options"] = cleaned_options
        data["answer_text"] = cleaned_options[answer_index] if 0 <= answer_index < len(cleaned_options) else None
        data["scope"] = "global" if data.get("chat_id") is None else "chat"
        return data

    def list_verification_questions(self, chat_id: int, include_global: bool = True) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            if include_global:
                rows = conn.execute(
                    """
                    SELECT id, chat_id, question, options, answer_index, created_at
                    FROM join_verification_questions
                    WHERE chat_id = ? OR chat_id IS NULL
                    ORDER BY CASE WHEN chat_id = ? THEN 0 ELSE 1 END, id DESC
                    """,
                    (chat_id, chat_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, chat_id, question, options, answer_index, created_at
                    FROM join_verification_questions
                    WHERE chat_id = ?
                    ORDER BY id DESC
                    """,
                    (chat_id,),
                ).fetchall()
        return [self._serialize_verification_question_row(row) for row in rows]

    def create_verification_question(
        self,
        *,
        chat_id: int | None,
        question: str,
        options: list[str],
        answer_index: int,
    ) -> dict[str, Any]:
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO join_verification_questions(chat_id, question, options, answer_index, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    question,
                    json.dumps(options, ensure_ascii=False),
                    answer_index,
                    to_iso(utc_now()),
                ),
            )
            row = conn.execute(
                """
                SELECT id, chat_id, question, options, answer_index, created_at
                FROM join_verification_questions
                WHERE id = ?
                """,
                (int(cur.lastrowid),),
            ).fetchone()
        if row is None:
            raise RuntimeError("verification_question_create_failed")
        return self._serialize_verification_question_row(row)

    def _get_accessible_verification_question_row(self, chat_id: int, question_id: int):
        with self.db.connect() as conn:
            return conn.execute(
                """
                SELECT id, chat_id, question, options, answer_index, created_at
                FROM join_verification_questions
                WHERE id = ? AND (chat_id = ? OR chat_id IS NULL)
                """,
                (question_id, chat_id),
            ).fetchone()

    def update_verification_question(
        self,
        *,
        access_chat_id: int,
        question_id: int,
        target_chat_id: int | None,
        question: str,
        options: list[str],
        answer_index: int,
    ) -> dict[str, Any] | None:
        if self._get_accessible_verification_question_row(access_chat_id, question_id) is None:
            return None
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE join_verification_questions
                SET chat_id = ?, question = ?, options = ?, answer_index = ?
                WHERE id = ?
                """,
                (
                    target_chat_id,
                    question,
                    json.dumps(options, ensure_ascii=False),
                    answer_index,
                    question_id,
                ),
            )
            row = conn.execute(
                """
                SELECT id, chat_id, question, options, answer_index, created_at
                FROM join_verification_questions
                WHERE id = ?
                """,
                (question_id,),
            ).fetchone()
        return self._serialize_verification_question_row(row) if row else None

    def delete_verification_question(self, access_chat_id: int, question_id: int) -> int:
        if self._get_accessible_verification_question_row(access_chat_id, question_id) is None:
            return 0
        with self.db.connect() as conn:
            cur = conn.execute(
                "DELETE FROM join_verification_questions WHERE id = ?",
                (question_id,),
            )
        return cur.rowcount

    def get_verification_question(self, chat_id: int) -> dict | None:
        """随机取一道验证题：优先群专属题，无则取全局题（chat_id IS NULL）"""
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, question, options, answer_index FROM join_verification_questions
                WHERE chat_id = ?
                ORDER BY RANDOM() LIMIT 1
                """,
                (chat_id,),
            ).fetchone()
            if row:
                return self._serialize_verification_question_row(row)
            row = conn.execute(
                """
                SELECT id, question, options, answer_index FROM join_verification_questions
                WHERE chat_id IS NULL
                ORDER BY RANDOM() LIMIT 1
                """,
            ).fetchone()
            return self._serialize_verification_question_row(row) if row else None

    def save_verification_log(
        self,
        chat_id: int,
        user_id: int,
        username: str | None,
        result: str,
        attempts: int,
        whitelist_bypass: bool,
    ) -> int:
        """写入入群验证审计日志"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO join_verification_log
                  (chat_id, user_id, username, result, attempts, whitelist_bypass, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    user_id,
                    username,
                    result,
                    attempts,
                    1 if whitelist_bypass else 0,
                    to_iso(utc_now()),
                ),
            )
            return int(cur.lastrowid)

    def list_verification_logs(self, chat_id: int, limit: int = 100) -> list[dict]:
        """查询验证审计日志"""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, chat_id, user_id, username, result, attempts, whitelist_bypass, created_at
                FROM join_verification_log
                WHERE chat_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_welcome_templates(self, chat_id: int, hour: int | None = None, chat_type: str | None = None) -> list[dict]:
        """取有效欢迎语模板，按 time_start/time_end 和 chat_type 过滤，随机权重排序"""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, template, time_start, time_end, chat_type, weight
                FROM welcome_templates
                WHERE (chat_id = ? OR chat_id IS NULL)
                  AND enabled = 1
                ORDER BY RANDOM() * weight DESC
                """,
                (chat_id,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if hour is not None and d["time_start"] is not None and d["time_end"] is not None:
                t_start = int(d["time_start"])
                t_end = int(d["time_end"])
                if t_start <= t_end:
                    if not (t_start <= hour < t_end):
                        continue
                else:  # 跨午夜
                    if not (hour >= t_start or hour < t_end):
                        continue
            if chat_type and d["chat_type"] and d["chat_type"] != chat_type:
                continue
            result.append(d)
        return result

    def add_welcome_template(
        self,
        chat_id: int | None,
        template: str,
        time_start: int | None = None,
        time_end: int | None = None,
        chat_type: str | None = None,
        weight: int = 1,
    ) -> int:
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO welcome_templates(chat_id, template, time_start, time_end, chat_type, weight, enabled, created_at)
                VALUES(?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (chat_id, template, time_start, time_end, chat_type, weight, to_iso(utc_now())),
            )
            return int(cur.lastrowid)

    def delete_welcome_template(self, template_id: int) -> bool:
        with self.db.connect() as conn:
            cur = conn.execute("DELETE FROM welcome_templates WHERE id = ?", (template_id,))
            return cur.rowcount > 0

    def save_raid_event(self, chat_id: int, trigger_type: str, join_count: int, details: str | None = None) -> int:
        """记录 Raid 事件"""
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO raid_events(chat_id, trigger_type, join_count, details, created_at) VALUES(?,?,?,?,?)",
                (chat_id, trigger_type, join_count, details, to_iso(utc_now())),
            )
            return int(cur.lastrowid)

    def list_raid_events(self, chat_id: int, limit: int = 50) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM raid_events WHERE chat_id=? ORDER BY id DESC LIMIT ?",
                (chat_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
