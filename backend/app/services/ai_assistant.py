"""The bursar's 'Ask Ledgr' assistant. Read-only by design: every tool
below queries data, none of them write anything. A bursar can ask things
like "which Grade 4 students are overdue" or "has the Otieno boy paid this
term" and get a real, grounded answer instead of having to click through
the Students/Invoices tables themselves — useful once a school has enough
students that scanning the tables by eye stops being practical.

Not built yet, deliberately: any tool that *does* something (send
reminders, generate invoices) needs a separate confirmation step before
it fires, so it isn't in this first pass — this is Q&A only.
"""

import json

import anthropic
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import analytics_service

MODEL = "claude-sonnet-4-6"
MAX_TOOL_ITERATIONS = 4

SYSTEM_PROMPT = """You are Ledgr's bursar assistant, embedded in a school fee-management app. \
You answer questions about the school's students, invoices, and fee collection using the tools \
provided — never from your own assumptions or general knowledge about schools.

Rules:
- Always call a tool to get real numbers before answering anything about the school's data. \
Never guess or estimate a figure.
- If a tool returns no results, say so plainly rather than inventing a plausible-sounding answer.
- Money is in the school's local currency; state amounts exactly as returned, don't round.
- You cannot send reminders, record payments, or change any data — you can only look things up. \
If asked to take an action, say that's not something you can do yet and suggest where in the app \
to do it (the Invoices page has "Remind" buttons per invoice).
- Keep answers short and concrete — a bursar wants the number and the names, not a narrative."""

TOOLS = [
    {
        "name": "get_summary_stats",
        "description": "Overall totals: money collected, money outstanding, count of overdue invoices, count of active students. Use for 'how are we doing overall' type questions.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_collection_by_term",
        "description": "Billed vs paid totals broken down by term. Use for questions comparing terms or asking about a trend over time.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_overdue_invoices",
        "description": "List of overdue invoices with student name, class, balance, and due date. Optionally filter to one class.",
        "input_schema": {
            "type": "object",
            "properties": {
                "class_name": {"type": "string", "description": "Optional class name to filter by, e.g. 'Grade 4'."},
                "limit": {"type": "integer", "description": "Max results, default 20."},
            },
        },
    },
    {
        "name": "get_top_risk_students",
        "description": "Unpaid invoices ranked by risk score (likelihood of non-payment), highest risk first. Optionally filter to one class.",
        "input_schema": {
            "type": "object",
            "properties": {
                "class_name": {"type": "string", "description": "Optional class name to filter by."},
                "limit": {"type": "integer", "description": "Max results, default 5."},
            },
        },
    },
    {
        "name": "search_students",
        "description": "Find a specific student by name or admission number, and show their total billed/paid/balance across all their invoices.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Name (full or partial) or admission number."}},
            "required": ["query"],
        },
    },
]


def _run_tool(db: Session, school_id: str, name: str, tool_input: dict) -> str:
    if name == "get_summary_stats":
        stats = analytics_service.get_summary_stats(db, school_id)
        result = {
            "total_collected": str(stats.total_collected),
            "total_outstanding": str(stats.total_outstanding),
            "overdue_count": stats.overdue_count,
            "active_student_count": stats.active_student_count,
        }
    elif name == "get_collection_by_term":
        result = [
            {"term_name": t.term_name, "total_billed": str(t.total_billed), "total_paid": str(t.total_paid)}
            for t in analytics_service.get_collection_by_term(db, school_id)
        ]
    elif name == "get_overdue_invoices":
        class_id = None
        if class_name := tool_input.get("class_name"):
            class_id = analytics_service.resolve_class_id(db, school_id, class_name)
            if not class_id:
                return json.dumps({"error": f"No class matching '{class_name}' found."})
        result = analytics_service.get_overdue_invoices(db, school_id, class_id=class_id, limit=tool_input.get("limit", 20))
    elif name == "get_top_risk_students":
        class_id = None
        if class_name := tool_input.get("class_name"):
            class_id = analytics_service.resolve_class_id(db, school_id, class_name)
            if not class_id:
                return json.dumps({"error": f"No class matching '{class_name}' found."})
        risk = analytics_service.get_top_risk_invoices(db, school_id, limit=tool_input.get("limit", 5), class_id=class_id)
        result = [
            {
                "student_name": r.student_name,
                "class_name": r.class_name,
                "balance": str(r.balance),
                "risk_score": r.risk_score,
                "risk_level": r.risk_level,
            }
            for r in risk
        ]
    elif name == "search_students":
        result = analytics_service.search_students(db, school_id, tool_input["query"])
    else:
        return json.dumps({"error": f"Unknown tool '{name}'"})

    return json.dumps(result, default=str)


def ask_assistant(db: Session, school_id: str, messages: list[dict]) -> str:
    """messages is the full conversation so far, each item {"role": "user"|"assistant", "content": str}.
    Returns the assistant's reply text for this turn. Stateless — the caller
    (frontend) is responsible for keeping and resending history, same as any
    direct use of the Messages API."""
    if not settings.anthropic_api_key:
        return "The AI assistant isn't configured yet — an ANTHROPIC_API_KEY needs to be set in the backend's .env."

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    conversation: list[dict] = [{"role": m["role"], "content": m["content"]} for m in messages]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=conversation,
            tools=TOOLS,
        )

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text")

        conversation.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            output = _run_tool(db, school_id, block.name, block.input)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})

        conversation.append({"role": "user", "content": tool_results})

    return "That took more lookups than expected — try asking a more specific question."
