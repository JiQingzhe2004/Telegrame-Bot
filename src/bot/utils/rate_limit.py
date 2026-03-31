from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class BurstCheckResult:
    hit: bool
    count: int
    window_seconds: int


class UserMessageWindow:
    def __init__(self) -> None:
        self._events: dict[tuple[int, int], deque[datetime]] = defaultdict(deque)

    def record_and_check(
        self,
        chat_id: int,
        user_id: int,
        now: datetime,
        threshold: int = 5,
        window_seconds: int = 15,
    ) -> BurstCheckResult:
        key = (chat_id, user_id)
        q = self._events[key]
        q.append(now)
        cutoff = now - timedelta(seconds=window_seconds)
        while q and q[0] < cutoff:
            q.popleft()
        return BurstCheckResult(hit=len(q) >= threshold, count=len(q), window_seconds=window_seconds)


import difflib
import re


@dataclass
class RaidCheckResult:
    hit: bool
    join_count: int
    window_seconds: int
    trigger_type: str  # 'join_surge' | 'similar_nickname' | 'none'
    similar_names: list[str] | None = None


class RaidDetector:
    """检测短时入群激增（join_surge）和相似昵称批量入群（similar_nickname）"""

    def __init__(self) -> None:
        # chat_id -> deque of (datetime, display_name)
        self._join_events: dict[int, deque[tuple[datetime, str]]] = defaultdict(deque)

    def record_and_check(
        self,
        chat_id: int,
        display_name: str,
        now: datetime,
        surge_threshold: int = 5,
        surge_window_seconds: int = 60,
        similarity_threshold: float = 0.75,
    ) -> RaidCheckResult:
        q = self._join_events[chat_id]
        q.append((now, display_name))
        cutoff = now - timedelta(seconds=surge_window_seconds)
        while q and q[0][0] < cutoff:
            q.popleft()

        recent_names = [n for _, n in q]
        join_count = len(recent_names)

        # 检测短时入群激增
        if join_count >= surge_threshold:
            return RaidCheckResult(
                hit=True,
                join_count=join_count,
                window_seconds=surge_window_seconds,
                trigger_type="join_surge",
            )

        # 检测相似昵称（≥3人且两两相似度超阈值）
        if join_count >= 3:
            similar = _find_similar_names(recent_names, threshold=similarity_threshold)
            if len(similar) >= 3:
                return RaidCheckResult(
                    hit=True,
                    join_count=join_count,
                    window_seconds=surge_window_seconds,
                    trigger_type="similar_nickname",
                    similar_names=similar,
                )

        return RaidCheckResult(hit=False, join_count=join_count, window_seconds=surge_window_seconds, trigger_type="none")


def _normalize_name(name: str) -> str:
    """去除数字尾缀和常见前后缀以提升相似度检测准确性"""
    return re.sub(r"[\d_\-\.]+$", "", name.strip().lower())


def _find_similar_names(names: list[str], threshold: float = 0.75) -> list[str]:
    """返回彼此相似的昵称列表（去重）"""
    normalized = [_normalize_name(n) for n in names]
    similar_set: set[int] = set()
    for i in range(len(normalized)):
        for j in range(i + 1, len(normalized)):
            if not normalized[i] or not normalized[j]:
                continue
            ratio = difflib.SequenceMatcher(None, normalized[i], normalized[j]).ratio()
            if ratio >= threshold:
                similar_set.add(i)
                similar_set.add(j)
    return [names[i] for i in sorted(similar_set)]
