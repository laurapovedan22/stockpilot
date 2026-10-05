from sqlalchemy.orm import Session

from stockpilot.db.models import Job
from stockpilot.services.forecasts import train
from stockpilot.services.imports import apply_import
from stockpilot.services.scenarios import create_scenario


def handle(session: Session, job: Job) -> str:
    if job.kind == "import":
        return apply_import(
            session,
            job.payload["batch_id"],
            job.payload["excluded_rows"],
            job.payload["last_day_complete"],
        )
    if job.kind == "forecast":
        return train(
            session, job.dataset_id, job.payload.get("cutoff_date"), job.payload["horizon"]
        )
    if job.kind == "scenario":
        return create_scenario(session, job.dataset_id, job.payload, job.owner_hash)
    raise ValueError("Unsupported job kind")
