from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    services: dict[str, str]


class ListResponse(BaseModel):
    data: list[Any]
    count: int
