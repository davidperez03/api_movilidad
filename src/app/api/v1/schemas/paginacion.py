from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class PaginaResponse(BaseModel, Generic[T]):
    items: list[T]
    siguiente_cursor: Optional[str] = None
    total: int
