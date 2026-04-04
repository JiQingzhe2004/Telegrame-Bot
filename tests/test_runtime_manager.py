import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.runtime_manager import RuntimeManager
from bot.system_config import RuntimeConfig


class _FakeConfigService:
    def __init__(self, conf: RuntimeConfig) -> None:
        self._conf = conf

    def get_runtime_config(self) -> RuntimeConfig:
        return self._conf

    def is_complete(self, conf: RuntimeConfig) -> bool:
        return True


class _FakeRepo:
    def __init__(self) -> None:
        self.defaults = {}


def test_runtime_manager_runs_post_init_when_starting() -> None:
    conf = RuntimeConfig(bot_token="token", run_mode="polling")
    repo = _FakeRepo()
    post_init = AsyncMock()
    tg_app = SimpleNamespace(
        initialize=AsyncMock(),
        start=AsyncMock(),
        stop=AsyncMock(),
        shutdown=AsyncMock(),
        post_init=post_init,
        bot=SimpleNamespace(delete_webhook=AsyncMock()),
        updater=SimpleNamespace(start_polling=AsyncMock(), running=False),
    )

    manager = RuntimeManager(
        repo=repo,
        config_service=_FakeConfigService(conf),
        build_application_fn=lambda **_: tg_app,
    )

    asyncio.run(manager.reload(conf))

    tg_app.initialize.assert_awaited_once()
    post_init.assert_awaited_once_with(tg_app)
    tg_app.start.assert_awaited_once()
    tg_app.bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=True)
    tg_app.updater.start_polling.assert_awaited_once_with(drop_pending_updates=True)
