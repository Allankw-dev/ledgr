from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, get_school_scope
from app.core.rate_limit import limiter
from app.schemas.assistant import AssistantQueryRequest, AssistantQueryResponse
from app.services.parent_assistant import ask_parent_assistant

router = APIRouter(prefix="/api/parent/assistant", tags=["parent"], dependencies=[Depends(get_current_user)])


@router.post("/query", response_model=AssistantQueryResponse)
@limiter.limit("15/minute")
def query_parent_assistant(
    request: Request,
    payload: AssistantQueryRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _school_id: str = Depends(get_school_scope),  # sets RLS tenant context — see parent.py's list_my_children
):
    if user.role != "PARENT":
        raise HTTPException(403, "This endpoint is for parent accounts only")

    answer = ask_parent_assistant(db, user.user_id, [m.model_dump() for m in payload.messages])
    return AssistantQueryResponse(answer=answer)
