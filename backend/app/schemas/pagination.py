from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    has_more: bool


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta
