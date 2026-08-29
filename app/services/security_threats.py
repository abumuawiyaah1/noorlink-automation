"""Track and summarize external security signals for the admin dashboard."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.ops_event_log import list_ops_events, log_ops_event

SECURITY_EVENT_PREFIX = "security_"

LOGIN_ALERT_THRESHOLD = 5
LOGIN_ALERT_WINDOW_MINUTES = 60
LOGIN_ALERT_COOLDOWN_MINUTES = 60


def log_security_event(
    *,
    threat_type: str,
    source: str,
    message: str,
    severity: str = "warning",
    ip_address: Optional[str] = None,
    order_number: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Best-effort security signal — stored in ops_event_log for admin review."""
    payload = dict(details or {})
    if ip_address:
        payload["ip"] = ip_address.strip()
    log_ops_event(
        event_type=f"{SECURITY_EVENT_PREFIX}{threat_type}",
        source=source,
        severity=severity,
        order_number=order_number,
        message=message[:500],
        details=payload,
    )
    if threat_type == "admin_login_failed" and ip_address:
        maybe_alert_repeated_admin_login(ip_address=ip_address.strip(), username=payload.get("username"))


def _events_since(events: List[Dict[str, Any]], *, minutes: int) -> List[Dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    filtered: List[Dict[str, Any]] = []
    for row in events:
        created = _parse_created_at(row.get("created_at"))
        if created is None or created >= since:
            filtered.append(row)
    return filtered


def _login_failures_for_ip(*, ip_address: str, minutes: int) -> int:
    events = list_ops_events(limit=200, event_type=f"{SECURITY_EVENT_PREFIX}admin_login_failed")
    count = 0
    for row in _events_since(events, minutes=minutes):
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        if str(details.get("ip") or "").strip() == ip_address:
            count += 1
    return count


def _login_alert_sent_recently(*, ip_address: str, minutes: int) -> bool:
    events = list_ops_events(limit=50, event_type=f"{SECURITY_EVENT_PREFIX}login_alert_sent")
    for row in _events_since(events, minutes=minutes):
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        if str(details.get("ip") or "").strip() == ip_address:
            return True
    return False


def maybe_alert_repeated_admin_login(*, ip_address: str, username: Optional[str] = None) -> None:
    """Email/Slack ops when one IP hits repeated failed admin logins."""
    if not ip_address:
        return

    failures = _login_failures_for_ip(
        ip_address=ip_address,
        minutes=LOGIN_ALERT_WINDOW_MINUTES,
    )
    if failures < LOGIN_ALERT_THRESHOLD:
        return
    if _login_alert_sent_recently(ip_address=ip_address, minutes=LOGIN_ALERT_COOLDOWN_MINUTES):
        return

    from app.services.ops_alerts import notify_security_threat

    notify_security_threat(
        title="Repeated failed admin login attempts",
        summary=(
            f"{failures} failed admin login(s) from the same IP in the last "
            f"{LOGIN_ALERT_WINDOW_MINUTES} minutes. Consider blocking the IP in Cloudflare."
        ),
        details={
            "ip": ip_address,
            "failures": failures,
            "username_tried": username or "unknown",
            "window_minutes": LOGIN_ALERT_WINDOW_MINUTES,
        },
    )
    log_ops_event(
        event_type=f"{SECURITY_EVENT_PREFIX}login_alert_sent",
        source="security_alerts",
        severity="warning",
        message=f"Ops alerted for {failures} failed logins from {ip_address}",
        details={"ip": ip_address, "failures": failures},
    )


def _parse_created_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def security_threats_summary(*, hours: int = 24) -> Dict[str, Any]:
    """Recent external-facing security signals from ops_event_log."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    raw_events = list_ops_events(limit=300, event_type_prefix=SECURITY_EVENT_PREFIX)

    recent: List[Dict[str, Any]] = []
    by_type: Counter[str] = Counter()
    by_ip: Counter[str] = Counter()
    login_fail_ips: Counter[str] = Counter()
    urgent_count = 0

    for row in raw_events:
        created = _parse_created_at(row.get("created_at"))
        if created and created < since:
            continue

        event_type = str(row.get("event_type") or "")
        short_type = event_type.removeprefix(SECURITY_EVENT_PREFIX) or event_type
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        ip = str(details.get("ip") or "").strip()

        by_type[short_type] += 1
        if ip:
            by_ip[ip] += 1
            if short_type == "admin_login_failed":
                login_fail_ips[ip] += 1

        severity = str(row.get("severity") or "info")
        if severity in {"warning", "error"}:
            urgent_count += 1

        recent.append(
            {
                "at": row.get("created_at"),
                "type": short_type,
                "severity": severity,
                "message": row.get("message"),
                "source": row.get("source"),
                "ip": ip or None,
                "order_number": row.get("order_number"),
            }
        )

    top_ips = [{"ip": ip, "count": count} for ip, count in by_ip.most_common(5)]
    repeated_login_ips = [
        {"ip": ip, "count": count} for ip, count in login_fail_ips.most_common(5) if count >= 3
    ]

    return {
        "hours": hours,
        "total": len(recent),
        "urgent_count": urgent_count,
        "by_type": dict(by_type),
        "top_ips": top_ips,
        "repeated_login_ips": repeated_login_ips,
        "recent": recent[:20],
        "needs_attention": urgent_count > 0 or bool(repeated_login_ips),
    }


def notification_security_count(*, hours: int = 24) -> int:
    summary = security_threats_summary(hours=hours)
    if summary.get("needs_attention"):
        return int(summary.get("urgent_count") or 0)
    return 0
