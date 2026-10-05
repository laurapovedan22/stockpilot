import hashlib
import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from stockpilot.api.errors import AppError
from stockpilot.db.models import DailySale, Job, Product, utcnow


def dataset_lock(session: Session, dataset_id: str) -> None:
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": dataset_id})


def enqueue(
    session: Session,
    dataset_id: str,
    kind: str,
    payload: dict,
    owner_hash: str | None = None,
    key: str | None = None,
) -> Job:
    dataset_lock(session, dataset_id)
    if kind == "forecast":
        checksum = hashlib.sha256()
        rows = session.execute(
            select(DailySale.product_id, DailySale.day, DailySale.units)
            .join(Product)
            .where(Product.dataset_id == dataset_id)
            .order_by(DailySale.product_id, DailySale.day)
        )
        for product_id, day, units in rows:
            checksum.update(f"{product_id}:{day}:{units}\n".encode())
        payload = {**payload, "data_checksum": checksum.hexdigest()}
    digest = (
        key
        or hashlib.sha256(
            (kind + json.dumps(payload, sort_keys=True) + str(owner_hash)).encode()
        ).hexdigest()
    )
    existing = session.scalar(select(Job).where(Job.dataset_id == dataset_id, Job.key == digest))
    if existing:
        return existing
    if kind in ("import", "forecast"):
        busy = session.scalar(
            select(Job).where(
                Job.dataset_id == dataset_id,
                Job.kind.in_(["import", "forecast"]),
                Job.status.in_(["queued", "running"]),
            )
        )
        if busy:
            raise AppError(409, "DATASET_BUSY", "An import or training job is already active")
    job = Job(dataset_id=dataset_id, kind=kind, key=digest, payload=payload, owner_hash=owner_hash)
    session.add(job)
    session.flush()
    return job


def claim(session: Session) -> Job | None:
    now = utcnow()
    session.execute(
        update(Job)
        .where(
            Job.owner_hash.is_not(None),
            Job.created_at <= now - timedelta(hours=24),
            or_(Job.status == "queued", (Job.status == "running") & (Job.lease_until < now)),
        )
        .values(status="failed", stage="failed", error="Demo session expired", lease_until=None)
    )
    session.execute(
        update(Job)
        .where(Job.status == "running", Job.lease_until < now, Job.attempts >= 2)
        .values(
            status="failed", error="Worker lease expired after maximum attempts", stage="failed"
        )
    )
    job = session.scalar(
        select(Job)
        .where(
            or_(Job.status == "queued", (Job.status == "running") & (Job.lease_until < now)),
            Job.attempts < 2,
        )
        .order_by(Job.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job:
        job.status = "running"
        job.attempts += 1
        job.owner = str(uuid4())
        job.lease_until = now + timedelta(seconds=60)
        job.stage = "loading inputs"
        job.progress = 5
    return job
