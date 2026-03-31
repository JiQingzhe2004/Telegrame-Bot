import asyncio
from datetime import timezone

from bot.domain.models import AiDecision, ChatRef, ChatSettings, MessageRef, ModerationContext, UserRef
from bot.domain.moderation import ModerationService
from bot.domain.rules import default_rules
from bot.utils.time import utc_now


class FakeAi:
    async def classify(self, message, context):
        return AiDecision(
            category="harassment",
            level=2,
            confidence=0.88,
            reasons=["contextual abuse"],
            suggested_action="delete",
            should_escalate_to_admin=False,
            raw={"fake": True},
        )


def test_e2e_decision_with_ai():
    service = ModerationService(default_rules(), FakeAi())
    msg = MessageRef(
        chat_id=1,
        message_id=9,
        user_id=2,
        date=utc_now().astimezone(timezone.utc),
        text="你这个人真恶心",
        meta={},
    )
    ctx = ModerationContext(
        chat=ChatRef(chat_id=1, type="supergroup"),
        user=UserRef(user_id=2, username="u", is_bot=False),
        settings=ChatSettings(chat_id=1),
        strike_score=1,
        whitelist_hit=False,
        blacklist_words=[],
        recent_message_texts=["x", "y"],
    )
    out = asyncio.run(service.decide(msg, ctx))
    assert out.final_level == 2
    assert out.ai_used is True
    assert out.ai_status == "success"


def test_e2e_webhook_like_low_confidence_downgrade():
    class LowConfidenceAi:
        async def classify(self, message, context):
            return AiDecision(
                category="scam",
                level=3,
                confidence=0.2,
                reasons=["maybe scam"],
                suggested_action="kick",
                should_escalate_to_admin=True,
                raw={},
            )

    service = ModerationService(default_rules(), LowConfidenceAi())
    msg = MessageRef(
        chat_id=1,
        message_id=10,
        user_id=3,
        date=utc_now().astimezone(timezone.utc),
        text="加我返利",
        meta={},
    )
    ctx = ModerationContext(
        chat=ChatRef(chat_id=1, type="supergroup"),
        user=UserRef(user_id=3, username="u2", is_bot=False),
        settings=ChatSettings(chat_id=1, ai_threshold=0.75),
        strike_score=4,
        whitelist_hit=False,
        blacklist_words=[],
        recent_message_texts=[],
    )
    out = asyncio.run(service.decide(msg, ctx))
    assert out.final_action == "warn"


def test_high_level_rule_still_calls_ai():
    class SpyAi:
        def __init__(self) -> None:
            self.called = 0

        async def classify(self, message, context):
            self.called += 1
            return AiDecision(
                category="spam",
                level=1,
                confidence=0.82,
                reasons=["ai checked"],
                suggested_action="warn",
                should_escalate_to_admin=False,
                raw={"_model": "fake-model"},
            )

    ai = SpyAi()
    service = ModerationService(default_rules(), ai)
    msg = MessageRef(
        chat_id=1,
        message_id=11,
        user_id=4,
        date=utc_now().astimezone(timezone.utc),
        text="spam test",
        meta={},
    )
    ctx = ModerationContext(
        chat=ChatRef(chat_id=1, type="supergroup"),
        user=UserRef(user_id=4, username="u4", is_bot=False),
        settings=ChatSettings(chat_id=1),
        strike_score=0,
        whitelist_hit=False,
        blacklist_words=["spam", "test"],
        recent_message_texts=[],
    )

    out = asyncio.run(service.decide(msg, ctx))

    assert ai.called == 1
    assert out.ai_used is True
    assert out.ai_status == "success"
    assert out.final_level == 2


def test_e2e_ai_failure_sets_failed_status():
    class BrokenAi:
        async def classify(self, message, context):
            raise RuntimeError("ai down")

    service = ModerationService(default_rules(), BrokenAi())
    msg = MessageRef(
        chat_id=1,
        message_id=12,
        user_id=5,
        date=utc_now().astimezone(timezone.utc),
        text="普通消息",
        meta={},
    )
    ctx = ModerationContext(
        chat=ChatRef(chat_id=1, type="supergroup"),
        user=UserRef(user_id=5, username="u5", is_bot=False),
        settings=ChatSettings(chat_id=1),
        strike_score=0,
        whitelist_hit=False,
        blacklist_words=[],
        recent_message_texts=[],
    )

    out = asyncio.run(service.decide(msg, ctx))

    assert out.ai_used is True
    assert out.ai_status == "failed"
    assert out.ai_error == "ai down"
