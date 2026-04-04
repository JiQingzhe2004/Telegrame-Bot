from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any

from telegram import Update
from telegram.ext import Application

from bot.ai.openai_client import AiRuntimeConfig, OpenAiModerator
from bot.domain.moderation import Enforcer, ModerationService
from bot.domain.rules import default_rules
from bot.storage.repo import BotRepository
from bot.system_config import ConfigService, RuntimeConfig

logger = logging.getLogger(__name__)


class RuntimeManager:
    def __init__(
        self,
        repo: BotRepository,
        config_service: ConfigService,
        build_application_fn,
        webhook_path: str = "/telegram/webhook",
    ) -> None:
        self.repo = repo
        self.config_service = config_service
        self.build_application_fn = build_application_fn
        self.webhook_path = webhook_path
        self._lock = asyncio.Lock()
        self._tg_app: Application | None = None
        self._enforcer: Enforcer | None = None
        self._ai_moderator: OpenAiModerator | None = None
        self._state = "setup"

    @property
    def state(self) -> str:
        return self._state

    def is_active(self) -> bool:
        return self._state == "active" and self._tg_app is not None

    def _apply_repo_defaults(self, conf: RuntimeConfig) -> None:
        self.repo.defaults = {
            "chat_enabled": False,
            "mode": conf.default_mode,
            "ai_enabled": conf.default_ai_enabled,
            "ai_threshold": conf.default_ai_threshold,
            "allow_admin_self_test": False,
            "action_policy": conf.default_action_policy,
            "rate_limit_policy": conf.default_rate_limit_policy,
            "language": conf.default_language,
            "level3_mute_seconds": conf.default_level3_mute_seconds,
        }

    async def startup(self) -> None:
        conf = self.config_service.get_runtime_config()
        if self.config_service.is_complete(conf):
            await self.reload(conf)
            return
        self._state = "setup"

    async def shutdown(self) -> None:
        async with self._lock:
            await self._stop_current()
            self._state = "setup"

    async def sync_bot_commands(self) -> None:
        async with self._lock:
            if not self._tg_app:
                raise RuntimeError("runtime not active")
            if callable(getattr(self._tg_app, "post_init", None)):
                await self._tg_app.post_init(self._tg_app)

    async def reload(self, conf: RuntimeConfig | None = None) -> None:
        async with self._lock:
            next_conf = conf or self.config_service.get_runtime_config()
            if not self.config_service.is_complete(next_conf):
                await self._stop_current()
                self._state = "setup"
                return
            self._apply_repo_defaults(next_conf)
            await self._stop_current()
            await self._start_from_config(next_conf)
            self._state = "active"

    async def _start_from_config(self, conf: RuntimeConfig) -> None:
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
        enforcer = Enforcer(self.repo)
        tg_app = self.build_application_fn(
            bot_token=conf.bot_token,
            repo=self.repo,
            moderation_service=moderation_service,
            enforcer=enforcer,
            ai_moderator=ai,
            runtime_config=conf,
        )

        await tg_app.initialize()
        if callable(getattr(tg_app, "post_init", None)):
            await tg_app.post_init(tg_app)
        await tg_app.start()
        if conf.run_mode == "webhook":
            if conf.webhook_public_url:
                webhook_url = f"{conf.webhook_public_url.rstrip('/')}{self.webhook_path}"
                await tg_app.bot.set_webhook(url=webhook_url)
        else:
            await tg_app.bot.delete_webhook(drop_pending_updates=True)
            await tg_app.updater.start_polling(drop_pending_updates=True)
        self._tg_app = tg_app
        self._enforcer = enforcer
        self._ai_moderator = ai
        logger.info("runtime activated run_mode=%s", conf.run_mode)

    async def _stop_current(self) -> None:
        if not self._tg_app:
            self._tg_app = None
            self._enforcer = None
            self._ai_moderator = None
            return
        app = self._tg_app
        if app.updater and app.updater.running:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()
        self._tg_app = None
        self._enforcer = None
        self._ai_moderator = None

    def runtime_state(self) -> dict[str, Any]:
        conf = self.config_service.get_runtime_config()
        return {
            "state": self._state,
            "config_complete": self.config_service.is_complete(conf),
            "config_version": 1,
            "run_mode": conf.run_mode,
        }

    async def process_webhook_update(self, payload: dict[str, Any]) -> None:
        if not self._tg_app:
            raise RuntimeError("runtime not active")
        update = Update.de_json(payload, self._tg_app.bot)
        await self._tg_app.process_update(update)

    def get_bot_application(self) -> Application | None:
        return self._tg_app

    def get_enforcer(self) -> Enforcer | None:
        return self._enforcer

    def get_ai_moderator(self) -> OpenAiModerator | None:
        return self._ai_moderator

    def get_runtime_config_public(self) -> dict[str, Any]:
        return self.config_service.get_runtime_config().redacted()

    def get_runtime_config_raw(self) -> RuntimeConfig:
        return self.config_service.get_runtime_config()

    def get_admin_token(self) -> str:
        return self.config_service.get_runtime_config().admin_api_token

    def verify_admin_token(self, token: str) -> bool:
        return self.config_service.verify_admin_token(token)

    def update_runtime_config(self, payload: dict[str, Any]) -> RuntimeConfig:
        return self.config_service.save_runtime_config(payload)

    def validate_runtime_payload(self, payload: dict[str, Any]) -> list[str]:
        conf = RuntimeConfig.from_dict(asdict(self.config_service.get_runtime_config()) | payload)
        return self.config_service.validate_config(conf)
