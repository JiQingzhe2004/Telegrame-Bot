from __future__ import annotations

from bot.domain.models import MessageRef, ModerationContext

SCHEMA_DOC = {
    "category": "ok|spam|scam|harassment|sexual|violence|personal_data|other",
    "level": "0..3",
    "confidence": "0..1",
    "reasons": ["string"],
    "suggested_action": "none|warn|delete|mute|restrict|kick|ban",
    "should_escalate_to_admin": "boolean",
}


def build_system_prompt() -> str:
    return (
        "You are a Telegram moderation classifier. Output JSON only. "
        "Classify by policy and keep false positive rate low."
    )


def build_user_prompt(message: MessageRef, context: ModerationContext, redacted_text: str) -> str:
    return (
        f"chat_mode={context.settings.mode}\n"
        f"language={context.settings.language}\n"
        f"strike_score={context.strike_score}\n"
        f"schema={SCHEMA_DOC}\n"
        f"message={redacted_text}\n"
        f"meta={message.meta}\n"
    )


def build_welcome_system_prompt() -> str:
    return (
        "You are a Telegram community assistant. "
        "Write short, warm, safe welcome messages without markdown or emoji spam."
    )


def build_welcome_user_prompt(chat_title: str, user_display_name: str, language: str, template: str) -> str:
    return (
        f"language={language}\n"
        f"chat_title={chat_title}\n"
        f"user_display_name={user_display_name}\n"
        f"template_hint={template}\n"
        "requirements=<=60 Chinese chars, include user_display_name once, remind reading group rules politely\n"
    )
