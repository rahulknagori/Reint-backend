from fastapi import APIRouter, Request, status

from app.core.response import build_success_response
from app.schemas.api_response import ApiResponse
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
)
async def healthcheck(request: Request) -> ApiResponse:
    payload = HealthResponse(status="ok")
    return ApiResponse.model_validate(
        build_success_response(
            request,
            data=payload.model_dump(),
            status_code=status.HTTP_200_OK,
            message="Health check successful",
        )
    )
