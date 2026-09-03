"""Monitor eSIM device catalog drift and failed customer device checks."""

from __future__ import annotations

import html
import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from app.services.admin_report_core import mark_report_sent, ny_now, report_already_sent
from app.services.admin_report_recipients import admin_report_recipient_emails
from app.services.email_service import EmailDeliveryError, send_email
from app.services.ops_alerts import notify_device_catalog_review
from app.services.ops_event_log import list_ops_events, log_ops_event

logger = logging.getLogger(__name__)

NY_TZ = ZoneInfo("America/New_York")
AUDIT_ACTION = "device_catalog_monitor_sent"
REFERENCE_PATH = Path(__file__).resolve().parents[2] / "data" / "esim_device_reference.json"
MISS_EVENT = "device_check_miss"
MISS_ALERT_THRESHOLD = 2


def _normalize_model(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _catalog_model_keys(catalog: List[Dict[str, Any]]) -> Set[Tuple[str, str]]:
    keys: Set[Tuple[str, str]] = set()
    for brand in catalog:
        brand_id = str(brand.get("id") or "").strip().lower()
        for model in brand.get("models") or []:
            model_name = _normalize_model(str(model.get("name") or ""))
            if brand_id and model_name:
                keys.add((brand_id, model_name))
    return keys


def load_reference_catalog() -> List[Dict[str, Any]]:
    if not REFERENCE_PATH.is_file():
        from app.api.devices import get_compatible_catalog

        logger.warning("Device reference file missing at %s — using live catalog", REFERENCE_PATH)
        return get_compatible_catalog()
    payload = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    brands = payload.get("brands")
    if not isinstance(brands, list):
        raise ValueError("Invalid device reference file: missing brands array")
    return brands


def load_live_catalog() -> List[Dict[str, Any]]:
    from app.api.devices import get_compatible_catalog

    return get_compatible_catalog()


def diff_device_catalogs() -> Dict[str, List[str]]:
    """Return human-readable model names missing from live or reference catalogs."""
    reference = _catalog_model_keys(load_reference_catalog())
    live = _catalog_model_keys(load_live_catalog())

    ref_by_key = {}
    for brand in load_reference_catalog():
        for model in brand.get("models") or []:
            key = (str(brand.get("id") or "").lower(), _normalize_model(str(model.get("name") or "")))
            ref_by_key[key] = str(model.get("name") or "")

    live_by_key = {}
    for brand in load_live_catalog():
        for model in brand.get("models") or []:
            key = (str(brand.get("id") or "").lower(), _normalize_model(str(model.get("name") or "")))
            live_by_key[key] = str(model.get("name") or "")

    missing_from_live = sorted(ref_by_key[name] for name in sorted(reference - live))
    missing_from_reference = sorted(live_by_key[name] for name in sorted(live - reference))
    return {
        "missing_from_live": missing_from_live,
        "missing_from_reference": missing_from_reference,
    }


def record_device_check_miss(query: str, *, source: str = "site") -> None:
    normalized = _normalize_model(query)
    if len(normalized) < 2:
        return
    log_ops_event(
        event_type=MISS_EVENT,
        source=source,
        severity="info",
        message=query.strip()[:120],
        details={"normalized": normalized},
    )


def get_top_device_check_misses(*, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = list_ops_events(limit=500, event_type=MISS_EVENT)
    counts: Counter[str] = Counter()
    for row in rows:
        created_at = row.get("created_at")
        if created_at:
            try:
                ts = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                if ts < since:
                    continue
            except ValueError:
                pass
        message = str(row.get("message") or "").strip()
        if message:
            counts[message] += 1
    return [{"query": query, "count": count} for query, count in counts.most_common(limit)]


def _week_record_id(now_utc: Optional[datetime] = None) -> str:
    local = ny_now(now_utc)
    year, week, _ = local.isocalendar()
    return f"{year}-W{week:02d}"


def should_send_weekly_device_alert(now_utc: Optional[datetime] = None) -> bool:
    return ny_now(now_utc).weekday() == 0


def _build_alert_html(
    *,
    diff: Dict[str, List[str]],
    misses: List[Dict[str, Any]],
) -> str:
    lines = [
        "<h2>eSIM device catalog review</h2>",
        "<p>Additions in the reference list that are not live yet:</p>",
    ]
    if diff["missing_from_live"]:
        lines.append("<ul>")
        lines.extend(f"<li>{html.escape(name)}</li>" for name in diff["missing_from_live"])
        lines.append("</ul>")
        lines.append(
            "<p>Update <code>app/api/devices.py</code> and redeploy, "
            "or trim the reference file if the model is not eSIM-capable.</p>"
        )
    else:
        lines.append("<p>None — live catalog matches the reference list.</p>")

    lines.append("<h3>Customer searches we could not match (7 days)</h3>")
    hot_misses = [row for row in misses if int(row.get("count") or 0) >= MISS_ALERT_THRESHOLD]
    if hot_misses:
        lines.append("<ul>")
        for row in hot_misses:
            lines.append(
                f"<li>{html.escape(str(row['query']))} · {int(row['count'])} check(s)</li>"
            )
        lines.append("</ul>")
    elif misses:
        lines.append("<ul>")
        for row in misses[:5]:
            lines.append(
                f"<li>{html.escape(str(row['query']))} · {int(row['count'])} check(s)</li>"
            )
        lines.append("</ul>")
    else:
        lines.append("<p>No failed device checks logged this week.</p>")

    if diff["missing_from_reference"]:
        lines.append("<h3>Live-only models (add to reference file)</h3><ul>")
        lines.extend(f"<li>{html.escape(name)}</li>" for name in diff["missing_from_reference"][:10])
        lines.append("</ul>")

    lines.append(
        "<p>Reference file: <code>data/esim_device_reference.json</code> · "
        "Admin: <a href=\"https://api.noorlink.co/admin/system-diagnostics\">System diagnostics</a></p>"
    )
    return "\n".join(lines)


def run_device_catalog_monitor(*, force: bool = False, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    diff = diff_device_catalogs()
    misses = get_top_device_check_misses(days=7, limit=10)
    hot_misses = [row for row in misses if int(row.get("count") or 0) >= MISS_ALERT_THRESHOLD]

    needs_attention = bool(diff["missing_from_live"] or hot_misses)
    record_id = _week_record_id(now_utc)

    if not force and not should_send_weekly_device_alert(now_utc):
        return {
            "sent": 0,
            "skipped": "Weekly device catalog alert sends on Mondays (New York).",
            "needs_attention": needs_attention,
            "diff": diff,
            "misses": misses,
        }

    if not force and not needs_attention:
        return {
            "sent": 0,
            "skipped": "No catalog drift or repeated failed device checks.",
            "needs_attention": False,
            "diff": diff,
            "misses": misses,
        }

    if not force and report_already_sent(AUDIT_ACTION, record_id):
        return {
            "sent": 0,
            "skipped": f"Already sent for {record_id}.",
            "needs_attention": needs_attention,
            "diff": diff,
            "misses": misses,
        }

    subject_parts = []
    if diff["missing_from_live"]:
        subject_parts.append(f"{len(diff['missing_from_live'])} model(s) to add")
    if hot_misses:
        subject_parts.append(f"{len(hot_misses)} failed search(es)")
    subject = "[NoorLink] eSIM device catalog — " + (", ".join(subject_parts) or "weekly review")

    html_body = _build_alert_html(diff=diff, misses=misses)
    text_body = subject
    if diff["missing_from_live"]:
        text_body += "\nAdd to live catalog: " + ", ".join(diff["missing_from_live"][:5])
    if hot_misses:
        text_body += "\nFailed searches: " + ", ".join(
            f"{row['query']} ({row['count']})" for row in hot_misses[:5]
        )
    notify_device_catalog_review(subject=subject, html_body=html_body, text_body=text_body)

    recipients = admin_report_recipient_emails()
    sent = 0
    errors: List[str] = []
    for email in recipients:
        try:
            send_email(to_email=email, subject=subject, html_body=html_body)
            sent += 1
        except EmailDeliveryError as exc:
            errors.append(f"{email}: {exc}")

    if sent and not force:
        try:
            mark_report_sent(AUDIT_ACTION, record_id, recipient_count=sent)
        except Exception:
            logger.exception("Failed to record device catalog monitor send for %s", record_id)

    log_ops_event(
        event_type="device_catalog_monitor",
        source="cron",
        severity="warning" if needs_attention else "info",
        message=subject,
        details={
            "missing_from_live": diff["missing_from_live"],
            "hot_misses": hot_misses,
            "record_id": record_id,
        },
    )

    return {
        "sent": sent,
        "needs_attention": needs_attention,
        "diff": diff,
        "misses": misses,
        "record_id": record_id,
        "errors": errors,
    }


def device_catalog_notification_count() -> int:
    diff = diff_device_catalogs()
    misses = get_top_device_check_misses(days=7, limit=10)
    hot_misses = [row for row in misses if int(row.get("count") or 0) >= MISS_ALERT_THRESHOLD]
    return len(diff["missing_from_live"]) + len(hot_misses)
