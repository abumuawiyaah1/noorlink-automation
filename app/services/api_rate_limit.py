"""Simple in-memory rate limiting for public customer APIs."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from time import time
from typing import Dict, List, Tuple

_buckets: Dict[str, List[float]] = defaultdict(list)
_lock = Lock()


def check_rate_limit(
    key: str,
    *,
    max_calls: int,
    window_seconds: int,
) -> Tuple[bool, int]:
    """
    Return (allowed, retry_after_seconds).
    Uses a sliding window per key (typically IP or IP+email).
    """
    now = time()
    cutoff = now - window_seconds
    with _lock:
        hits = [stamp for stamp in _buckets[key] if stamp > cutoff]
        if len(hits) >= max_calls:
            retry_after = max(1, int(window_seconds - (now - hits[0])) + 1)
            _buckets[key] = hits
            return False, retry_after
        hits.append(now)
        _buckets[key] = hits
        return True, 0


def reset_rate_limit_for_tests() -> None:
    """Clear buckets — test helper only."""
    with _lock:
        _buckets.clear()
