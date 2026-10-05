from datetime import timedelta

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from stockpilot.api.dependencies import DB, session_hash
from stockpilot.api.errors import AppError
from stockpilot.api.schemas import AssistantInput
from stockpilot.config import settings
from stockpilot.db.models import AssistantMessage, AssistantSession, Dataset, utcnow
from stockpilot.db.repositories import get
from stockpilot.services.assistant import answer
from stockpilot.worker.queue import dataset_lock

router = APIRouter()


@router.post("/datasets/{dataset_id}/assistant/messages")
def assistant(dataset_id: str, inputs: AssistantInput, db: DB, request: Request):
    get(db, Dataset, dataset_id)
    owner = session_hash(request)
    if settings.app_mode == "public_demo":
        # The limit counts this owner across datasets, so its lock must do the same.
        dataset_lock(db, f"public-assistant:{owner}")
        count = (
            db.scalar(
                select(func.count())
                .select_from(AssistantMessage)
                .join(AssistantSession)
                .where(
                    AssistantSession.owner_hash == owner,
                    AssistantMessage.created_at > utcnow() - timedelta(minutes=1),
                )
            )
            or 0
        )
        if count >= 10:
            raise AppError(429, "RATE_LIMIT", "Too many explanation requests")
    result = answer(db, dataset_id, inputs, owner)
    db.commit()
    return result
