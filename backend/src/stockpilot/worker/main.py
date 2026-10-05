import logging
import threading
import time
from datetime import timedelta

from sqlalchemy import select, update

from stockpilot.api.errors import AppError
from stockpilot.db.models import Job, utcnow
from stockpilot.db.session import SessionFactory
from stockpilot.worker.handlers import handle
from stockpilot.worker.queue import claim, dataset_lock

logger = logging.getLogger("stockpilot.worker")


def heartbeat(identifier: str, owner: str, stop: threading.Event) -> None:
    while not stop.wait(15):
        with SessionFactory.begin() as session:
            session.execute(
                update(Job)
                .where(Job.id == identifier, Job.owner == owner, Job.status == "running")
                .values(lease_until=utcnow() + timedelta(seconds=60))
            )


def run_once() -> bool:
    with SessionFactory.begin() as session:
        job = claim(session)
        if job is None:
            return False
        identifier, owner = job.id, job.owner
    stop = threading.Event()
    thread = threading.Thread(target=heartbeat, args=(identifier, owner, stop), daemon=True)
    thread.start()
    try:
        with SessionFactory.begin() as session:
            job = session.get(Job, identifier)
            assert job is not None
            dataset_lock(session, job.dataset_id)
            result_id = handle(session, job)
            # Owner fencing prevents an expired worker from publishing after reclamation.
            current_owner = session.execute(
                select(Job.owner).where(Job.id == identifier).with_for_update()
            ).scalar_one()
            if current_owner != owner:
                raise RuntimeError("Lease ownership lost")
            job.result_id, job.status, job.stage, job.progress = (
                result_id,
                "succeeded",
                "completed",
                100,
            )
            job.lease_until = None
        logger.info("job_completed", extra={"job_id": identifier})
    except Exception as exc:
        logger.exception("job_failed", extra={"job_id": identifier})
        with SessionFactory.begin() as session:
            current = session.get(Job, identifier)
            assert current is not None
            if current.owner == owner:
                validation = isinstance(exc, (ValueError, AppError))
                current.status = "failed" if validation or current.attempts >= 2 else "queued"
                current.stage = current.status
                current.error = (
                    str(exc)[:400] if validation else "Processing failed; consult local worker logs"
                )
                current.lease_until = None
    finally:
        stop.set()
        thread.join(timeout=2)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    maintenance_at = 0.0
    while True:
        try:
            if time.monotonic() >= maintenance_at:
                from stockpilot.services.maintenance import cleanup

                with SessionFactory.begin() as session:
                    cleanup(session)
                maintenance_at = time.monotonic() + 3600
            if not run_once():
                time.sleep(1)
        except Exception:
            logger.exception("queue_unavailable")
            time.sleep(5)


if __name__ == "__main__":
    main()
