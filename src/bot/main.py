from __future__ import annotations

import asyncio
import logging

import uvicorn

from bot.api.http_api import Services, create_http_app
from bot.config import load_config
from bot.logging_setup import setup_logging
from bot.runtime_manager import RuntimeManager
from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository
from bot.system_config import ConfigService
from bot.telegram.adapter_ptb import build_application

logger = logging.getLogger(__name__)


async def async_main() -> None:
    conf = load_config()
    setup_logging(conf.log_level)

    db = Database(conf.db_path)
    migrate(db)

    config_service = ConfigService(db)
    runtime_conf = config_service.get_runtime_config()
    repo = BotRepository(
        db=db,
        defaults={
            "chat_enabled": False,
            "mode": runtime_conf.default_mode,
            "ai_enabled": runtime_conf.default_ai_enabled,
            "ai_threshold": runtime_conf.default_ai_threshold,
            "allow_admin_self_test": False,
            "action_policy": runtime_conf.default_action_policy,
            "rate_limit_policy": runtime_conf.default_rate_limit_policy,
            "language": runtime_conf.default_language,
            "level3_mute_seconds": runtime_conf.default_level3_mute_seconds,
        },
    )
    runtime_manager = RuntimeManager(
        repo=repo,
        config_service=config_service,
        build_application_fn=build_application,
    )
    await runtime_manager.startup()
    state = runtime_manager.runtime_state()
    if state["state"] == "setup":
        code = config_service.issue_bootstrap_code(ttl_minutes=20)
        logger.warning("SETUP MODE: 请在前端输入首次启动口令: %s", code)

    http_app = create_http_app(
        Services(
            repo=repo,
            config_service=config_service,
            runtime_manager=runtime_manager,
            cors_origins=conf.http_api_cors_origins,
            web_admin_dist_path=conf.web_admin_dist_path,
        ),
        webhook_path="/telegram/webhook",
    )
    uv_conf = uvicorn.Config(http_app, host=conf.http_host, port=conf.http_port, log_level="info")
    server = uvicorn.Server(uv_conf)
    try:
        await server.serve()
    finally:
        await runtime_manager.shutdown()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
