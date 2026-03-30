from datetime import timezone

from bot.domain.models import ChatRef, ChatSettings, MessageRef, ModerationContext, UserRef
from bot.domain.rules import BanwordRule, FloodRule, SuspiciousLinkRule
from bot.utils.time import utc_now


def make_context(**kwargs):
    base = ModerationContext(
        chat=ChatRef(chat_id=1, type="supergroup"),
        user=UserRef(user_id=2, username="u", is_bot=False),
        settings=ChatSettings(chat_id=1),
        strike_score=0,
        whitelist_hit=False,
        blacklist_words=["诈骗", "拉群"],
        recent_message_texts=["a", "a", "a"],
    )
    data = base.__dict__ | kwargs
    return ModerationContext(**data)


def make_msg(text: str):
    return MessageRef(
        chat_id=1,
        message_id=1,
        user_id=2,
        date=utc_now().astimezone(timezone.utc),
        text=text,
        meta={},
    )


def test_banword_rule_hit():
    r = BanwordRule()
    out = r.evaluate(make_msg("这是一条诈骗消息"), make_context())
    assert out.hit is True
    assert out.level >= 1


def test_link_rule_hit():
    r = SuspiciousLinkRule()
    out = r.evaluate(make_msg("看看 http://bit.ly/abc"), make_context())
    assert out.hit is True
    assert out.level == 2


def test_flood_rule_repeat_hit():
    r = FloodRule()
    ctx = make_context(recent_message_texts=["hi", "hi", "hi", "hello"])
    out = r.evaluate(make_msg("hi"), ctx)
    assert out.hit is True
    assert out.level == 2
