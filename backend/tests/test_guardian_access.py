"""A parent whose link to a child is still PENDING (or was REJECTED) has NOT been verified by
the school. Anyone can sign up as a parent and request a link to any admission number, so
until a bursar approves, that link must grant no access to the child's data — anywhere."""

import json

import httpx
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.deps import CurrentUser
from app.models.enums import GuardianLinkStatus
from app.models.student import StudentGuardian
from app.routers import parent as parent_router
from app.routers.mpesa import _prepare_stk_push
from app.schemas.mpesa import StkPushRequest
from app.services import llm, parent_assistant
from tests.conftest import needs_db

pytestmark = needs_db

STATUSES = [GuardianLinkStatus.PENDING, GuardianLinkStatus.REJECTED]


def _link(db, w, status):
    db.add(StudentGuardian(student_id=w.student.id, user_id=w.parent.id, relationship_type="mother", status=status))
    db.commit()


def _parent(w):
    return CurrentUser(user_id=w.parent.id, school_id=w.school.id, role="PARENT")


@pytest.mark.parametrize("status", STATUSES)
def test_unapproved_link_shows_no_children_in_the_portal(db, world, status):
    _link(db, world, status)
    assert parent_router.list_my_children(db=db, user=_parent(world), _school_id=world.school.id) == []


def test_approved_link_still_works(db, world):
    _link(db, world, GuardianLinkStatus.APPROVED)
    [child] = parent_router.list_my_children(db=db, user=_parent(world), _school_id=world.school.id)
    assert child.full_name == "Kid One" and child.invoices[0].total_amount == 10000


@pytest.mark.parametrize("status", STATUSES)
def test_unapproved_link_cannot_start_a_payment_for_the_child(db, world, status):
    _link(db, world, status)
    req = StkPushRequest(student_id=world.student.id, phone_number="0712345678")
    with pytest.raises(HTTPException) as e:
        _prepare_stk_push(db, req, _parent(world), world.school.id)
    assert e.value.status_code == 403
    req2 = StkPushRequest(invoice_id=world.invoice.id, phone_number="0712345678")
    with pytest.raises(HTTPException) as e2:
        _prepare_stk_push(db, req2, _parent(world), world.school.id)
    assert e2.value.status_code == 403


@pytest.mark.parametrize("status", STATUSES)
def test_unapproved_link_gets_nothing_from_the_ai_assistant(db, world, monkeypatch, status):
    _link(db, world, status)
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "ai_provider", "auto")
    monkeypatch.setattr(llm, "_resolved_gemini_model", None)
    seen = {}

    def handler(request):
        last = json.loads(request.content)["contents"][-1]["parts"][0]
        if "functionResponse" in last:
            seen["result"] = json.dumps(last["functionResponse"]["response"], default=str)
            return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [{"text": "ok"}]}}]})
        return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": "get_children_overview", "args": {}}}]}}]})

    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))
    parent_assistant.ask_parent_assistant(db, world.parent.id, [{"role": "user", "content": "how are my kids doing?"}])
    monkeypatch.setattr(llm, "_transport", None)
    assert "Kid One" not in seen["result"] and "10000" not in seen["result"]
