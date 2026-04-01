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
        "Write short, warm, safe welcome messages without markdown or emoji spam. "
        "Use the template as a style/content hint, but do not copy it verbatim unless absolutely necessary."
    )


def build_verification_question_system_prompt() -> str:
    return (
        "You generate Telegram join verification quiz questions. "
        "Output JSON only. Questions must be short, clear, safe, and easy for normal humans in the target group to answer. "
        "Avoid external trivia, avoid ambiguous wording, and ensure each question has exactly one correct answer."
    )


def build_welcome_user_prompt(
    chat_title: str,
    user_display_name: str,
    language: str,
    template: str,
    *,
    time_of_day: str | None = None,
    chat_type: str | None = None,
) -> str:
    extra = ""
    if time_of_day:
        extra += f"time_of_day={time_of_day}\n"
    if chat_type:
        extra += f"chat_type={chat_type}\n"
    return (
        f"language={language}\n"
        f"chat_title={chat_title}\n"
        f"user_display_name={user_display_name}\n"
        f"template_hint={template}\n"
        f"{extra}"
        "template_rule=follow the template's intent and key points, but rewrite naturally instead of copying it word for word\n"
        "requirements=<=60 Chinese chars, include user_display_name once, remind reading group rules politely\n"
    )


def build_verification_question_user_prompt(
    *,
    chat_title: str,
    language: str,
    count: int,
    topic_hint: str | None = None,
    chat_type: str | None = None,
) -> str:
    extra = ""
    if chat_type:
        extra += f"chat_type={chat_type}\n"
    if topic_hint:
        extra += f"topic_hint={topic_hint.strip()}\n"
    return (
        f"language={language}\n"
        f"chat_title={chat_title}\n"
        f"count={count}\n"
        f"{extra}"
        "schema=questions:[{question:string,options:[string],answer_index:integer}]\n"
        "requirements=each question in Chinese, each question <=30 Chinese chars, 2..4 options, exactly one correct answer, "
        "options should be concise, avoid all-of-the-above/none-of-the-above, avoid sensitive content, "
        "fit a normal Telegram community onboarding quiz\n"
    )
