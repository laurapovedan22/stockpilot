import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from stockpilot.api.dependencies import DB
from stockpilot.api.errors import AppError
from stockpilot.api.routers import assistant, catalog, imports, planning
from stockpilot.config import settings

app = FastAPI(
    title="StockPilot", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)
logger = logging.getLogger("stockpilot.api")
logging.basicConfig(level=settings.log_level)


@app.middleware("http")
async def audit(request: Request, call_next):
    request.state.request_id = str(uuid4())
    started = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    logger.info(
        json.dumps(
            {
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )
    )
    return response


def error_response(request, status, code, message, details=None):
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "request_id": getattr(request.state, "request_id", "unknown"),
            }
        },
    )


@app.exception_handler(AppError)
async def app_error(request: Request, exc: AppError):
    return error_response(request, exc.status, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def schema_error(request: Request, exc: RequestValidationError):
    details = [
        {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
        for error in exc.errors()
    ]
    return error_response(request, 422, "INVALID_SCHEMA", "Check input fields", details)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return error_response(request, exc.status_code, "HTTP_ERROR", str(exc.detail))


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    return error_response(
        request,
        503,
        "DATABASE_UNAVAILABLE",
        "Database unavailable or transaction conflict; refresh and retry",
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.error(
        "Unexpected error", extra={"request_id": getattr(request.state, "request_id", "unknown")}
    )
    return error_response(
        request, 500, "INTERNAL_ERROR", "Unexpected error; consult local server logs"
    )


@app.get("/api/v1/health/live")
def live():
    return {"status": "alive"}


@app.get("/api/v1/health/ready")
def ready(db: DB):
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    if version != "0001":
        raise AppError(503, "MIGRATION_REQUIRED", "Database migration mismatch")
    return {"status": "ready", "migration": version}


for router in (catalog.router, imports.router, planning.router, assistant.router):
    app.include_router(router, prefix="/api/v1")
