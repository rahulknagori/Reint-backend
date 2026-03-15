from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool
    status_code: int
    error_code: str | None = None
    message: str
    request_timestamp: datetime
    request_id: str | None = None
    data: Any | None = None
    meta: dict[str, Any] | None = None
