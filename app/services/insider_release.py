"""Send due Insider issues and expire finished promos."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.email_service import EmailDeliveryError, send_insider_issue_email
from app.services.promo_codes import PromoCodeError, validate_promo_row

from app.api import supabase_repository as db

logger = logging.getLogger(__name__)


def expire_finished_promos() -> int:
    return db.expire_promo_codes()


def release_due_insider_issues() -> Dict[str, Any]:
    due = db.list_due_insider_issues()
    if not due:
        return {"sent": 0, "failed": 0, "issues": []}

    sent_issues = 0
    failed_issues = 0
    results: List[Dict[str, Any]] = []

    for issue in due:
        slug = issue["slug"]
        audience = str(issue.get("audience") or "all").strip().lower() or "all"
        subscribers = db.list_newsletter_subscribers(
            active_only=True,
            audience=audience,
        )
        if not subscribers:
            logger.warning(
                "Insider release deferred for %s — no subscribers for audience=%s",
                slug,
                audience,
            )
            # Keep scheduled so later cron retries when the pilgrimage list grows.
            results.append(
                {
                    "slug": slug,
                    "status": "deferred",
                    "reason": "no_subscribers",
                    "audience": audience,
                }
            )
            continue

        db.mark_insider_issue_status(slug, "sending")
        promo_row = None
        promo_code = issue.get("promo_code")
        if promo_code:
            promo_row = db.get_promo_code(str(promo_code))

        promo_percent = promo_row.get("percent_off") if promo_row else None
        promo_ends = None
        if promo_row:
            try:
                promo_ends = validate_promo_row(promo_row, subtotal_cents=1000).ends_at
            except PromoCodeError:
                promo_ends = str(promo_row.get("ends_at") or "")

        issue_failures = 0
        for email in subscribers:
            try:
                send_insider_issue_email(
                    to_email=email,
                    subject=str(issue.get("subject") or "NoorLink Insider"),
                    preview=str(issue.get("preview") or ""),
                    hero_image_url=str(issue.get("hero_image_url") or ""),
                    web_path=str(issue.get("web_path") or f"/newsletter/{slug}"),
                    promo_code=str(promo_code) if promo_code else None,
                    promo_percent=int(promo_percent) if promo_percent else None,
                    promo_ends=promo_ends,
                    email_highlight=(
                        str(issue["email_highlight"])
                        if issue.get("email_highlight")
                        else None
                    ),
                    email_highlight_ref=(
                        str(issue["email_highlight_ref"])
                        if issue.get("email_highlight_ref")
                        else None
                    ),
                    email_note=(
                        str(issue["email_note"]) if issue.get("email_note") else None
                    ),
                    email_giving_note=(
                        str(issue["email_giving_note"])
                        if issue.get("email_giving_note")
                        else None
                    ),
                )
            except EmailDeliveryError as exc:
                issue_failures += 1
                logger.error("Insider send failed for %s → %s: %s", slug, email, exc)

        if issue_failures == len(subscribers):
            failed_issues += 1
            db.mark_insider_issue_status(
                slug,
                "failed",
                error=f"All {issue_failures} sends failed",
            )
            results.append({"slug": slug, "status": "failed", "audience": audience})
            continue

        sent_issues += 1
        db.mark_insider_issue_status(slug, "sent")
        results.append(
            {
                "slug": slug,
                "status": "sent",
                "audience": audience,
                "recipients": len(subscribers) - issue_failures,
                "failed": issue_failures,
            }
        )

    return {"sent": sent_issues, "failed": failed_issues, "issues": results}
