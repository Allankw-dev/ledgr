from typing import Literal

from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistantQueryRequest(BaseModel):
    # Full conversation so far, oldest first — the endpoint is stateless,
    # same pattern as any direct use of the Anthropic Messages API.
    messages: list[AssistantMessage] = Field(min_length=1, max_length=40)


class AssistantQueryResponse(BaseModel):
    answer: str
