from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles
from app.core.rate_limit import limiter
from app.schemas.assistant import AssistantQueryRequest, AssistantQueryResponse
from app.services.ai_assistant import ask_assistant

router = APIRouter(prefix="/api/assistant", tags=["assistant"], dependencies=[Depends(get_current_user)])


@router.post("/query", response_model=AssistantQueryResponse)
@limiter.limit("15/minute")
def query_assistant(
    request: Request,
    payload: AssistantQueryRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR", "SUPER_ADMIN")),
):
    """Rate-limited (unlike most read endpoints) because each call may hit
    the Anthropic API, which costs real money per request — 15/minute is
    generous for a human typing questions, tight enough to blunt a runaway
    script or a compromised session from racking up an unbounded bill."""
    if not school_id:
        raise HTTPException(400, "SUPER_ADMIN must act within a specific school to use the assistant")

    answer = ask_assistant(db, school_id, [m.model_dump() for m in payload.messages])
    return AssistantQueryResponse(answer=answer)
