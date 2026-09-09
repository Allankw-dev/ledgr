"""The parent-facing 'Ask Ledgr' assistant — same tool-use pattern as the
bursar's version, but every tool is hard-scoped to the calling parent's own
linked children via parent_data_service (which itself resolves everything
through student_guardians, never a client-supplied student_id). A parent
can ask "has my payment gone through" or "what's still owed this term" and
get a grounded answer instead of reading the invoice table by eye."""

import json

import anthropic
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import parent_data_service

MODEL = "claude-sonnet-4-6"
MAX_TOOL_ITERATIONS = 4

SYSTEM_PROMPT = """You are Ledgr's assistant for a parent/guardian, embedded in the parent portal of a \
school fee-management app. You answer questions about THIS PARENT'S OWN children's fees, invoices, and \
payments using the tools provided — never from assumptions, and never about any other family's data \
(the tools themselves only ever return this parent's own linked children, so there is no way to look up \
anyone else's).

Rules:
- Always call a tool to get real numbers before answering anything about fees, balances, or payments. \
Never guess or estimate a figure.
- If a tool returns no results, say so plainly — e.g. "no payment record matching that" — rather than \
inventing a plausible-sounding answer.
- State amounts exactly as returned, don't round.
- You cannot make a payment, change any data, link a new child, or set up a payment plan — you can only look things up and preview what a plan would look like. If asked to pay a fee, direct them to the "Pay with M-Pesa" button on their dashboard. If asked to link another child, direct them to the "Link another child" option in the portal. If they like a previewed payment plan, direct them to "Request a payment plan" on that invoice.
- Keep answers short and warm — a parent wants a clear answer, not a financial report."""

TOOLS = [
    {
        "name": "get_children_overview",
        "description": "Summary for every child linked to this parent: class, total billed, total paid, balance, and how many invoices are overdue. Use for general 'how are we doing' questions or when the parent has more than one child and hasn't said which.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_payment_history",
        "description": "Recent payments (amount, method, status, M-Pesa/bank reference, date) for this parent's children. Use for 'has my payment gone through', 'did you get my M-Pesa payment', or questions about a specific past payment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {"type": "string", "description": "Optional — narrow to one child if the parent has more than one and named them."},
                "limit": {"type": "integer", "description": "Max results, default 10."},
            },
        },
    },
    {
        "name": "get_invoice_details",
        "description": "Every invoice for this parent's children — due date, total, amount paid, balance, and status. Use for 'what's due', 'when is the next payment due', or 'what do I still owe'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {"type": "string", "description": "Optional — narrow to one child if the parent has more than one and named them."},
            },
        },
    },
    {
        "name": "get_invoice_breakdown",
        "description": "Itemized charges (tuition, transport, lunch, etc.) for each invoice. Use for 'why is my balance so high', 'what am I actually being charged for', or 'explain this invoice' — questions that need the itemization, not just the total.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {"type": "string", "description": "Optional — narrow to one child if the parent has more than one and named them."},
            },
        },
    },
    {
        "name": "get_term_summary",
        "description": "Total billed, total paid, and balance per term (not per invoice) — use for 'how much did we pay this term', 'summarize this term', or 'how does this term compare to last term'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {"type": "string", "description": "Optional — narrow to one child if the parent has more than one and named them."},
            },
        },
    },
    {
        "name": "suggest_payment_plan",
        "description": "Previews a possible installment schedule for any of this parent's unpaid invoices, with a plain-language rationale for the sizing. This is a PREVIEW ONLY — it does not set anything up. Use when a parent asks about paying in installments, spreading out a balance, or a payment plan. Always tell them to use the 'Request a payment plan' option on the invoice in their portal if they want to actually accept it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {"type": "string", "description": "Optional — narrow to one child if the parent has more than one and named them."},
            },
        },
    },
]


def _run_tool(db: Session, guardian_user_id: str, name: str, tool_input: dict) -> str:
    if name == "get_children_overview":
        result = parent_data_service.get_children_overview(db, guardian_user_id)
    elif name == "get_payment_history":
        result = parent_data_service.get_payment_history(
            db, guardian_user_id, student_name=tool_input.get("student_name"), limit=tool_input.get("limit", 10)
        )
    elif name == "get_invoice_details":
        result = parent_data_service.get_invoice_details(db, guardian_user_id, student_name=tool_input.get("student_name"))
    elif name == "get_invoice_breakdown":
        result = parent_data_service.get_invoice_breakdown(db, guardian_user_id, student_name=tool_input.get("student_name"))
    elif name == "get_term_summary":
        result = parent_data_service.get_term_summary(db, guardian_user_id, student_name=tool_input.get("student_name"))
    elif name == "suggest_payment_plan":
        result = parent_data_service.suggest_payment_plan(db, guardian_user_id, student_name=tool_input.get("student_name"))
    else:
        return json.dumps({"error": f"Unknown tool '{name}'"})

    return json.dumps(result, default=str)


def ask_parent_assistant(db: Session, guardian_user_id: str, messages: list[dict]) -> str:
    """Stateless, same pattern as the bursar assistant — caller resends the
    full conversation each turn."""
    if not settings.anthropic_api_key:
        return "The AI assistant isn't available yet — please check back later."

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
            output = _run_tool(db, guardian_user_id, block.name, block.input)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})

        conversation.append({"role": "user", "content": tool_results})

    return "That took more lookups than expected — try asking a more specific question."
