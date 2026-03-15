from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.response import build_error_response

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        error_code = "HTTP_ERROR"
        if exc.status_code == HTTPStatus.BAD_REQUEST:
            error_code = "BAD_REQUEST"
        elif exc.status_code == HTTPStatus.NOT_FOUND:
            error_code = "NOT_FOUND"
        elif exc.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            error_code = "VALIDATION_ERROR"
        elif exc.status_code == HTTPStatus.BAD_GATEWAY:
            error_code = "UPSTREAM_ERROR"

        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_response(
                request,
                status_code=exc.status_code,
                error_code=error_code,
                message=str(exc.detail),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=build_error_response(
                request,
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                error_code="VALIDATION_ERROR",
                message="Request validation failed",
                meta={"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        _: Exception,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=build_error_response(
                request,
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                error_code="INTERNAL_SERVER_ERROR",
                message="Internal server error",
            ),
        )
