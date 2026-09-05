"""
AI bursar assistant — a bounded tool-calling loop over the Anthropic API.

Design notes:
- Read tools (get_dashboard_summary, get_top_risk_invoices, search_students,
  get_student_invoices) reuse analytics_service so the assistant can never
  report numbers that disagree with the dashboard.
- The one action tool (send_fee_reminder) reuses the exact same
  notification_service call the "Send reminder" button on an invoice uses —
  the assistant has no code path to contact a guardian that a human bursar
  doesn't already have.
- Every send_fee_reminder call is audit-logged (entity_type="ai_action") in
  the same transaction as the rest of the request, and is also returned to
  the caller as a structured `actions_taken` entry — independent of
  whatever the model's text response says — so the UI can show an
  unambiguous "the assistant did X" record even if the model's phrasing is
  vague or it forgets to mention it.
- The loop is bounded (MAX_TOOL_ROUNDS) so a confused model can't spiral
  into an unbounded number of tool calls/API spend on one request.
- Tenant scoping: every tool takes `school_id` from the authenticated
  request (see router), never from the model — the model cannot ask for
  another school's data no matter what it's prompted to do.
"""

import json
from dataclasses import dataclass, field
from decimal import Decimal

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import GuardianLinkStatus, InvoiceStatus
from app.models.invoice import Invoice
from app.models.school import School, User
from app.models.student import SchoolClass, Student, StudentGuardian
from app.services import analytics_service, audit_service
from app.services.notification_service import send_reminder_to_guardian

MAX_TOOL_ROUNDS = 6
MAX_HISTORY_MESSAGES = 20  # caller-side cap on conversation turns sent per request


class AssistantConfigError(Exception):
    """Raised when the assistant is invoked without an Anthropic API key configured."""


@dataclass
class ToolContext:
    db: Session
    school_id: str
    user_id: str


@dataclass
class ActionRecord:
    tool: str
    input: dict
    result_summary: str


@dataclass
class AssistantReply:
    reply: str
    actions_taken: list[ActionRecord] = field(default_factory=list)


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def _json(obj) -> str:
    return json.dumps(obj, default=_decimal_default)


# --- Tool schemas (Anthropic tool-use format) -------------------------------

TOOLS = [
    {
        "name": "get_dashboard_summary",
        "description": (
            "Get headline fee-collection numbers for the school: total collected, "
            "total outstanding, count of overdue invoices, active student count, "
            "and billed-vs-paid totals broken down by term. Use this for any "
            "question about overall collection status or trends."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_top_risk_invoices",
        "description": (
            "Get the unpaid invoices most likely to go unpaid, ranked by a risk "
            "score (0-100) based on the student's payment history, how overdue "
            "the invoice is, remaining balance, and past failed/reversed "
            "payments. Use this for questions about which students/invoices "
            "need attention."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max number of invoices to return (default 5, max 20).",
                }
            },
        },
    },
    {
        "name": "forecast_next_term_collection",
        "description": (
            "Get a simple linear-trend forecast of how much the school is likely "
            "to collect next term, based on past terms' totals. Always report "
            "the returned confidence level ('low' or 'medium') alongside the "
            "number — this is a straight-line extrapolation from a handful of "
            "terms, not a strong prediction. Returns null if there isn't enough "
            "term history yet (fewer than 2 completed terms)."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_students",
        "description": (
            "Search for students by name or admission number within this school. "
            "Use this to resolve a student the user mentions by name into an ID "
            "before calling get_student_invoices or send_fee_reminder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Name (partial match) or admission number."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_student_invoices",
        "description": "Get all invoices (with status and balance) for one specific student.",
        "input_schema": {
            "type": "object",
            "properties": {"student_id": {"type": "string"}},
            "required": ["student_id"],
        },
    },
    {
        "name": "send_fee_reminder",
        "description": (
            "Send a fee reminder (email + SMS, whichever channels are configured) "
            "to every approved guardian of the student on this invoice. Only use "
            "this when the user has clearly asked to remind/notify/nudge a "
            "specific guardian or student about a balance — never send reminders "
            "on your own initiative just because an invoice looks risky. Fails "
            "harmlessly (no-ops) if the invoice is already fully paid or has no "
            "approved guardian contacts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"invoice_id": {"type": "string"}},
            "required": ["invoice_id"],
        },
    },
]


# --- Tool execution ----------------------------------------------------------

def _tool_get_dashboard_summary(ctx: ToolContext, _input: dict) -> dict:
    stats = analytics_service.get_headline_stats(ctx.db, ctx.school_id)
    terms = analytics_service.get_collection_by_term(ctx.db, ctx.school_id)
    return {
        "total_collected": stats.total_collected,
        "total_outstanding": stats.total_outstanding,
        "overdue_count": stats.overdue_count,
        "active_student_count": stats.active_student_count,
        "collection_by_term": [
            {"term_name": t.term_name, "total_billed": t.total_billed, "total_paid": t.total_paid} for t in terms
        ],
    }


def _tool_forecast_next_term_collection(ctx: ToolContext, _input: dict) -> dict:
    forecast = analytics_service.forecast_next_term_collection(ctx.db, ctx.school_id)
    if forecast is None:
        return {"forecast_available": False, "reason": "Not enough completed terms of history yet (need at least 2)."}
    return {
        "forecast_available": True,
        "forecasted_total_paid": forecast.forecasted_total_paid,
        "confidence": forecast.confidence,
        "based_on_terms": forecast.based_on_terms,
    }


def _tool_get_top_risk_invoices(ctx: ToolContext, input: dict) -> dict:
    limit = min(int(input.get("limit") or 5), 20)
    rows = analytics_service.get_top_risk_invoices(ctx.db, ctx.school_id, limit=limit)
    return {
        "invoices": [
            {
                "invoice_id": r.invoice_id,
                "student_id": r.student_id,
                "student_name": r.student_name,
                "class_name": r.class_name,
                "balance": r.balance,
                "risk_score": r.risk_score,
                "risk_level": r.risk_level,
            }
            for r in rows
        ]
    }


def _tool_search_students(ctx: ToolContext, input: dict) -> dict:
    query = (input.get("query") or "").strip()
    if not query:
        return {"students": []}

    like = f"%{query}%"
    rows = ctx.db.execute(
        select(Student, SchoolClass)
        .outerjoin(SchoolClass, Student.class_id == SchoolClass.id)
        .where(
            Student.school_id == ctx.school_id,
            (Student.full_name.ilike(like)) | (Student.admission_number.ilike(like)),
        )
        .limit(10)
    ).all()

    return {
        "students": [
            {
                "student_id": student.id,
                "full_name": student.full_name,
                "admission_number": student.admission_number,
                "class_name": school_class.name if school_class else None,
                "is_active": student.is_active,
            }
            for student, school_class in rows
        ]
    }


def _tool_get_student_invoices(ctx: ToolContext, input: dict) -> dict:
    student_id = input.get("student_id")
    student = ctx.db.get(Student, student_id)
    if not student or student.school_id != ctx.school_id:
        return {"error": "Student not found in this school."}

    invoices = ctx.db.execute(
        select(Invoice).where(Invoice.student_id == student_id, Invoice.school_id == ctx.school_id)
    ).scalars().all()

    return {
        "student_name": student.full_name,
        "invoices": [
            {
                "invoice_id": inv.id,
                "term_id": inv.term_id,
                "total_amount": inv.total_amount,
                "amount_paid": inv.amount_paid,
                "balance": inv.total_amount - inv.amount_paid,
                "status": inv.status.value,
                "due_date": inv.due_date.isoformat(),
            }
            for inv in invoices
        ],
    }


def _tool_send_fee_reminder(ctx: ToolContext, input: dict) -> tuple[dict, ActionRecord | None]:
    invoice_id = input.get("invoice_id")
    invoice = ctx.db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.school_id == ctx.school_id)
    ).scalar_one_or_none()
    if not invoice:
        return {"error": "Invoice not found in this school."}, None

    balance = invoice.total_amount - invoice.amount_paid
    if balance <= 0:
        return {"error": "This invoice is already fully paid — no reminder sent."}, None

    student = ctx.db.get(Student, invoice.student_id)
    school = ctx.db.get(School, ctx.school_id)
    if not student or not school:
        return {"error": "Related student/school record not found."}, None

    links = ctx.db.execute(
        select(StudentGuardian).where(
            StudentGuardian.student_id == student.id,
            StudentGuardian.status == GuardianLinkStatus.APPROVED,
        )
    ).scalars().all()

    if not links:
        return {"error": "No approved guardian contacts linked to this student — nothing sent."}, None

    notified = 0
    errors: list[str] = []
    for link in links:
        guardian = ctx.db.get(User, link.user_id)
        if not guardian:
            continue
        outcome = send_reminder_to_guardian(
            guardian_email=guardian.email,
            guardian_phone=guardian.phone,
            student_name=student.full_name,
            school_name=school.name,
            balance=balance,
            currency=school.currency,
            due_date=invoice.due_date,
        )
        if outcome.email_sent or outcome.sms_sent:
            notified += 1
        errors.extend(outcome.errors)

    audit_service.log_audit(
        ctx.db,
        school_id=ctx.school_id,
        action="ai_send_fee_reminder",
        entity_type="invoice",
        entity_id=invoice.id,
        user_id=ctx.user_id,
        metadata={"guardians_notified": notified, "errors": errors},
    )

    summary = f"Reminder sent to {notified} guardian(s) for {student.full_name}'s invoice."
    if errors:
        summary += f" ({len(errors)} delivery error(s).)"

    return (
        {"guardians_notified": notified, "errors": errors},
        ActionRecord(tool="send_fee_reminder", input=input, result_summary=summary),
    )


_READ_TOOLS = {
    "get_dashboard_summary": _tool_get_dashboard_summary,
    "get_top_risk_invoices": _tool_get_top_risk_invoices,
    "forecast_next_term_collection": _tool_forecast_next_term_collection,
    "search_students": _tool_search_students,
    "get_student_invoices": _tool_get_student_invoices,
}


def _execute_tool(ctx: ToolContext, name: str, input: dict) -> tuple[dict, ActionRecord | None]:
    if name in _READ_TOOLS:
        return _READ_TOOLS[name](ctx, input), None
    if name == "send_fee_reminder":
        return _tool_send_fee_reminder(ctx, input)
    return {"error": f"Unknown tool '{name}'."}, None


SYSTEM_PROMPT = """You are Ledgr's AI bursar assistant. You help school bursars and admins \
understand fee collection status and, when explicitly asked, contact guardians about balances.

Rules:
- Only discuss data for the current school — you have no access to any other school's records.
- Never state a number you haven't retrieved from a tool call this turn. If you don't know, call a tool.
- Only call send_fee_reminder when the user has clearly asked you to notify/remind/contact a guardian. \
Do not send reminders on your own initiative, even if you notice a risky invoice.
- When you take an action (like sending a reminder), say plainly what you did and to whom/what result.
- Be concise. Bursars are busy — lead with the number or answer, not a preamble."""


def run_assistant(
    db: Session,
    school_id: str,
    user_id: str,
    message: str,
    history: list[dict] | None = None,
) -> AssistantReply:
    if not settings.anthropic_api_key:
        raise AssistantConfigError("AI assistant is not configured (missing ANTHROPIC_API_KEY).")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    ctx = ToolContext(db=db, school_id=school_id, user_id=user_id)

    messages: list[dict] = list((history or [])[-MAX_HISTORY_MESSAGES:])
    messages.append({"role": "user", "content": message})

    actions_taken: list[ActionRecord] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=settings.ai_assistant_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            final_text = "".join(block.text for block in response.content if block.type == "text")
            return AssistantReply(reply=final_text.strip(), actions_taken=actions_taken)

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result, action = _execute_tool(ctx, block.name, block.input)
            if action:
                actions_taken.append(action)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _json(result),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return AssistantReply(
        reply="I wasn't able to finish that within my step limit — could you narrow the request?",
        actions_taken=actions_taken,
    )
