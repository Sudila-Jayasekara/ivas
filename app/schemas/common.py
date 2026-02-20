"""
Common API Schemas

Defines generic Pydantic models used across multiple API routes, such as standard
response formats for health checks and list endpoints.
"""

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    services: dict[str, str]


class ListResponse(BaseModel):
    data: list[Any]
    count: int
