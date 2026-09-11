"""Tests for optional Emergency help LLM."""

from unittest.mock import MagicMock, patch

from app.services.emergency_assist import emergency_assist, emergency_desk_context
from app.services.emergency_llm import generate_emergency_llm_answer


@patch("app.services.emergency_llm.get_settings")
def test_generate_emergency_llm_answer_disabled(mock_settings):
    mock_settings.return_value = MagicMock(emergency_llm_api_key="")
    assert generate_emergency_llm_answer(question="checkout failing", role="admin") is None


@patch("app.services.emergency_llm.httpx.Client")
@patch("app.services.emergency_llm.get_settings")
def test_generate_emergency_llm_answer_success(mock_settings, mock_client_cls):
    mock_settings.return_value = MagicMock(
        emergency_llm_api_key="sk-test",
        emergency_llm_base_url="https://api.openai.com/v1",
        emergency_llm_model="gpt-4o-mini",
        emergency_llm_timeout_seconds=10.0,
    )
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "1. Open Critical logs\nOpen tool: /admin/event-log"}}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.post.return_value = mock_response

    text = generate_emergency_llm_answer(
        question="Checkout is failing",
        role="admin",
        recent_critical=[{"severity": "critical", "event_type": "checkout_failed", "message": "Stripe 502"}],
        playbooks=[],
    )
    assert "Critical logs" in (text or "")
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0].endswith("/chat/completions")
    assert kwargs["headers"]["Authorization"] == "Bearer sk-test"


@patch("app.services.emergency_assist.generate_emergency_llm_answer")
@patch("app.services.emergency_assist.list_critical_events", return_value=[])
@patch("app.services.emergency_assist.llm_configured", return_value=True)
def test_emergency_assist_uses_llm_when_available(_llm_on, _events, mock_gen):
    mock_gen.return_value = "AI says check Stripe keys.\nOpen tool: /admin/event-log?severity=critical"
    result = emergency_assist(question="Checkout is failing for customers", role="admin")
    assert result["source"] == "llm"
    assert result["answer"].startswith("AI says")
    assert result["llm_enabled"] is True


@patch("app.services.emergency_assist.generate_emergency_llm_answer", return_value=None)
@patch("app.services.emergency_assist.list_critical_events", return_value=[])
@patch("app.services.emergency_assist.llm_configured", return_value=False)
def test_emergency_assist_falls_back_to_playbook(_llm_off, _events, _gen):
    result = emergency_assist(question="Checkout is failing for customers", role="admin")
    assert result["source"] == "playbook"
    assert "Checkout" in result["answer"] or "checkout" in result["answer"].lower()


@patch("app.services.emergency_assist.llm_configured", return_value=True)
@patch("app.services.emergency_assist.list_critical_events", return_value=[])
def test_emergency_desk_context_shows_ai_mode(_events, _llm_on):
    ctx = emergency_desk_context(role="admin")
    assert ctx["llm_enabled"] is True
    assert "AI" in ctx["assist_mode"]
