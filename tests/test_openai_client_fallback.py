import asyncio
from types import SimpleNamespace

from bot.ai.openai_client import AiRuntimeConfig, OpenAiModerator
from bot.domain.models import ChatRef, ChatSettings, MessageRef, ModerationContext, UserRef
from bot.utils.time import utc_now


class FakeResponsesApi:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        raise self.exc


class FakeChatCompletionsApi:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            model=kwargs["model"],
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ],
        )


def make_ai() -> OpenAiModerator:
    ai = OpenAiModerator(
        AiRuntimeConfig(
            api_key="test-key",
            base_url="https://compatible.example/v1",
            low_risk_model="test-low-model",
            high_risk_model="test-high-model",
            timeout_seconds=12,
        )
    )
    return ai


def make_context() -> ModerationContext:
    return ModerationContext(
        chat=ChatRef(chat_id=1, type="supergroup", title="测试群"),
        user=UserRef(user_id=2, username="tester", is_bot=False),
        settings=ChatSettings(chat_id=1),
        strike_score=0,
        whitelist_hit=False,
        blacklist_words=[],
        recent_message_texts=[],
    )


def make_message() -> MessageRef:
    return MessageRef(
        chat_id=1,
        message_id=10,
        user_id=2,
        date=utc_now(),
        text="测试广告消息",
        meta={},
    )


def test_classify_falls_back_to_chat_completions_for_compatible_base_url():
    ai = make_ai()
    responses_api = FakeResponsesApi(RuntimeError("404 page not found"))
    chat_api = FakeChatCompletionsApi(
        '```json\n{"category":"spam","level":2,"confidence":0.91,"reasons":["fallback"],"suggested_action":"delete","should_escalate_to_admin":false}\n```'
    )
    ai.client = SimpleNamespace(
        responses=responses_api,
        chat=SimpleNamespace(completions=chat_api),
    )

    decision = asyncio.run(ai.classify(make_message(), make_context()))

    assert responses_api.calls == 1
    assert chat_api.calls == 1
    assert decision.category == "spam"
    assert decision.level == 2
    assert decision.raw["_model"] == "test-low-model"


def test_generate_welcome_falls_back_to_chat_completions_for_compatible_base_url():
    ai = make_ai()
    responses_api = FakeResponsesApi(RuntimeError("unsupported endpoint"))
    chat_api = FakeChatCompletionsApi("欢迎 小明 加入测试群，请先阅读群规。")
    ai.client = SimpleNamespace(
        responses=responses_api,
        chat=SimpleNamespace(completions=chat_api),
    )

    result = asyncio.run(
        ai.generate_welcome_result(
            chat_title="测试群",
            user_display_name="小明",
            language="zh",
            template="欢迎 {user} 加入 {chat}，请先阅读群规。",
            time_of_day="evening",
            chat_type="supergroup",
        )
    )

    assert responses_api.calls == 1
    assert chat_api.calls == 1
    assert result.model == "test-low-model"
    assert "小明" in result.text


def test_generate_verification_questions_falls_back_to_chat_completions_for_compatible_base_url():
    ai = make_ai()
    responses_api = FakeResponsesApi(RuntimeError("unsupported endpoint"))
    chat_api = FakeChatCompletionsApi(
        '```json\n{"questions":[{"question":"进群后先做什么？","options":["看群规","发广告"],"answer_index":0}]}\n```'
    )
    ai.client = SimpleNamespace(
        responses=responses_api,
        chat=SimpleNamespace(completions=chat_api),
    )

    result = asyncio.run(
        ai.generate_verification_questions_result(
            chat_title="测试群",
            language="zh",
            count=1,
            topic_hint="群规",
            chat_type="supergroup",
        )
    )

    assert responses_api.calls == 1
    assert chat_api.calls == 1
    assert result.model == "test-low-model"
    assert len(result.items) == 1
    assert result.items[0].question == "进群后先做什么？"
