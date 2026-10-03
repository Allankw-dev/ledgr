"""The real assistants over Gemini, against a real database: tools run for real and stay scoped."""

import json
from datetime import datetime, timezone

import httpx
import pytest

from app.core.config import settings
from app.models.enums import GuardianLinkStatus
from app.models.student import Student, StudentGuardian
from app.services import ai_assistant, llm, parent_assistant
from tests.conftest import needs_db

pytestmark = needs_db


@pytest.fixture(autouse=True)
def _gemini(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "gemini_model", "m")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "ai_provider", "auto")
    monkeypatch.setattr(llm, "_resolved_gemini_model", None)
    yield
    monkeypatch.setattr(llm, "_transport", None)


def _script(monkeypatch, tool_name, args=None):
    """Gemini asks for one tool, then 'answers' — and records what the tool returned."""
    seen = {}

    def handler(request):
        body = json.loads(request.content)
        last = body["contents"][-1]["parts"][0]
        if "functionResponse" in last:
            seen["tool_result"] = last["functionResponse"]["response"]
            return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [{"text": "Here you go."}]}}]})
        return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": tool_name, "args": args or {}}}]}}]})

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    return seen


def test_parent_assistant_runs_a_real_tool_and_only_sees_own_children(db, world, monkeypatch):
    other = Student(school_id=world.school.id, admission_number="2002", full_name="Someone Else's Child")
    db.add(other)
    db.add(StudentGuardian(student_id=world.student.id, user_id=world.parent.id, relationship_type="mother", status=GuardianLinkStatus.APPROVED))
    db.commit()
    seen = _script(monkeypatch, "get_children_overview")

    answer = parent_assistant.ask_parent_assistant(db, world.parent.id, [{"role": "user", "content": "how are we doing?"}])
    assert answer == "Here you go."
    dump = json.dumps(seen["tool_result"], default=str)
    assert "Kid One" in dump and "Someone Else" not in dump  # scoped to this parent's own linked child


def test_bursar_assistant_runs_a_real_tool(db, world, monkeypatch):
    seen = _script(monkeypatch, "get_summary_stats")
    answer = ai_assistant.ask_assistant(db, world.school.id, [{"role": "user", "content": "overall?"}])
    assert answer == "Here you go." and seen["tool_result"]


def test_not_configured_messages_are_unchanged_in_spirit(db, world, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    assert "GEMINI_API_KEY" in ai_assistant.ask_assistant(db, world.school.id, [{"role": "user", "content": "hi"}])
    assert "isn't available yet" in parent_assistant.ask_parent_assistant(db, world.parent.id, [{"role": "user", "content": "hi"}])
