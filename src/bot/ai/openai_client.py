from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from bot.ai.prompts import (
    build_system_prompt,
    build_user_prompt,
    build_welcome_system_prompt,
    build_welcome_user_prompt,
)
from bot.ai.redact import redact_pii
from bot.domain.models import AiDecision, MessageRef, ModerationContext

logger = logging.getLogger(__name__)

ALLOWED_CATEGORY = {"ok", "spam", "scam", "harassment", "sexual", "violence", "personal_data", "other"}
ALLOWED_ACTION = {"none", "warn", "delete", "mute", "restrict", "kick", "ban"}


@dataclass(frozen=True)
class AiRuntimeConfig:
    api_key: str
    base_url: str
    low_risk_model: str
    high_risk_model: str
    timeout_seconds: int


@dataclass(frozen=True)
class AiWelcomeResult:
    model: str
    text: str


@dataclass(frozen=True)
class _AiTextResult:
    model: str
    text: str
    transport: str


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
        if not conf.api_key:
            self.client = None
        elif conf.base_url:
            self.client = AsyncOpenAI(api_key=conf.api_key, base_url=conf.base_url)
        else:
            self.client = AsyncOpenAI(api_key=conf.api_key)

    def choose_model(self, context: ModerationContext) -> str:
        if context.strike_score >= 2 or context.settings.mode == "strict":
            return self.conf.high_risk_model
        return self.conf.low_risk_model

    @staticmethod
    def _extract_content_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if not content:
            return ""
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    text = item
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("value") or ""
                else:
                    text = getattr(item, "text", None) or getattr(item, "value", None) or ""
                if text:
                    parts.append(str(text))
            return "\n".join(parts).strip()
        if isinstance(content, dict):
            return str(content.get("text") or content.get("value") or "").strip()
        return str(content).strip()

    def _extract_response_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        output = getattr(response, "output", None)
        if not output:
            return ""
        parts: list[str] = []
        for item in output:
            content = getattr(item, "content", None)
            if content is None and isinstance(item, dict):
                content = item.get("content")
            text = self._extract_content_text(content)
            if text:
                parts.append(text)
        return "\n".join(parts).strip()

    def _extract_chat_completion_text(self, response: Any) -> str:
        choices = getattr(response, "choices", None)
        if choices is None and isinstance(response, dict):
            choices = response.get("choices")
        if not choices:
            return ""
        first = choices[0]
        message = getattr(first, "message", None)
        if message is None and isinstance(first, dict):
            message = first.get("message")
        if message is None:
            return ""
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        return self._extract_content_text(content)

    @staticmethod
    def _extract_json_text(raw_text: str) -> str:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[-1].strip().startswith("```"):
                text = "\n".join(lines[1:-1]).strip()
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return text[start : end + 1]
            raise

    def _should_fallback_to_chat_completions(self, exc: Exception) -> bool:
        if not self.conf.base_url:
            return False
        if isinstance(exc, ValueError):
            return False
        status_code = getattr(exc, "status_code", None)
        if status_code in {401, 403, 429}:
            return False
        return True

    async def _request_with_responses(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> _AiTextResult:
        request: dict[str, Any] = {
            "model": model,
            "instructions": system_prompt,
            "input": user_prompt,
            "timeout": self.conf.timeout_seconds,
        }
        if schema is not None:
            request["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "moderation_output",
                    "schema": schema,
                    "strict": True,
                }
            }
        response = await self.client.responses.create(**request)
        text = self._extract_response_text(response)
        if not text:
            raise ValueError("empty AI response")
        return _AiTextResult(
            model=str(getattr(response, "model", None) or model),
            text=text.strip(),
            transport="responses",
        )

    async def _request_with_chat_completions(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> _AiTextResult:
        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            timeout=self.conf.timeout_seconds,
        )
        text = self._extract_chat_completion_text(response)
        if not text:
            raise ValueError("empty AI response")
        return _AiTextResult(
            model=str(getattr(response, "model", None) or model),
            text=text.strip(),
            transport="chat.completions",
        )

    async def _request_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> _AiTextResult:
        try:
            return await self._request_with_responses(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
            )
        except Exception as exc:  # noqa: BLE001
            if not self._should_fallback_to_chat_completions(exc):
                raise
            logger.warning("responses api failed for model=%s, fallback to chat.completions: %s", model, exc)
            try:
                return await self._request_with_chat_completions(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
            except Exception as fallback_exc:  # noqa: BLE001
                raise RuntimeError(
                    f"responses_failed: {exc}; chat_completions_failed: {fallback_exc}"
                ) from fallback_exc

    async def classify(self, message: MessageRef, context: ModerationContext) -> AiDecision:
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        text = redact_pii(message.text or "")
        model = self.choose_model(context)
        result = await self._request_text(
            model=model,
            system_prompt=build_system_prompt(),
            user_prompt=build_user_prompt(message, context, text),
            schema={
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
        )
        data = json.loads(self._extract_json_text(result.text))
        data["_model"] = result.model
        decision = _coerce(data)
        logger.info(
            "ai_classified model=%s transport=%s level=%s category=%s",
            result.model,
            result.transport,
            decision.level,
            decision.category,
        )
        return decision

    async def generate_welcome(self, *, chat_title: str, user_display_name: str, language: str, template: str, time_of_day: str | None = None, chat_type: str | None = None) -> str:
        result = await self.generate_welcome_result(
            chat_title=chat_title,
            user_display_name=user_display_name,
            language=language,
            template=template,
            time_of_day=time_of_day,
            chat_type=chat_type,
        )
        return result.text

    async def generate_welcome_result(
        self,
        *,
        chat_title: str,
        user_display_name: str,
        language: str,
        template: str,
        time_of_day: str | None = None,
        chat_type: str | None = None,
    ) -> AiWelcomeResult:
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        model = self.conf.low_risk_model or self.conf.high_risk_model
        result = await self._request_text(
            model=model,
            system_prompt=build_welcome_system_prompt(),
            user_prompt=build_welcome_user_prompt(
                chat_title=chat_title,
                user_display_name=user_display_name,
                language=language,
                template=template,
                time_of_day=time_of_day,
                chat_type=chat_type,
            ),
        )
        text = result.text.strip()
        if not text:
            raise ValueError("empty welcome response")
        if len(text) > 180:
            text = text[:180].strip()
        logger.info("ai_welcome_generated model=%s transport=%s", result.model, result.transport)
        return AiWelcomeResult(model=result.model, text=text)
