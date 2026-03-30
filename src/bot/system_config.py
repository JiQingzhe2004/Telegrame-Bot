from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

from bot.storage.db import Database
from bot.utils.time import to_iso, utc_now


@dataclass(frozen=True)
class RuntimeConfig:
    bot_token: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""
    run_mode: str = "polling"
    webhook_public_url: str = ""
    webhook_path: str = "/telegram/webhook"
    admin_api_token: str = ""
    admin_api_token_hash: str = ""
    default_mode: str = "balanced"
    default_ai_enabled: bool = True
    default_ai_threshold: float = 0.75
    default_action_policy: str = "progressive"
    default_rate_limit_policy: str = "default"
    default_language: str = "zh"
    default_level3_mute_seconds: int = 604800
    ai_low_risk_model: str = "gpt-4.1-mini"
    ai_high_risk_model: str = "gpt-5.2"
    ai_timeout_seconds: int = 12
    join_verification_enabled: bool = True
    join_verification_timeout_seconds: int = 180
    join_welcome_enabled: bool = True
    join_welcome_use_ai: bool = True
    join_welcome_template: str = "欢迎 {user} 加入 {chat}，请先阅读群规并友善交流。"

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "RuntimeConfig":
        defaults = RuntimeConfig()
        merged = asdict(defaults) | data
        return RuntimeConfig(
            bot_token=str(merged["bot_token"]).strip(),
            openai_api_key=str(merged["openai_api_key"]).strip(),
            openai_base_url=str(merged["openai_base_url"]).strip(),
            run_mode=str(merged["run_mode"]).strip().lower(),
            webhook_public_url=str(merged["webhook_public_url"]).strip(),
            webhook_path=str(merged["webhook_path"]).strip() or "/telegram/webhook",
            admin_api_token=str(merged["admin_api_token"]).strip(),
            admin_api_token_hash=str(merged.get("admin_api_token_hash", "")).strip(),
            default_mode=str(merged["default_mode"]).strip(),
            default_ai_enabled=bool(merged["default_ai_enabled"]),
            default_ai_threshold=float(merged["default_ai_threshold"]),
            default_action_policy=str(merged["default_action_policy"]).strip(),
            default_rate_limit_policy=str(merged["default_rate_limit_policy"]).strip(),
            default_language=str(merged["default_language"]).strip(),
            default_level3_mute_seconds=int(merged["default_level3_mute_seconds"]),
            ai_low_risk_model=str(merged["ai_low_risk_model"]).strip(),
            ai_high_risk_model=str(merged["ai_high_risk_model"]).strip(),
            ai_timeout_seconds=int(merged["ai_timeout_seconds"]),
            join_verification_enabled=bool(merged["join_verification_enabled"]),
            join_verification_timeout_seconds=int(merged["join_verification_timeout_seconds"]),
            join_welcome_enabled=bool(merged["join_welcome_enabled"]),
            join_welcome_use_ai=bool(merged["join_welcome_use_ai"]),
            join_welcome_template=str(merged["join_welcome_template"]).strip()
            or "欢迎 {user} 加入 {chat}，请先阅读群规并友善交流。",
        )

    def redacted(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("bot_token", "openai_api_key", "admin_api_token", "admin_api_token_hash"):
            raw = data[key]
            if not raw:
                data[key] = ""
            else:
                data[key] = f"{raw[:4]}***{raw[-3:]}" if len(raw) > 8 else "***"
        data["has_admin_api_token"] = bool(self.admin_api_token_hash or self.admin_api_token)
        return data


class ConfigService:
    CONFIG_KEY = "runtime_config"

    def __init__(self, db: Database) -> None:
        self.db = db

    def get_runtime_config(self) -> RuntimeConfig:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT value FROM system_config WHERE key = ?",
                (self.CONFIG_KEY,),
            ).fetchone()
        if not row:
            return RuntimeConfig()
        try:
            raw = json.loads(row["value"])
        except json.JSONDecodeError:
            raw = {}
        return RuntimeConfig.from_dict(raw)

    def save_runtime_config(self, payload: dict[str, Any]) -> RuntimeConfig:
        current = asdict(self.get_runtime_config())
        merged = current | payload
        raw_admin = str(payload.get("admin_api_token", "")).strip() if "admin_api_token" in payload else ""
        if raw_admin:
            merged["admin_api_token_hash"] = self._hash(raw_admin)
            merged["admin_api_token"] = ""
        conf = RuntimeConfig.from_dict(merged)
        errors = self.validate_config(conf)
        if errors:
            raise ValueError("; ".join(errors))
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO system_config(key, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (self.CONFIG_KEY, json.dumps(asdict(conf), ensure_ascii=False), to_iso(utc_now())),
            )
        return conf

    def validate_config(self, conf: RuntimeConfig) -> list[str]:
        errors: list[str] = []
        if conf.run_mode not in {"polling", "webhook"}:
            errors.append("run_mode must be polling or webhook")
        if not 0 <= conf.default_ai_threshold <= 1:
            errors.append("default_ai_threshold out of range")
        if conf.default_level3_mute_seconds <= 0:
            errors.append("default_level3_mute_seconds must be positive")
        if conf.ai_timeout_seconds <= 0:
            errors.append("ai_timeout_seconds must be positive")
        if conf.join_verification_timeout_seconds <= 0:
            errors.append("join_verification_timeout_seconds must be positive")
        if len(conf.join_welcome_template) > 300:
            errors.append("join_welcome_template is too long")
        if conf.run_mode == "webhook" and not conf.webhook_public_url:
            errors.append("webhook_public_url is required in webhook mode")
        return errors

    def is_complete(self, conf: RuntimeConfig | None = None) -> bool:
        c = conf or self.get_runtime_config()
        return bool(c.bot_token and (c.admin_api_token_hash or c.admin_api_token))

    def validate_activation(self, conf: RuntimeConfig | None = None) -> list[str]:
        c = conf or self.get_runtime_config()
        errors = self.validate_config(c)
        if not c.bot_token:
            errors.append("bot_token is required")
        if not (c.admin_api_token_hash or c.admin_api_token):
            errors.append("admin_api_token is required")
        return errors

    def verify_admin_token(self, raw_token: str) -> bool:
        token = raw_token.strip()
        if not token:
            return False
        conf = self.get_runtime_config()
        if conf.admin_api_token_hash:
            return self._hash(token) == conf.admin_api_token_hash
        # 兼容早期明文配置
        return token == conf.admin_api_token

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue_bootstrap_code(self, ttl_minutes: int = 20) -> str:
        code = secrets.token_urlsafe(9)
        expires = to_iso(utc_now() + timedelta(minutes=ttl_minutes))
        with self.db.connect() as conn:
            conn.execute("UPDATE setup_sessions SET consumed_at = ? WHERE kind = ? AND consumed_at IS NULL", (to_iso(utc_now()), "bootstrap_code"))
            conn.execute(
                "INSERT INTO setup_sessions(kind, token_hash, expires_at, consumed_at, created_at) VALUES(?, ?, ?, NULL, ?)",
                ("bootstrap_code", self._hash(code), expires, to_iso(utc_now())),
            )
        return code

    def verify_bootstrap_code(self, code: str) -> bool:
        now = to_iso(utc_now())
        token_hash = self._hash(code)
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM setup_sessions
                WHERE kind = ? AND token_hash = ? AND consumed_at IS NULL AND expires_at > ?
                ORDER BY id DESC LIMIT 1
                """,
                ("bootstrap_code", token_hash, now),
            ).fetchone()
            if not row:
                return False
            conn.execute("UPDATE setup_sessions SET consumed_at = ? WHERE id = ?", (now, int(row["id"])))
            return True

    def issue_setup_token(self, ttl_minutes: int = 30) -> str:
        token = secrets.token_urlsafe(32)
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO setup_sessions(kind, token_hash, expires_at, consumed_at, created_at) VALUES(?, ?, ?, NULL, ?)",
                (
                    "setup_token",
                    self._hash(token),
                    to_iso(utc_now() + timedelta(minutes=ttl_minutes)),
                    to_iso(utc_now()),
                ),
            )
        return token

    def verify_setup_token(self, token: str, consume: bool = False) -> bool:
        now = to_iso(utc_now())
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM setup_sessions
                WHERE kind = ? AND token_hash = ? AND consumed_at IS NULL AND expires_at > ?
                ORDER BY id DESC LIMIT 1
                """,
                ("setup_token", self._hash(token), now),
            ).fetchone()
            if not row:
                return False
            if consume:
                conn.execute("UPDATE setup_sessions SET consumed_at = ? WHERE id = ?", (now, int(row["id"])))
            return True
