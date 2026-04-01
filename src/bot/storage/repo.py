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
        )

    def update_settings(self, chat_id: int, payload: dict[str, Any]) -> None:
        current = self.get_settings(chat_id)
        new = asdict(current) | payload
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_settings(chat_id, mode, ai_enabled, ai_threshold, allow_admin_self_test, action_policy, rate_limit_policy, language, level3_mute_seconds, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                  mode=excluded.mode,
                  ai_enabled=excluded.ai_enabled,
                  ai_threshold=excluded.ai_threshold,
                  allow_admin_self_test=excluded.allow_admin_self_test,
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
                    1 if new["allow_admin_self_test"] else 0,
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
