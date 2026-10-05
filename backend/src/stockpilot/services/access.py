from sqlalchemy.orm import Session

from stockpilot.api.errors import AppError
from stockpilot.db.models import RecommendationRun, ScenarioRun, utcnow
from stockpilot.db.repositories import get, scoped


def owned_scenario(
    session: Session, identifier: str, dataset_id: str, owner_hash: str | None
) -> ScenarioRun:
    run = get(session, ScenarioRun, identifier)
    scoped(session, RecommendationRun, run.base_run_id, dataset_id)
    if run.owner_hash != owner_hash or (run.expires_at and run.expires_at <= utcnow()):
        raise AppError(404, "NOT_FOUND", "Scenario not found")
    return run
