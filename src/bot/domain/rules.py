from __future__ import annotations

import re
from collections import Counter

from bot.domain.models import MessageRef, ModerationContext, Rule, RuleResult

SHORTENER_HOSTS = ("bit.ly", "t.co", "tinyurl.com", "goo.gl")
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


class BanwordRule(Rule):
    name = "banword"

    def evaluate(self, message: MessageRef, context: ModerationContext) -> RuleResult:
        text = (message.text or "").lower()
        if not text or not context.blacklist_words:
            return RuleResult(hit=False, level=0, codes=[], details={})
        hits = [w for w in context.blacklist_words if w.lower() in text]
        if not hits:
            return RuleResult(hit=False, level=0, codes=[], details={})
        level = 2 if len(hits) >= 2 else 1
        return RuleResult(hit=True, level=level, codes=["rule.banword"], details={"hits": hits})


class SuspiciousLinkRule(Rule):
    name = "suspicious_link"

    def evaluate(self, message: MessageRef, context: ModerationContext) -> RuleResult:
        text = message.text or ""
        links = URL_RE.findall(text)
        if not links:
            return RuleResult(hit=False, level=0, codes=[], details={})
        low = [x.lower() for x in links]
        shortener_hits = [x for x in low if any(host in x for host in SHORTENER_HOSTS)]
        many_links = len(links) >= 3
        if not shortener_hits and not many_links:
            return RuleResult(hit=False, level=0, codes=[], details={"link_count": len(links)})
        level = 2 if shortener_hits or len(links) >= 5 else 1
        return RuleResult(
            hit=True,
            level=level,
            codes=["rule.suspicious_link"],
            details={"link_count": len(links), "shortener_hits": shortener_hits},
        )


class FloodRule(Rule):
    name = "flood"

    def evaluate(self, message: MessageRef, context: ModerationContext) -> RuleResult:
        texts = [x for x in context.recent_message_texts if x]
        if len(texts) < 3:
            return RuleResult(hit=False, level=0, codes=[], details={"recent_count": len(texts)})
        c = Counter(t.strip().lower() for t in texts)
        repeated, top_count = c.most_common(1)[0]
        if top_count >= 3:
            return RuleResult(
                hit=True,
                level=2,
                codes=["rule.flood.repeat"],
                details={"repeat_text": repeated, "repeat_count": top_count},
            )
        if len(texts) >= 5:
            return RuleResult(
                hit=True,
                level=1,
                codes=["rule.flood.burst"],
                details={"recent_count": len(texts)},
            )
        return RuleResult(hit=False, level=0, codes=[], details={"recent_count": len(texts)})


def default_rules() -> list[Rule]:
    return [BanwordRule(), SuspiciousLinkRule(), FloodRule()]
