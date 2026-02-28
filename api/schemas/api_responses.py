from __future__ import annotations

from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiError(BaseModel):
    """Standard error payload for API responses."""

    code: str = Field(default="error")
    message: str
    details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")


class ApiMeta(BaseModel):
    """Optional metadata attached to responses."""

    request_id: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ApiResponse(BaseModel, Generic[T]):
    """Standard envelope for all API responses."""

    ok: bool
    data: Optional[T] = None
    error: Optional[ApiError] = None
    meta: ApiMeta = Field(default_factory=ApiMeta)

    model_config = ConfigDict(extra="ignore")


def ok(data: T = None, *, meta: Optional[ApiMeta] = None) -> Dict[str, Any]:
    """Create a success envelope as a JSON-serializable dict."""

    payload = ApiResponse[T](ok=True, data=data, error=None, meta=meta or ApiMeta())
    return payload.model_dump(mode="json")


def fail(
    message: str,
    *,
    code: str = "error",
    details: Optional[Dict[str, Any]] = None,
    meta: Optional[ApiMeta] = None,
) -> Dict[str, Any]:
    """Create an error envelope as a JSON-serializable dict."""

    payload = ApiResponse[None](
        ok=False,
        data=None,
        error=ApiError(code=code, message=message, details=details),
        meta=meta or ApiMeta(),
    )
    return payload.model_dump(mode="json")
