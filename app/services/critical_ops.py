"""Critical site events — persist, alert, and list for the live dashboard stream."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.ops_alerts import notify_critical_ops
from app.services.ops_event_log import list_ops_events, log_ops_event

logger = logging.getLogger(__name__)

CRITICAL_SEVERITIES = frozenset({"critical", "error"})
CRITICAL_EVENT_TYPES = frozenset(
    {
        "checkout_failed",
        "checkout_order_failed",
        "fulfillment_failed",
        "payment_intent_failed",
        "topup_checkout_failed",
    }
)

_ALERT_COOLDOWN_SEC = 15 * 60
_recent_alerts: Dict[str, float] = {}


def _alert_allowed(key: str) -> bool:
    now = time.time()
    stale = [k for k, ts in _recent_alerts.items() if now - ts > _ALERT_COOLDOWN_SEC]
    for k in stale:
        _recent_alerts.pop(k, None)
    last = _recent_alerts.get(key)
    if last is not None and now - last < _ALERT_COOLDOWN_SEC:
        return False
    _recent_alerts[key] = now
    return True


def report_critical_event(
    *,
    event_type: str,
    source: str,
    message: str,
    order_number: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    notify: bool = True,
    title: Optional[str] = None,
) -> None:
    """Write a critical ops log row and (rate-limited) email/Slack the ops channel."""
    try:
        log_ops_event(
            event_type=event_type,
            source=source,
            message=message,
            severity="critical",
            order_number=order_number,
            details=details,
        )
    except Exception as exc:
        logger.warning("critical ops log failed: %s", exc)

    if not notify:
        return

    alert_key = f"{event_type}|{(message or '')[:120]}"
    if not _alert_allowed(alert_key):
        logger.info("Critical alert suppressed (cooldown): %s", alert_key)
        return

    notify_critical_ops(
        title=title or f"Critical: {event_type.replace('_', ' ')}",
        summary=message,
        event_type=event_type,
        order_number=order_number,
        details=details,
    )


def is_critical_row(row: Dict[str, Any]) -> bool:
    severity = str(row.get("severity") or "").lower()
    event_type = str(row.get("event_type") or "")
    if severity in CRITICAL_SEVERITIES:
        return True
    return event_type in CRITICAL_EVENT_TYPES or event_type.startswith("security_")


def _parse_created_at(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def list_critical_events(
    *,
    limit: int = 50,
    within_hours: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Recent critical/error events for the live stream (newest first)."""
    rows = list_ops_events(limit=max(limit * 3, 100))
    critical = [row for row in rows if is_critical_row(row)]
    if within_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
        filtered: List[Dict[str, Any]] = []
        for row in critical:
            created = _parse_created_at(row.get("created_at"))
            if created is None or created >= cutoff:
                filtered.append(row)
        critical = filtered
    return critical[:limit]


def critical_event_count(*, within_hours: int = 24, limit_scan: int = 100) -> int:
    return len(list_critical_events(limit=limit_scan, within_hours=within_hours))
