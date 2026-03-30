import pytest

from bot.ai.openai_client import _coerce


def test_ai_schema_parse_ok():
    out = _coerce(
        {
            "category": "spam",
            "level": 2,
            "confidence": 0.9,
            "reasons": ["link spam"],
            "suggested_action": "delete",
            "should_escalate_to_admin": False,
        }
    )
    assert out.category == "spam"
    assert out.level == 2


def test_ai_schema_parse_invalid_level():
    with pytest.raises(ValueError):
        _coerce(
            {
                "category": "spam",
                "level": 7,
                "confidence": 0.9,
                "reasons": ["x"],
                "suggested_action": "delete",
                "should_escalate_to_admin": False,
            }
        )
