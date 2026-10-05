import hashlib
import secrets
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from stockpilot.api.errors import AppError
from stockpilot.config import settings
from stockpilot.db.session import get_session

DB = Annotated[Session, Depends(get_session)]


def local_only() -> None:
    if settings.app_mode == "public_demo":
        raise AppError(
            403, "READ_ONLY_DEMO", "Shared demo is read-only; run locally to modify data"
        )


def session_hash(request: Request) -> str | None:
    if settings.app_mode == "local":
        return None
    token = request.cookies.get("stockpilot_session", "")
    if len(token) != 64:
        raise AppError(403, "SESSION_REQUIRED", "Open a demo session first")
    try:
        bytes.fromhex(token)
    except ValueError as exc:
        raise AppError(403, "INVALID_SESSION", "Invalid demo session") from exc
    return hashlib.sha256(token.encode()).hexdigest()


def new_session_token() -> str:
    return secrets.token_hex(32)
