"""Phone-friendly emergency desk — playbook guidance for critical site issues."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.admin.roles import ROLE_ADMIN, ROLE_OWNER, ROLE_SUPPORT
from app.services.admin_help_playbooks import PLAYBOOKS, HelpPlaybook
from app.services.critical_ops import list_critical_events


EMERGENCY_QUICK_ACTIONS: Tuple[Dict[str, str], ...] = (
    {
        "key": "fulfill",
        "title": "Customer paid, no eSIM",
        "detail": "Run Fulfill stuck order — most common emergency.",
        "path": "/admin/fulfill-order",
    },
    {
        "key": "critical-logs",
        "title": "Live critical logs",
        "detail": "Stream of checkout, fulfillment, and security failures.",
        "path": "/admin/event-log?severity=critical",
    },
    {
        "key": "support",
        "title": "Support inbox",
        "detail": "Reply to waiting customers.",
        "path": "/admin/support-inbox",
    },
    {
        "key": "order",
        "title": "Look up an order",
        "detail": "Gift, reminders, breakage, status in one place.",
        "path": "/admin/order-insight",
    },
    {
        "key": "operations",
        "title": "Operations health",
        "detail": "Suspended orders, cron, security checklist.",
        "path": "/admin/operations",
    },
    {
        "key": "notifications",
        "title": "Do next / notifications",
        "detail": "Your urgent queue for today.",
        "path": "/admin/home",
    },
)


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def match_emergency_playbooks(*, question: str, role: str, limit: int = 3) -> List[HelpPlaybook]:
    tokens = _tokenize(question)
    if not tokens:
        return []

    emergency_tokens = {
        "checkout",
        "payment",
        "stripe",
        "fail",
        "failed",
        "failing",
        "fulfill",
        "fulfillment",
        "esim",
        "qr",
        "stuck",
        "paid",
        "webhook",
        "security",
        "login",
        "refund",
        "down",
        "broken",
        "error",
        "critical",
    }
    is_site_emergency = bool(tokens & emergency_tokens)

    scored: List[Tuple[int, HelpPlaybook]] = []
    for playbook in PLAYBOOKS:
        if playbook.roles and role not in playbook.roles and role not in (ROLE_ADMIN, ROLE_OWNER):
            if role == ROLE_SUPPORT and playbook.area not in ("support", "getting-started", "admin"):
                continue
        hay = _tokenize(
            " ".join(
                [
                    playbook.title,
                    playbook.problem,
                    " ".join(playbook.tags),
                    " ".join(playbook.steps),
                    playbook.area,
                ]
            )
        )
        score = len(tokens & hay)
        if {"checkout", "payment", "stripe", "fail", "failed", "failing"} & tokens:
            if {"webhook", "fulfill", "fulfillment", "stripe", "event", "log"} & hay:
                score += 4
            if playbook.area == "catalog":
                score -= 3
        if {"fulfill", "esim", "qr", "stuck", "paid"} & tokens and {
            "fulfill",
            "esim",
            "qr",
            "stuck",
            "paid",
        } & hay:
            score += 4
        if {"security", "login"} & tokens and {"security", "login"} & hay:
            score += 3
        if {"refund"} & tokens and {"refund"} & hay:
            score += 3
        if is_site_emergency and playbook.area in ("support", "admin"):
            score += 1
        if score > 0:
            scored.append((score, playbook))

    scored.sort(key=lambda item: (-item[0], item[1].title))
    return [p for score, p in scored[:limit] if score > 0]


def emergency_assist(*, question: str, role: str = ROLE_ADMIN) -> Dict[str, Any]:
    """Return guided steps for an emergency question (no external LLM required)."""
    q = (question or "").strip()
    tokens = _tokenize(q)
    recent = list_critical_events(limit=5)
    playbooks = match_emergency_playbooks(question=q, role=role)

    # Hard-coded high-confidence emergencies (phone-first)
    if {"checkout", "payment", "stripe"} & tokens and {
        "fail",
        "failed",
        "failing",
        "down",
        "broken",
        "error",
    } & tokens:
        answer = (
            "Likely issue: Checkout / payment start is failing.\n"
            "Customers cannot reach Stripe or PayPal.\n"
            "Do this now:\n"
            "1. Open Critical logs and filter checkout_failed / payment_intent_failed\n"
            "2. Check Stripe Dashboard → Developers → Logs for declined API keys or mode mismatch\n"
            "3. Confirm Railway env has live STRIPE_SECRET_KEY and APP_URL\n"
            "4. Retry a $test checkout yourself on noorlink.co/checkout\n"
            "5. If orders were created but unpaid, customers can retry — if paid with no QR, use Fulfill stuck order\n"
            "Open tool: /admin/event-log?severity=critical"
        )
        return {
            "answer": answer,
            "playbooks": [
                {
                    "id": "checkout-down",
                    "title": "Checkout failing",
                    "problem": "Payment session cannot start",
                    "steps": [
                        "Open Critical logs",
                        "Check Stripe logs / API keys",
                        "Retry a test checkout",
                        "Fulfill any paid-no-QR orders",
                    ],
                    "wizard_path": "/admin/event-log?severity=critical",
                }
            ],
            "recent_critical": recent,
            "quick_actions": list(EMERGENCY_QUICK_ACTIONS),
        }

    if {"paid", "pay"} & tokens and {"qr", "esim", "email", "fulfill", "stuck"} & tokens:
        preferred = [p for p in playbooks if "fulfill" in p.id or "qr" in " ".join(p.tags)]
        playbooks = preferred + [p for p in playbooks if p not in preferred]

    if {"checkout", "payment", "stripe", "fail", "failed", "failing"} & tokens:
        preferred = [
            p
            for p in playbooks
            if p.area in ("support", "admin")
            or any(t in p.tags for t in ("webhook", "fulfill", "stripe", "event"))
        ]
        if preferred:
            playbooks = preferred + [p for p in playbooks if p not in preferred]

    if not playbooks:
        return {
            "answer": (
                "I couldn’t match a playbook. Open Critical logs for the latest failure, "
                "then Fulfill stuck order if someone paid without an eSIM. "
                "You can also search Help for the topic."
            ),
            "playbooks": [],
            "recent_critical": recent,
            "quick_actions": list(EMERGENCY_QUICK_ACTIONS),
        }

    top = playbooks[0]
    answer_lines = [
        f"Likely issue: {top.title}.",
        top.problem,
        "Do this now:",
    ]
    for i, step in enumerate(top.steps, start=1):
        answer_lines.append(f"{i}. {step}")
    answer_lines.append(f"Open tool: {top.wizard_path}")
    if recent:
        answer_lines.append("")
        answer_lines.append(
            f"Latest critical signal: {recent[0].get('event_type')} — {recent[0].get('message')}"
        )

    return {
        "answer": "\n".join(answer_lines),
        "playbooks": [
            {
                "id": p.id,
                "title": p.title,
                "problem": p.problem,
                "steps": list(p.steps),
                "wizard_path": p.wizard_path,
            }
            for p in playbooks
        ],
        "recent_critical": recent,
        "quick_actions": list(EMERGENCY_QUICK_ACTIONS),
    }


def emergency_desk_context(*, role: str) -> Dict[str, Any]:
    return {
        "quick_actions": list(EMERGENCY_QUICK_ACTIONS),
        "recent_critical": list_critical_events(limit=15),
        "starter_prompts": [
            "Checkout is failing for customers",
            "Customer paid but no QR email",
            "Stripe webhook or fulfillment error",
            "Security login alerts",
            "Refund a customer who already used data",
        ],
        "role": role,
    }
