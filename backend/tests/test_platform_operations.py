# ruff: noqa: F811  (fixtures imported from test_school_mpesa are used as test arguments)
"""Running many schools: the sweep, the operator's billing book, rotating one school's address, the payments-health
view, the shared-paybill guard and the Daraja token cache."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select

from app import main as app_main
from app.core.security import create_access_token
from app.models.enums import PaymentMethod, PaymentStatus
from app.models.mpesa_account import SchoolMpesaAccount
from app.models.mpesa_transaction import MpesaTransaction
from app.models.payment import AuditLog, Payment
from app.models.school import School
from app.models.subscription_payment import SubscriptionPayment
from app.services import mpesa_service
from app.services.mpesa_accounts import school_webhook_token, verify_school_webhook_token
from tests.conftest import needs_db
from tests.test_school_mpesa import (  # noqa: F401  (fixtures are used by name)
    A_KEY, A_PASSKEY, A_SECRET, B_KEY, B_SECRET, daraja, go_live, http, make_school, operator, save_account,
    school_a, school_b, stk,
)

pytestmark = needs_db

NOW = lambda: datetime.now(timezone.utc)  # noqa: E731


# ======================================================================================================
# 1. The daily reminder sweep does not run for schools that stopped paying
# ======================================================================================================


def test_the_daily_sweep_skips_schools_that_are_read_only(db, monkeypatch):
    def school(name, status, *, trial_ends=None, paid_until=None):
        s = School(name=name, country="KE", contact_email=f"{name}@x.test", auto_reminders_enabled=True,
                   subscription_status=status, trial_ends_at=trial_ends, paid_until=paid_until)
        db.add(s)
        return s

    active = school("active", "ACTIVE", paid_until=NOW() + timedelta(days=20))
    forever = school("forever", "ACTIVE")  # no end date: never expires
    trial = school("trial", "TRIAL", trial_ends=NOW() + timedelta(days=5))
    grace = school("grace", "ACTIVE", paid_until=NOW() - timedelta(days=2))  # lapsed, still inside the 7 grace days
    expired = school("expired", "ACTIVE", paid_until=NOW() - timedelta(days=30))
    suspended = school("suspended", "SUSPENDED", paid_until=NOW() + timedelta(days=20))
    db.commit()

    ran = []

    class _Result:
        invoices_checked, reminders_sent, errors = 0, 0, []

    monkeypatch.setattr(app_main, "run_overdue_reminder_sweep", lambda _db, school_id: ran.append(school_id) or _Result())
    app_main.run_daily_overdue_sweep()

    assert set(ran) == {active.id, forever.id, trial.id, grace.id}
    assert expired.id not in ran and suspended.id not in ran


# ======================================================================================================
# 2. What schools pay the operator: a book, not just a date
# ======================================================================================================


def pay(http, operator, school, **over):
    body = {"amount": "15000.00", "method": "MPESA", "reference": "SJK4X2L9QP", "months": 3}
    body.update(over)
    return http.post(f"/api/platform/schools/{school.id}/subscription-payments", headers=operator.headers, json=body)


def paid_until(db, school):
    db.expire_all()
    return db.get(School, school.id).paid_until


def test_recording_a_payment_books_the_money_and_extends_the_date_together(db, world, http, operator):
    res = pay(http, operator, world.school)
    assert res.status_code == 201, res.text
    body = res.json()
    assert Decimal(body["amount"]) == Decimal("15000.00") and body["months_added"] == 3 and body["reference"] == "SJK4X2L9QP"
    assert paid_until(db, world.school) is not None
    actions = {a.action for a in db.execute(select(AuditLog).where(AuditLog.school_id == world.school.id)).scalars()}
    assert {"SUBSCRIPTION_PAYMENT_RECORDED", "SUBSCRIPTION_UPDATED"} <= actions


def test_the_same_reference_cannot_be_booked_twice_and_does_not_extend_twice(db, world, http, operator):
    assert pay(http, operator, world.school).status_code == 201
    first = paid_until(db, world.school)
    again = pay(http, operator, world.school)
    assert again.status_code == 409 and "already booked" in again.json()["detail"]
    assert paid_until(db, world.school) == first  # not pushed out a second time
    assert db.execute(select(SubscriptionPayment)).scalars().all().__len__() == 1


def test_a_mobile_money_or_bank_payment_needs_a_reference(db, world, http, operator):
    assert pay(http, operator, world.school, reference=None).status_code == 422
    assert pay(http, operator, world.school, method="BANK_TRANSFER", reference="  ").status_code == 422
    assert pay(http, operator, world.school, method="CASH", reference=None, months=1).status_code == 201


def test_a_payment_with_no_months_books_the_money_without_moving_the_date(db, world, http, operator):
    before = paid_until(db, world.school)
    assert pay(http, operator, world.school, months=0, reference="DEP1").status_code == 201
    assert paid_until(db, world.school) == before


def test_amounts_must_be_positive(db, world, http, operator):
    assert pay(http, operator, world.school, amount="0").status_code == 422
    assert pay(http, operator, world.school, amount="-5").status_code == 422


def test_voiding_keeps_the_row_frees_the_reference_and_leaves_the_date_alone(db, world, http, operator):
    row = pay(http, operator, world.school).json()
    date_after = paid_until(db, world.school)
    res = http.post(f"/api/platform/subscription-payments/{row['id']}/void", headers=operator.headers, json={"reason": "entered twice by mistake"})
    assert res.status_code == 200 and res.json()["voided_at"] is not None
    assert paid_until(db, world.school) == date_after
    assert http.post(f"/api/platform/subscription-payments/{row['id']}/void", headers=operator.headers, json={"reason": "again please"}).status_code == 409
    listing = http.get(f"/api/platform/schools/{world.school.id}/subscription-payments", headers=operator.headers).json()
    assert len(listing["payments"]) == 1 and listing["payments"][0]["void_reason"] == "entered twice by mistake"
    assert Decimal(listing["total_paid"]) == Decimal("0")  # voided money isn't counted
    assert pay(http, operator, world.school, months=1).status_code == 201  # the reference is free again


def test_the_book_lists_newest_first_totals_and_shows_in_the_school_list(db, world, http, operator):
    pay(http, operator, world.school, reference="R1", amount="10000", months=1)
    pay(http, operator, world.school, reference="R2", amount="2500.50", months=0, paid_on=(NOW() + timedelta(days=1)).isoformat())
    listing = http.get(f"/api/platform/schools/{world.school.id}/subscription-payments", headers=operator.headers).json()
    assert [p["reference"] for p in listing["payments"]] == ["R2", "R1"]
    assert Decimal(listing["total_paid"]) == Decimal("12500.50") and listing["currency"] == "KES"
    schools = http.get("/api/platform/schools", headers=operator.headers).json()
    assert next(s for s in schools if s["id"] == world.school.id)["last_payment_on"] is not None


def test_only_the_operator_can_see_or_write_the_book(db, world, http, operator):
    headers = {"Authorization": "Bearer " + create_access_token(world.bursar.id, world.school.id, "BURSAR")}
    url = f"/api/platform/schools/{world.school.id}/subscription-payments"
    assert http.get(url, headers=headers).status_code == 403
    assert http.post(url, headers=headers, json={"amount": "1", "method": "CASH", "months": 1}).status_code == 403
    assert http.get("/api/platform/payments-health", headers=headers).status_code == 403


# ======================================================================================================
# 3. Rotating ONE school's webhook address
# ======================================================================================================


def test_rotating_kills_the_old_address_gives_a_new_one_and_touches_no_other_school(db, world, http, operator, daraja, school_a, school_b):
    register = lambda s: http.post(f"/api/platform/schools/{s.id}/mpesa/register-urls", headers=operator.headers)  # noqa: E731
    register(school_a.school)
    register(school_b.school)
    old_a = school_webhook_token(school_a.school.id, 1)
    old_b = school_webhook_token(school_b.school.id, 1)
    assert verify_school_webhook_token(old_a) == school_a.school.id

    res = http.post(f"/api/platform/schools/{school_a.school.id}/mpesa/rotate-address", headers=operator.headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"]["c2b_registered_at"] is None and "Register URLs" in res.json()["message"]

    assert verify_school_webhook_token(old_a) is None  # the leaked address is dead
    assert verify_school_webhook_token(school_webhook_token(school_a.school.id, 2)) == school_a.school.id
    assert verify_school_webhook_token(old_b) == school_b.school.id  # school B did not notice a thing
    db.expire_all()
    assert db.execute(select(SchoolMpesaAccount).where(SchoolMpesaAccount.school_id == school_b.school.id)).scalar_one().c2b_registered_at is not None
    assert db.execute(select(AuditLog).where(AuditLog.action == "SCHOOL_MPESA_ADDRESS_ROTATED")).scalar_one().school_id == school_a.school.id


def test_registering_again_after_rotating_hands_safaricom_the_new_address(db, world, http, operator, daraja, school_a):
    http.post(f"/api/platform/schools/{school_a.school.id}/mpesa/rotate-address", headers=operator.headers)
    http.post(f"/api/platform/schools/{school_a.school.id}/mpesa/register-urls", headers=operator.headers)
    (reg,) = daraja.registrations()
    assert f"{school_a.school.id}.2." in reg["ConfirmationURL"] and f"{school_a.school.id}.1." not in reg["ConfirmationURL"]


def test_payment_prompts_keep_working_after_rotating(db, world, http, operator, daraja, school_a):
    http.post(f"/api/platform/schools/{school_a.school.id}/mpesa/rotate-address", headers=operator.headers)
    assert stk(http, school_a).status_code == 201
    assert f"{school_a.school.id}.2." in daraja.stk_payloads()[-1]["CallBackURL"]


def test_rotating_is_refused_while_a_prompt_is_in_flight(db, world, http, operator, daraja, school_a):
    assert stk(http, school_a).status_code == 201  # a PENDING prompt, just now
    res = http.post(f"/api/platform/schools/{school_a.school.id}/mpesa/rotate-address", headers=operator.headers)
    assert res.status_code == 409 and "still waiting" in res.json()["detail"]
    assert verify_school_webhook_token(school_webhook_token(school_a.school.id, 1)) == school_a.school.id  # unchanged


def test_a_school_with_no_account_of_its_own_has_nothing_to_rotate(db, world, http, operator):
    res = http.post(f"/api/platform/schools/{world.school.id}/mpesa/rotate-address", headers=operator.headers)
    assert res.status_code == 409


# ======================================================================================================
# 4. The server-wide paybill: sharing is a decision
# ======================================================================================================


def test_the_first_school_on_the_server_wide_paybill_needs_no_confirmation(db, world, http, operator, monkeypatch):
    from tests.test_school_mpesa import use_global_mpesa

    use_global_mpesa(db, world.school, monkeypatch)
    other = make_school(db, "Solo School")
    # world.school was switched to GLOBAL by the helper, so use a school that is the only one on it:
    db.execute(School.__table__.update().values(mpesa_mode="OFF"))
    db.commit()
    res = http.post(f"/api/platform/schools/{other.school.id}/mpesa/mode", headers=operator.headers, json={"mode": "GLOBAL"})
    assert res.status_code == 200, res.text


# ======================================================================================================
# 5. Payments health
# ======================================================================================================


def seed_payment(db, who, *, status, minutes_old=0, notes=None, amount="1000.00", method=PaymentMethod.MPESA, invoice=True):
    p = Payment(
        school_id=who.school.id, student_id=who.student.id, invoice_id=who.invoice.id if invoice else None,
        amount=Decimal(amount), method=method, status=status, notes=notes,
        paid_at=NOW() - timedelta(minutes=minutes_old) if status == PaymentStatus.CONFIRMED else None,
    )
    db.add(p)
    db.flush()
    p.created_at = NOW() - timedelta(minutes=minutes_old)
    db.commit()
    return p


def health(http, operator):
    res = http.get("/api/platform/payments-health", headers=operator.headers)
    assert res.status_code == 200, res.text
    return {r["school_id"]: r for r in res.json()}


def test_health_flags_each_problem_per_school_and_counts_only_that_schools_payments(db, world, http, operator, daraja, school_a, school_b):
    seed_payment(db, school_a, status=PaymentStatus.CONFIRMED, minutes_old=60, amount="2000")
    seed_payment(db, school_a, status=PaymentStatus.CONFIRMED, minutes_old=120, amount="3000")
    seed_payment(db, school_a, status=PaymentStatus.PENDING, minutes_old=45)  # stuck: older than 15 minutes
    seed_payment(db, school_a, status=PaymentStatus.PENDING, minutes_old=1)  # fresh: not stuck yet
    seed_payment(db, school_a, status=PaymentStatus.PENDING, minutes_old=45, notes="Amount mismatch: we asked for KES 2,000, Safaricom reported 1,000")
    for _ in range(5):
        seed_payment(db, school_a, status=PaymentStatus.FAILED, minutes_old=300)
    seed_payment(db, school_a, status=PaymentStatus.CONFIRMED, minutes_old=10, invoice=False)  # money no invoice has claimed
    db.add(MpesaTransaction(trans_id="X1", amount=Decimal("500"), business_shortcode="111111", school_id=school_a.school.id, status="UNMATCHED"))
    db.commit()
    seed_payment(db, school_b, status=PaymentStatus.CONFIRMED, minutes_old=5, amount="9999")

    rows = health(http, operator)
    a, b = rows[school_a.school.id], rows[school_b.school.id]

    assert a["confirmed_30d_count"] == 3 and Decimal(a["confirmed_30d_amount"]) == Decimal("6000.00")
    assert a["stuck_pending"] == 1  # the mismatch is counted on its own, not as "stuck"
    assert a["mismatches"] == 1 and a["failed_7d"] == 5 and a["unallocated"] == 1 and a["unmatched_c2b"] == 1
    assert a["severity"] == "warn" and len(a["attention"]) >= 4
    assert any("could not be matched" in t for t in a["attention"])

    assert b["confirmed_30d_count"] == 1 and Decimal(b["confirmed_30d_amount"]) == Decimal("9999.00")
    assert b["stuck_pending"] == 0 and b["mismatches"] == 0 and b["unmatched_c2b"] == 0
    assert b["last_confirmed_at"] is not None


def test_health_shows_setup_problems_worst_first(db, world, http, operator, daraja, school_a):
    off = make_school(db, "Off School")  # never set up: M-Pesa is off
    rows = http.get("/api/platform/payments-health", headers=operator.headers).json()
    by_id = {r["school_id"]: r for r in rows}
    assert by_id[off.school.id]["mpesa_mode"] == "OFF" and by_id[off.school.id]["severity"] == "info"
    # school_a is live but its direct-payment addresses were never registered: a warning, not a failure
    assert by_id[school_a.school.id]["severity"] == "warn"
    assert any("aren't registered" in t for t in by_id[school_a.school.id]["attention"])
    # a recorded Safaricom problem on a live school is the worst kind
    acct = db.execute(select(SchoolMpesaAccount).where(SchoolMpesaAccount.school_id == school_a.school.id)).scalar_one()
    acct.last_error = "Safaricom rejected the key"
    db.commit()
    rows = http.get("/api/platform/payments-health", headers=operator.headers).json()
    assert rows[0]["school_id"] == school_a.school.id and rows[0]["severity"] == "bad"


def test_health_does_not_leak_secrets_or_people(db, world, http, operator, daraja, school_a):
    seed_payment(db, school_a, status=PaymentStatus.CONFIRMED)
    raw = http.get("/api/platform/payments-health", headers=operator.headers).text
    for secret in (A_KEY, A_SECRET, A_PASSKEY, school_a.student.full_name, "0712345678"):
        assert secret not in raw


def test_health_uses_a_fixed_number_of_queries_however_many_schools_there_are(db, world, http, operator):
    from sqlalchemy import event
    from app.core.database import system_engine

    for i in range(12):
        make_school(db, f"Bulk {i}")
    counts = []
    listener = lambda *a, **k: counts.append(1)  # noqa: E731
    event.listen(system_engine, "before_cursor_execute", listener)
    try:
        assert len(http.get("/api/platform/payments-health", headers=operator.headers).json()) >= 13
    finally:
        event.remove(system_engine, "before_cursor_execute", listener)
    assert len(counts) < 25  # a handful of grouped queries, not a few per school


# ======================================================================================================
# 6. Daraja tokens are remembered, per paybill, and never mixed up
# ======================================================================================================


def test_a_schools_token_is_fetched_once_and_reused_for_its_next_payments(db, world, http, operator, daraja, school_a):
    mpesa_service.clear_token_cache()  # setting the school up already cached a token; start from nothing
    before = len(daraja.oauth_logins())
    for _ in range(3):
        db.query(Payment).delete()  # the duplicate-prompt guard blocks back-to-back prompts for one invoice
        db.commit()
        assert stk(http, school_a, amount="100").status_code == 201
    assert len(daraja.oauth_logins()) - before == 1  # one login for three payments


def test_two_schools_never_share_a_token(db, world, http, operator, daraja, school_a, school_b):
    stk(http, school_a)
    stk(http, school_b)
    logins = daraja.oauth_logins()
    assert f"{A_KEY}:{A_SECRET}" in logins and f"{B_KEY}:{B_SECRET}" in logins
    # and each prompt carried ITS OWN school's paybill, whatever token was cached
    assert {p["BusinessShortCode"] for p in daraja.stk_payloads()} == {"111111", "222222"}


def test_testing_the_connection_always_asks_safaricom_not_the_cache(db, world, http, operator, daraja, school_a):
    n = len(daraja.oauth_logins())
    http.post(f"/api/platform/schools/{school_a.school.id}/mpesa/test", headers=operator.headers)
    http.post(f"/api/platform/schools/{school_a.school.id}/mpesa/test", headers=operator.headers)
    assert len(daraja.oauth_logins()) - n == 2


def test_a_rejected_token_is_dropped_and_the_prompt_is_retried_once_with_a_fresh_one(monkeypatch):
    import asyncio

    calls = {"oauth": 0, "stk": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/v1/generate"):
            calls["oauth"] += 1
            return httpx.Response(200, json={"access_token": f"tok{calls['oauth']}", "expires_in": "3599"})
        calls["stk"] += 1
        if request.headers["Authorization"] == "Bearer tok1":
            return httpx.Response(401, json={"errorMessage": "Invalid Access Token"})
        return httpx.Response(200, json={"CheckoutRequestID": "ws_CO_1"})

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: real(transport=httpx.MockTransport(handler)))
    creds = mpesa_service.MpesaCredentials(consumer_key="k", consumer_secret="s", shortcode="1", passkey="p", base_url="https://x.test")
    out = asyncio.run(mpesa_service.initiate_stk_push(creds, "254712345678", 10, "ref", "desc", "https://cb.test"))
    assert out["CheckoutRequestID"] == "ws_CO_1"
    assert calls == {"oauth": 2, "stk": 2}  # a second login, and exactly one retry


def test_an_expired_token_is_not_reused(monkeypatch):
    import asyncio

    n = {"oauth": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["oauth"] += 1
        return httpx.Response(200, json={"access_token": f"tok{n['oauth']}", "expires_in": "100"})  # shorter than the safety margin

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: real(transport=httpx.MockTransport(handler)))
    creds = mpesa_service.MpesaCredentials(consumer_key="k", consumer_secret="s", shortcode="1", passkey="p", base_url="https://x.test")
    assert asyncio.run(mpesa_service.get_access_token(creds)) == "tok1"
    assert asyncio.run(mpesa_service.get_access_token(creds)) == "tok2"
