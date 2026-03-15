from datetime import UTC, datetime
from typing import Any

from fastapi import Request


def build_success_response(
    request: Request,
    data: Any,
    status_code: int,
    message: str = "Request successful",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "success": True,
        "status_code": status_code,
        "error_code": None,
        "message": message,
        "request_timestamp": datetime.now(UTC).isoformat(),
        "request_id": getattr(request.state, "request_id", None),
        "data": data,
        "meta": meta,
    }


def build_error_response(
    request: Request,
    *,
    status_code: int,
    error_code: str,
    message: str,
    data: Any = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "status_code": status_code,
        "error_code": error_code,
        "message": message,
        "request_timestamp": datetime.now(UTC).isoformat(),
        "request_id": getattr(request.state, "request_id", None),
        "data": data,
        "meta": meta,
    }
