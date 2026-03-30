from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from bot.ai.prompts import build_system_prompt, build_user_prompt
from bot.ai.redact import redact_pii
from bot.domain.models import AiDecision, MessageRef, ModerationContext

logger = logging.getLogger(__name__)

ALLOWED_CATEGORY = {"ok", "spam", "scam", "harassment", "sexual", "violence", "personal_data", "other"}
ALLOWED_ACTION = {"none", "warn", "delete", "mute", "restrict", "kick", "ban"}


@dataclass(frozen=True)
class AiRuntimeConfig:
    api_key: str
    low_risk_model: str
    high_risk_model: str
    timeout_seconds: int


def _coerce(data: dict[str, Any]) -> AiDecision:
    category = str(data.get("category", "other"))
    if category not in ALLOWED_CATEGORY:
        raise ValueError("invalid category")
    level = int(data.get("level", 1))
    if level < 0 or level > 3:
        raise ValueError("invalid level")
    confidence = float(data.get("confidence", 0.5))
    if not 0 <= confidence <= 1:
        raise ValueError("invalid confidence")
    action = str(data.get("suggested_action", "warn"))
    if action not in ALLOWED_ACTION:
        raise ValueError("invalid action")
    reasons = data.get("reasons", [])
    if not isinstance(reasons, list):
        raise ValueError("invalid reasons")
    return AiDecision(
        category=category,
        level=level,
        confidence=confidence,
        reasons=[str(x) for x in reasons][:5],
        suggested_action=action,
        should_escalate_to_admin=bool(data.get("should_escalate_to_admin", False)),
        raw=data,
    )


class OpenAiModerator:
    def __init__(self, conf: AiRuntimeConfig) -> None:
        self.conf = conf
        self.client = AsyncOpenAI(api_key=conf.api_key) if conf.api_key else None

    def choose_model(self, context: ModerationContext) -> str:
        if context.strike_score >= 2 or context.settings.mode == "strict":
            return self.conf.high_risk_model
        return self.conf.low_risk_model

    async def classify(self, message: MessageRef, context: ModerationContext) -> AiDecision:
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        text = redact_pii(message.text or "")
        model = self.choose_model(context)
        response = await self.client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": build_user_prompt(message, context, text)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "moderation_output",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "category": {"type": "string"},
                            "level": {"type": "integer"},
                            "confidence": {"type": "number"},
                            "reasons": {"type": "array", "items": {"type": "string"}},
                            "suggested_action": {"type": "string"},
                            "should_escalate_to_admin": {"type": "boolean"},
                        },
                        "required": [
                            "category",
                            "level",
                            "confidence",
                            "reasons",
                            "suggested_action",
                            "should_escalate_to_admin",
                        ],
                    },
                    "strict": True,
                }
            },
            timeout=self.conf.timeout_seconds,
        )
        raw_text = response.output_text
        if not raw_text:
            raise ValueError("empty AI response")
        data = json.loads(raw_text)
        decision = _coerce(data)
        logger.info("ai_classified model=%s level=%s category=%s", model, decision.level, decision.category)
        return decision
