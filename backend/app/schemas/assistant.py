from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    # Prior turns of THIS conversation, oldest first — the frontend keeps the
    # transcript and resends it each turn; the server holds no session state.
    history: list[AssistantMessage] = Field(default_factory=list)


class AssistantAction(BaseModel):
    tool: str
    result_summary: str


class AssistantChatResponse(BaseModel):
    reply: str
    actions_taken: list[AssistantAction]
