from __future__ import annotations

import asyncio
import logging
import signal

import uvicorn

from bot.ai.openai_client import AiRuntimeConfig, OpenAiModerator
from bot.api.http_api import Services, create_http_app
from bot.config import load_config
from bot.domain.moderation import Enforcer, ModerationService
from bot.domain.rules import default_rules
from bot.logging_setup import setup_logging
from bot.storage.db import Database
from bot.storage.migrations import migrate
from bot.storage.repo import BotRepository
from bot.telegram.adapter_ptb import build_application

logger = logging.getLogger(__name__)


async def run_polling_with_api(conf, tg_app, http_app) -> None:
    server = None
    api_task = None
    if conf.http_api_enabled:
        uv_conf = uvicorn.Config(http_app, host=conf.http_api_host, port=conf.http_api_port, log_level="info")
        server = uvicorn.Server(uv_conf)
        api_task = asyncio.create_task(server.serve())

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(drop_pending_updates=True)
    stop_event = asyncio.Event()

    def _stop(*_) -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    await stop_event.wait()
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()

    if server:
        server.should_exit = True
    if api_task:
        await api_task


async def run_webhook(conf, tg_app, http_app) -> None:
    await tg_app.initialize()
    await tg_app.start()
    if conf.webhook_public_url:
        await tg_app.bot.set_webhook(url=f"{conf.webhook_public_url.rstrip('/')}{conf.webhook_path}")
    uv_conf = uvicorn.Config(http_app, host=conf.webhook_host, port=conf.webhook_port, log_level="info")
    server = uvicorn.Server(uv_conf)
    await server.serve()
    await tg_app.stop()
    await tg_app.shutdown()


async def async_main() -> None:
    conf = load_config()
    setup_logging(conf.log_level)
    db = Database(conf.db_path)
    migrate(db)
    repo = BotRepository(
        db=db,
        defaults={
            "mode": conf.default_mode,
            "ai_enabled": conf.default_ai_enabled,
            "ai_threshold": conf.default_ai_threshold,
            "action_policy": conf.default_action_policy,
            "rate_limit_policy": conf.default_rate_limit_policy,
            "language": conf.default_language,
            "level3_mute_seconds": conf.default_level3_mute_seconds,
        },
    )
    ai = OpenAiModerator(
        AiRuntimeConfig(
            api_key=conf.openai_api_key,
            base_url=conf.openai_base_url,
            low_risk_model=conf.ai_low_risk_model,
            high_risk_model=conf.ai_high_risk_model,
            timeout_seconds=conf.ai_timeout_seconds,
        )
    )
    moderation_service = ModerationService(default_rules(), ai)
    enforcer = Enforcer(repo)

    tg_app = build_application(
        bot_token=conf.bot_token,
        repo=repo,
        moderation_service=moderation_service,
        enforcer=enforcer,
    )
    http_app = create_http_app(
        Services(repo=repo, admin_token=conf.admin_api_token, tg_app=tg_app, enforcer=enforcer),
        webhook_path=conf.webhook_path,
    )
    logger.info("starting run_mode=%s", conf.run_mode)
    if conf.run_mode == "webhook":
        await run_webhook(conf, tg_app, http_app)
        return
    await run_polling_with_api(conf, tg_app, http_app)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
