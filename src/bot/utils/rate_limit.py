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
