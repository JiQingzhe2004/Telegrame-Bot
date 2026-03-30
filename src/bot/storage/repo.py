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

    def upsert_chat_user(self, chat: ChatRef, user: UserRef) -> None:
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
                INSERT INTO users(user_id, username, first_name, last_name, is_bot, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name, last_name=excluded.last_name, is_bot=excluded.is_bot, updated_at=excluded.updated_at
                """,
                (user.user_id, user.username, user.first_name, user.last_name, 1 if user.is_bot else 0, now),
            )
            conn.execute(
                """
                INSERT INTO chat_settings(chat_id, mode, ai_enabled, ai_threshold, action_policy, rate_limit_policy, language, level3_mute_seconds, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO NOTHING
                """,
                (
                    chat.chat_id,
                    self.defaults["mode"],
                    1 if self.defaults["ai_enabled"] else 0,
                    self.defaults["ai_threshold"],
                    self.defaults["action_policy"],
                    self.defaults["rate_limit_policy"],
                    self.defaults["language"],
                    self.defaults["level3_mute_seconds"],
                    now,
                ),
            )

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
            action_policy=row["action_policy"],
            rate_limit_policy=row["rate_limit_policy"],
            language=row["language"],
            level3_mute_seconds=int(row["level3_mute_seconds"]),
        )

    def update_settings(self, chat_id: int, payload: dict[str, Any]) -> None:
        current = self.get_settings(chat_id)
        new = asdict(current) | payload
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_settings(chat_id, mode, ai_enabled, ai_threshold, action_policy, rate_limit_policy, language, level3_mute_seconds, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                  mode=excluded.mode,
                  ai_enabled=excluded.ai_enabled,
                  ai_threshold=excluded.ai_threshold,
                  action_policy=excluded.action_policy,
                  rate_limit_policy=excluded.rate_limit_policy,
                  language=excluded.language,
                  level3_mute_seconds=excluded.level3_mute_seconds,
                  updated_at=excluded.updated_at
                """,
                (
                    chat_id,
                    new["mode"],
                    1 if new["ai_enabled"] else 0,
                    float(new["ai_threshold"]),
                    new["action_policy"],
                    new["rate_limit_policy"],
                    new["language"],
                    int(new["level3_mute_seconds"]),
                    to_iso(utc_now()),
                ),
            )

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
                INSERT INTO moderation_decisions(chat_id, message_id, user_id, rule_hit, ai_used, ai_model, ai_input_ref, ai_output, final_level, confidence, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.chat_id,
                    message.message_id,
                    message.user_id,
                    ",".join(decision.reason_codes),
                    1 if decision.ai_used else 0,
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
                SELECT id, chat_id, message_id, user_id, rule_hit, ai_used, ai_model, final_level, confidence, created_at
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
            latest = conn.execute(
                "SELECT created_at FROM moderation_decisions ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return {
            "decisions_total": int(decisions),
            "enforcements_total": int(enforcements),
            "ai_used_total": int(ai_used),
            "latest_decision_at": latest["created_at"] if latest else None,
        }

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
