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
