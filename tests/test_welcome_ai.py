import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.ai.openai_client import AiRuntimeConfig, OpenAiModerator
from bot.system_config import RuntimeConfig
from bot.telegram.adapter_ptb import _build_welcome_text


def make_context(ai_moderator):
    return SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "repo": None,
                "ai_moderator": ai_moderator,
            }
        )
    )


def test_welcome_uses_ai_and_passes_template_hint():
    ai = OpenAiModerator(AiRuntimeConfig(api_key="", base_url="", low_risk_model="gpt-4.1-mini", high_risk_model="gpt-5.2", timeout_seconds=12))
    ai.generate_welcome = AsyncMock(return_value="欢迎小明，进群先看群规。")  # type: ignore[method-assign]
    context = make_context(ai)
    runtime_config = RuntimeConfig(
        join_welcome_enabled=True,
        join_welcome_use_ai=True,
        join_welcome_template="欢迎 {user} 加入 {chat}，请先阅读群规。",
    )

    out = asyncio.run(
        _build_welcome_text(
            context,
            runtime_config,
            chat_id=1,
            chat_title="测试群",
            chat_type="supergroup",
            user_name="小明",
        )
    )

    assert out == "欢迎小明，进群先看群规。"
    ai.generate_welcome.assert_awaited_once()
    kwargs = ai.generate_welcome.await_args.kwargs
    assert kwargs["template"] == "欢迎 {user} 加入 {chat}，请先阅读群规。"
    assert kwargs["user_display_name"] == "小明"
    assert kwargs["chat_title"] == "测试群"


def test_welcome_falls_back_to_template_when_ai_fails():
    ai = OpenAiModerator(AiRuntimeConfig(api_key="", base_url="", low_risk_model="gpt-4.1-mini", high_risk_model="gpt-5.2", timeout_seconds=12))
    ai.generate_welcome = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]
    context = make_context(ai)
    runtime_config = RuntimeConfig(
        join_welcome_enabled=True,
        join_welcome_use_ai=True,
        join_welcome_template="欢迎 {user} 加入 {chat}，请先阅读群规。",
    )

    out = asyncio.run(
        _build_welcome_text(
            context,
            runtime_config,
            chat_id=1,
            chat_title="测试群",
            chat_type="supergroup",
            user_name="小明",
        )
    )

    assert out == "欢迎 小明 加入 测试群，请先阅读群规。"
