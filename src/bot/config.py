from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    bot_token: str
    openai_api_key: str
    run_mode: str
    log_level: str
    db_path: Path
    webhook_host: str
    webhook_port: int
    webhook_public_url: str
    webhook_path: str
    http_api_enabled: bool
    http_api_host: str
    http_api_port: int
    admin_api_token: str
    default_mode: str
    default_ai_enabled: bool
    default_ai_threshold: float
    default_action_policy: str
    default_rate_limit_policy: str
    default_language: str
    default_level3_mute_seconds: int
    ai_low_risk_model: str
    ai_high_risk_model: str
    ai_timeout_seconds: int


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> AppConfig:
    load_dotenv()
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        raise ValueError("Missing BOT_TOKEN")
    return AppConfig(
        bot_token=bot_token,
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        run_mode=os.getenv("RUN_MODE", "polling").strip().lower(),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        db_path=Path(os.getenv("DB_PATH", "data/bot.db")),
        webhook_host=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "8080")),
        webhook_public_url=os.getenv("WEBHOOK_PUBLIC_URL", ""),
        webhook_path=os.getenv("WEBHOOK_PATH", "/telegram/webhook"),
        http_api_enabled=_bool("HTTP_API_ENABLED", True),
        http_api_host=os.getenv("HTTP_API_HOST", "0.0.0.0"),
        http_api_port=int(os.getenv("HTTP_API_PORT", "8080")),
        admin_api_token=os.getenv("ADMIN_API_TOKEN", ""),
        default_mode=os.getenv("DEFAULT_MODE", "balanced"),
        default_ai_enabled=_bool("DEFAULT_AI_ENABLED", True),
        default_ai_threshold=float(os.getenv("DEFAULT_AI_THRESHOLD", "0.75")),
        default_action_policy=os.getenv("DEFAULT_ACTION_POLICY", "progressive"),
        default_rate_limit_policy=os.getenv("DEFAULT_RATE_LIMIT_POLICY", "default"),
        default_language=os.getenv("DEFAULT_LANGUAGE", "zh"),
        default_level3_mute_seconds=int(os.getenv("DEFAULT_LEVEL3_MUTE_SECONDS", "604800")),
        ai_low_risk_model=os.getenv("AI_LOW_RISK_MODEL", "gpt-4.1-mini"),
        ai_high_risk_model=os.getenv("AI_HIGH_RISK_MODEL", "gpt-5.2"),
        ai_timeout_seconds=int(os.getenv("AI_TIMEOUT_SECONDS", "12")),
    )
