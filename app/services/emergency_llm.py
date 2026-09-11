"""Optional OpenAI-compatible LLM for Emergency help free-form answers."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are NoorLink Emergency Desk — a calm travel-ops assistant for staff on their phone.

Brand voice: practical, trustworthy, no hype. Short sentences.

You help with site emergencies: checkout failures, paid-but-no-eSIM, Stripe/PayPal, fulfillment, support tickets, refunds, security alerts, promos, catalog.

Rules:
- Give concrete next steps staff can do in the NoorLink admin dashboard.
- Prefer these paths when relevant:
  /admin/event-log?severity=critical
  /admin/emergency
  /admin/fulfill-order
  /admin/order-insight
  /admin/support-inbox
  /admin/operations
  /admin/home
  /admin/refund-order
- If recent critical events are provided, use them.
- If playbooks are provided, follow them unless the question clearly needs something else.
- Never invent secret keys, customer PII, or claim you changed production.
- Never suggest destructive DB edits.
- Keep answers under 220 words. Use a numbered list for actions.
- End with one "Open tool:" line pointing to the best admin URL.
"""


def llm_configured() -> bool:
    return get_settings().emergency_llm_enabled


def _build_user_prompt(
    *,
    question: str,
    role: str,
    recent_critical: List[Dict[str, Any]],
    playbooks: List[Dict[str, Any]],
) -> str:
    lines = [
        f"Staff role: {role}",
        f"Question: {question.strip()}",
        "",
        "Recent critical events:",
    ]
    if recent_critical:
        for row in recent_critical[:5]:
            lines.append(
                f"- [{row.get('severity')}] {row.get('event_type')}: {row.get('message')}"
                + (f" (order {row.get('order_number')})" if row.get("order_number") else "")
            )
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("Matched playbooks:")
    if playbooks:
        for pb in playbooks[:3]:
            steps = "; ".join(pb.get("steps") or [])
            lines.append(
                f"- {pb.get('title')}: {pb.get('problem')} | steps: {steps} | tool: {pb.get('wizard_path')}"
            )
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("Answer with clear phone-friendly steps.")
    return "\n".join(lines)


def generate_emergency_llm_answer(
    *,
    question: str,
    role: str,
    recent_critical: Optional[List[Dict[str, Any]]] = None,
    playbooks: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """
    Call OpenAI-compatible chat completions.
    Returns answer text, or None if disabled / failed (caller should fall back).
    """
    settings = get_settings()
    api_key = (settings.emergency_llm_api_key or "").strip()
    if not api_key:
        return None

    base = (settings.emergency_llm_base_url or "https://api.openai.com/v1").rstrip("/")
    model = (settings.emergency_llm_model or "gpt-4o-mini").strip()
    timeout = float(settings.emergency_llm_timeout_seconds or 25.0)
    url = f"{base}/chat/completions"

    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 500,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_prompt(
                    question=question,
                    role=role,
                    recent_critical=list(recent_critical or []),
                    playbooks=list(playbooks or []),
                ),
            },
        ],
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        choices = data.get("choices") or []
        if not choices:
            logger.warning("Emergency LLM returned no choices")
            return None
        message = (choices[0].get("message") or {}).get("content") or ""
        text = str(message).strip()
        return text or None
    except Exception as exc:
        logger.warning("Emergency LLM call failed: %s", exc)
        return None
