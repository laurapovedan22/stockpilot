from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from stockpilot.config import settings
from stockpilot.db.models import (
    AssistantMessage,
    AssistantSession,
    ImportBatch,
    Job,
    ScenarioDaily,
    ScenarioRun,
    utcnow,
)


def cleanup(session: Session) -> None:
    now = utcnow()
    root = Path(settings.upload_dir).resolve()
    for batch in session.scalars(select(ImportBatch).where(ImportBatch.expires_at < now)):
        path = Path(batch.path).resolve()
        if path.is_relative_to(root) and path.suffix == ".csv":
            path.unlink(missing_ok=True)
    expired = list(
        session.scalars(
            select(ScenarioRun.id)
            .where(ScenarioRun.expires_at <= now)
            .with_for_update(skip_locked=True)
        )
    )
    if expired:
        session.execute(delete(ScenarioDaily).where(ScenarioDaily.scenario_id.in_(expired)))
        session.execute(delete(ScenarioRun).where(ScenarioRun.id.in_(expired)))
    conversations = list(
        session.scalars(
            select(AssistantSession.id)
            .where(
                AssistantSession.owner_hash.is_not(None),
                AssistantSession.created_at <= now - timedelta(hours=24),
            )
            .with_for_update(skip_locked=True)
        )
    )
    if conversations:
        session.execute(
            delete(AssistantMessage).where(AssistantMessage.session_id.in_(conversations))
        )
        session.execute(delete(AssistantSession).where(AssistantSession.id.in_(conversations)))
    session.execute(
        delete(Job).where(
            Job.owner_hash.is_not(None),
            Job.created_at < now - timedelta(hours=24),
            Job.status.in_(["succeeded", "failed"]),
        )
    )
