from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, get_school_scope, require_roles
from app.core.rate_limit import limiter
from app.schemas.assistant import AssistantAction, AssistantChatRequest, AssistantChatResponse
from app.services.ai_assistant_service import AssistantConfigError, run_assistant

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/chat", response_model=AssistantChatResponse)
@limiter.limit("15/minute")
def chat(
    request: Request,  # required by @limiter.limit — unused otherwise
    data: AssistantChatRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR", "SUPER_ADMIN")),
):
    """
    One turn of the AI bursar assistant. Stateless on the server — the
    frontend resends the conversation history each call. Rate-limited more
    tightly than most endpoints since each call is a paid Anthropic API
    request that can itself trigger several DB queries and, if asked, real
    guardian notifications.
    """
    if not school_id:
        raise HTTPException(400, "SUPER_ADMIN must act within a specific school to use the assistant")

    try:
        result = run_assistant(
            db=db,
            school_id=school_id,
            user_id=user.user_id,
            message=data.message,
            history=[{"role": m.role, "content": m.content} for m in data.history],
        )
    except AssistantConfigError as exc:
        raise HTTPException(503, str(exc))

    db.commit()

    return AssistantChatResponse(
        reply=result.reply,
        actions_taken=[
            AssistantAction(tool=a.tool, result_summary=a.result_summary) for a in result.actions_taken
        ],
    )
