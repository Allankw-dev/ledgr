"""Who may call what. Written after a security review found two routes that checked 'is logged in' but not
'is allowed':

  * GET /api/students and /api/students/{id} returned every student's name and admission number to ANY
    signed-in user, parents included. That leaks children's details across families and defeats the rate
    limit on the admission-number lookup that exists to stop admission numbers being enumerated.
  * POST /api/payments/mpesa/stk-push only checked the parent-to-student link `if role == PARENT`, so a
    teacher skipped authorization entirely and could trigger M-Pesa prompts for any student.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.main import app
from app.models.enums import GuardianLinkStatus, UserRole
from app.models.school import User
from app.models.student import Student, StudentGuardian
from app.services.subscription_service import invalidate_school_state
from tests.conftest import needs_db

pytestmark = needs_db


@pytest.fixture()
def http(db, world):
    limiter.reset()
    invalidate_school_state(world.school.id)
    c = TestClient(app)
    yield c
    invalidate_school_state(world.school.id)
    limiter.reset()


@pytest.fixture()
def families(db, world):
    """world.parent is linked (approved) to world.student. Another family's child exists too, and so does
    a teacher."""
    db.add(StudentGuardian(student_id=world.student.id, user_id=world.parent.id, status=GuardianLinkStatus.APPROVED, relationship_type="mother", is_primary=True))
    stranger_kid = Student(school_id=world.school.id, admission_number="9999", full_name="Someone Else's Child")
    teacher = User(
        school_id=world.school.id, email="teacher@example.com", password_hash="x", role=UserRole.TEACHER,
        full_name="Tee Cher", is_active=True,
    )
    db.add_all([stranger_kid, teacher])
    db.commit()
    return stranger_kid, teacher


def _as(user, role, school_id):
    return {"Authorization": "Bearer " + create_access_token(user.id, school_id, role)}


# ---- the student roster is for the school's staff ----------------------------------------------


def test_a_parent_cannot_list_the_schools_students(db, world, families, http):
    res = http.get("/api/students", headers=_as(world.parent, "PARENT", world.school.id))
    assert res.status_code == 403
    assert "Someone Else" not in res.text and "9999" not in res.text


def test_a_parent_cannot_fetch_any_student_record_by_id_not_even_their_own_childs(db, world, families, http):
    stranger_kid, _ = families
    headers = _as(world.parent, "PARENT", world.school.id)
    assert http.get(f"/api/students/{stranger_kid.id}", headers=headers).status_code == 403
    # Their own child's details reach them through /api/parent/students, which is scoped to approved links.
    assert http.get(f"/api/students/{world.student.id}", headers=headers).status_code == 403
    assert http.get("/api/parent/students", headers=headers).status_code == 200


@pytest.mark.parametrize("role", ["SCHOOL_ADMIN", "BURSAR", "TEACHER"])
def test_school_staff_can_still_list_and_open_students(db, world, families, http, role):
    user = {"BURSAR": world.bursar}.get(role) or families[1]
    if role == "SCHOOL_ADMIN":
        user = User(school_id=world.school.id, email="admin@example.com", password_hash="x", role=UserRole.SCHOOL_ADMIN, full_name="Admin", is_active=True)
        db.add(user)
        db.commit()
    headers = _as(user, role, world.school.id)
    listing = http.get("/api/students", headers=headers)
    assert listing.status_code == 200 and listing.json()["meta"]["total"] >= 2
    assert http.get(f"/api/students/{world.student.id}", headers=headers).status_code == 200


# ---- starting an M-Pesa payment is for parents (of their own child) and the bursar --------------


def test_a_teacher_cannot_start_an_mpesa_payment(db, world, families, http):
    _, teacher = families
    res = http.post(
        "/api/payments/mpesa/stk-push",
        json={"invoice_id": world.invoice.id, "phone_number": "0712345678"},
        headers=_as(teacher, "TEACHER", world.school.id),
    )
    assert res.status_code == 403


def test_a_parent_cannot_start_a_payment_for_someone_elses_child(db, world, families, http):
    stranger_kid, _ = families
    res = http.post(
        "/api/payments/mpesa/stk-push",
        json={"student_id": stranger_kid.id, "phone_number": "0712345678"},
        headers=_as(world.parent, "PARENT", world.school.id),
    )
    assert res.status_code in (403, 422)  # 422 if the stranger's child owes nothing; never a prompt


def test_the_bursar_and_a_linked_parent_pass_authorization_for_an_mpesa_payment(db, world, families, http):
    body = {"invoice_id": world.invoice.id, "phone_number": "0712345678"}
    for user, role in ((world.bursar, "BURSAR"), (world.parent, "PARENT")):
        res = http.post("/api/payments/mpesa/stk-push", json=body, headers=_as(user, role, world.school.id))
        # The test environment has no Daraja callback URL, so a request that clears authorization stops at
        # 503. Anything but 401/403 means the person was allowed to try.
        assert res.status_code not in (401, 403), (role, res.status_code, res.text)
