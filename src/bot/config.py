from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    log_level: str
    db_path: Path
    http_host: str
    http_port: int
    webhook_host: str
    webhook_port: int
    http_api_cors_origins: tuple[str, ...]
    web_admin_dist_path: Path


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple([x.strip() for x in value.split(",") if x.strip()])


def load_config() -> AppConfig:
    load_dotenv()
    return AppConfig(
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        db_path=Path(os.getenv("DB_PATH", "data/bot.db")),
        http_host=os.getenv("HTTP_API_HOST", "0.0.0.0"),
        # 默认使用 80，减少公网部署/Cloudflare 回源端口配置成本
        http_port=int(os.getenv("HTTP_API_PORT", "80")),
        webhook_host=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "80")),
        http_api_cors_origins=_split_csv(
            os.getenv("HTTP_API_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
        ),
        web_admin_dist_path=Path(os.getenv("WEB_ADMIN_DIST_PATH", "web-admin/dist")),
    )
