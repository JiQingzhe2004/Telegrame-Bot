import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.domain.models import MessageRef, ModerationDecision
from bot.domain.moderation import Enforcer, PermissionSnapshot
from bot.utils.time import utc_now


def test_warn_notice_uses_real_username_and_chinese_reason():
    bot = AsyncMock()
    enforcer = Enforcer(SimpleNamespace())
    message = MessageRef(
        chat_id=1,
        message_id=10,
        user_id=123456,
        date=utc_now(),
        text="bad",
        meta={"username": "alice", "display_name": "Alice"},
    )
    decision = ModerationDecision(
        final_level=1,
        final_action="warn",
        reason_codes=["rule.banword"],
        rule_results=[],
        ai_used=False,
        ai_decision=None,
        confidence=0.9,
    )

    result = asyncio.run(enforcer.apply(bot, message, decision, PermissionSnapshot(True, True, True)))

    assert result.success is True
    bot.send_message.assert_awaited_once()
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == 1
    assert "@alice" in kwargs["text"]
    assert "@123456" not in kwargs["text"]
    assert "命中违禁词" in kwargs["text"]
    assert kwargs["parse_mode"] == "HTML"


def test_ban_notice_uses_clickable_mention_when_no_username():
    bot = AsyncMock()
    enforcer = Enforcer(SimpleNamespace())
    message = MessageRef(
        chat_id=1,
        message_id=11,
        user_id=987654,
        date=utc_now(),
        text="spam",
        meta={"display_name": "张三"},
    )
    decision = ModerationDecision(
        final_level=3,
        final_action="ban",
        reason_codes=["ai.spam"],
        rule_results=[],
        ai_used=True,
        ai_decision=None,
        confidence=0.98,
    )

    result = asyncio.run(enforcer.apply(bot, message, decision, PermissionSnapshot(True, True, True)))

    assert result.success is True
    bot.ban_chat_member.assert_awaited_once_with(chat_id=1, user_id=987654)
    kwargs = bot.send_message.await_args.kwargs
    assert 'tg://user?id=987654' in kwargs["text"]
    assert "张三" in kwargs["text"]
    assert "AI 判定为垃圾信息" in kwargs["text"]
    assert "已被封禁" in kwargs["text"]
