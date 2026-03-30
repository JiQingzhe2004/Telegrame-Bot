from __future__ import annotations

import re

PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s]{6,}\d)(?!\d)")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def redact_pii(text: str, max_len: int = 2000) -> str:
    short = text[:max_len]
    short = PHONE_RE.sub("[PHONE]", short)
    short = EMAIL_RE.sub("[EMAIL]", short)
    return short
