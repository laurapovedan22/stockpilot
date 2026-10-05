import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from stockpilot.api.errors import AppError
from stockpilot.api.schemas import AssistantInput
from stockpilot.config import settings
from stockpilot.db.models import (
    AssistantMessage,
    AssistantSession,
    Dataset,
    ForecastRun,
    Job,
    Product,
    RecommendationRun,
    ScenarioDaily,
    ScenarioRun,
    Snapshot,
    utcnow,
)
from stockpilot.db.session import get_session
from stockpilot.domain.assistant.tools import Arguments, invoke
from stockpilot.main import app
from stockpilot.services.assistant import answer
from stockpilot.services.maintenance import cleanup
from stockpilot.worker.queue import claim

pytestmark = pytest.mark.integration
TOKEN = "ab" * 32
OWNER = hashlib.sha256(TOKEN.encode()).hexdigest()


def base_plan(db, dataset):
    snapshot = Snapshot(
        dataset_id=dataset.id, as_of_date=dataset.as_of_date, version=1, origin="fixture"
    )
    forecast = ForecastRun(
        dataset_id=dataset.id,
        cutoff_date=dataset.as_of_date,
        horizon=42,
        model="moving_average",
        metrics={},
        checksum="fixture",
        artifact_path="fixture",
    )
    db.add_all([snapshot, forecast])
    db.flush()
    run = RecommendationRun(forecast_run_id=forecast.id, snapshot_id=snapshot.id, policy={})
    db.add(run)
    db.flush()
    return run


@pytest.fixture
def public_database(monkeypatch):
    """Committed fixtures on the dedicated test DB let independent requests contend."""
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required: use real migrated PostgreSQL")
    engine = create_engine(url)
    monkeypatch.setattr(settings, "app_mode", "public_demo")
    with Session(engine, expire_on_commit=False) as db, db.begin():
        datasets = [
            Dataset(
                name=f"Concurrent fixture {uuid4()}",
                mode="synthetic",
                as_of_date=date(2025, 12, 31),
                provenance={"source": "test"},
            )
            for _ in range(2)
        ]
        db.add_all(datasets)
        db.flush()
        plans = [base_plan(db, dataset) for dataset in datasets]
        ids, run_ids = [d.id for d in datasets], [p.id for p in plans]

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = database
    try:
        yield engine, ids, run_ids
    finally:
        app.dependency_overrides.pop(get_session, None)
        # Remove only this fixture's committed rows; never reset the shared database.
        with Session(engine) as db, db.begin():
            conversations = select(AssistantSession.id).where(AssistantSession.dataset_id.in_(ids))
            db.execute(
                delete(AssistantMessage).where(AssistantMessage.session_id.in_(conversations))
            )
            db.execute(delete(AssistantSession).where(AssistantSession.dataset_id.in_(ids)))
            db.execute(delete(Job).where(Job.dataset_id.in_(ids)))
            db.execute(delete(RecommendationRun).where(RecommendationRun.id.in_(run_ids)))
            db.execute(delete(ForecastRun).where(ForecastRun.dataset_id.in_(ids)))
            db.execute(delete(Snapshot).where(Snapshot.dataset_id.in_(ids)))
            db.execute(delete(Dataset).where(Dataset.id.in_(ids)))
        engine.dispose()


def parallel_requests(ids, run_ids, endpoint):
    barrier = threading.Barrier(6)

    def send(index):
        with TestClient(app) as client:
            client.cookies.set("stockpilot_session", TOKEN)
            payload = (
                {"base_run_id": run_ids[index % 2], "name": f"Concurrent {index}"}
                if endpoint == "scenario-runs"
                else {"text": "unknown policy source"}
            )
            barrier.wait(timeout=10)
            response = client.post(f"/api/v1/datasets/{ids[index % 2]}/{endpoint}", json=payload)
            return response.status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(send, range(6)))


def test_global_scenario_cap_is_atomic_across_datasets(public_database):
    engine, ids, run_ids = public_database
    statuses = parallel_requests(ids, run_ids, "scenario-runs")
    assert sorted(statuses) == [202, 202, 429, 429, 429, 429]
    with Session(engine) as db:
        jobs = db.scalars(select(Job).where(Job.dataset_id.in_(ids))).all()
        assert len(jobs) == 2
        assert all(job.owner_hash == OWNER for job in jobs)


def test_scenario_submission_limit_counts_completed_jobs_and_is_owner_scoped(public_database):
    engine, ids, run_ids = public_database
    with Session(engine) as db, db.begin():
        db.add_all(
            [
                Job(
                    dataset_id=ids[index % 2],
                    kind="scenario",
                    key=f"recent-{index}",
                    payload={},
                    status="succeeded",
                    owner_hash=OWNER,
                )
                for index in range(3)
            ]
        )
    with TestClient(app) as client:
        client.cookies.set("stockpilot_session", TOKEN)
        url = f"/api/v1/datasets/{ids[1]}/scenario-runs"
        assert client.post(url, json={"base_run_id": run_ids[1]}).status_code == 429
        client.cookies.set("stockpilot_session", "cd" * 32)
        assert client.post(url, json={"base_run_id": run_ids[1]}).status_code == 202


def test_assistant_rate_limit_is_atomic_across_datasets(public_database):
    engine, ids, run_ids = public_database
    with Session(engine) as db, db.begin():
        conversation = AssistantSession(dataset_id=ids[0], owner_hash=OWNER)
        db.add(conversation)
        db.flush()
        db.add_all(
            [
                AssistantMessage(
                    session_id=conversation.id, question="fixture", answer="fixture", references=[]
                )
                for _ in range(8)
            ]
        )
    statuses = parallel_requests(ids, run_ids, "assistant/messages")
    assert sorted(statuses) == [200, 200, 429, 429, 429, 429]


def test_cleanup_skips_a_conversation_locked_by_an_active_request(
    public_database, monkeypatch, tmp_path
):
    engine, ids, _ = public_database
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    with Session(engine) as db, db.begin():
        conversation = AssistantSession(
            dataset_id=ids[0], owner_hash=OWNER, created_at=utcnow() - timedelta(hours=25)
        )
        db.add(conversation)
        db.flush()
        identifier = conversation.id
    with Session(engine) as active, active.begin():
        active.scalar(
            select(AssistantSession).where(AssistantSession.id == identifier).with_for_update()
        )
        with Session(engine) as maintenance, maintenance.begin():
            cleanup(maintenance)
            assert maintenance.get(AssistantSession, identifier) is not None
    with Session(engine) as maintenance, maintenance.begin():
        cleanup(maintenance)
        assert maintenance.get(AssistantSession, identifier) is None


def test_expired_public_resources_are_hidden_before_cleanup(db, dataset, monkeypatch):
    monkeypatch.setattr(settings, "app_mode", "public_demo")
    past = utcnow() - timedelta(hours=25)
    plan = base_plan(db, dataset)
    scenario = ScenarioRun(
        base_run_id=plan.id,
        name="Expired",
        inputs={},
        results={},
        owner_hash=OWNER,
        expires_at=past,
    )
    conversation = AssistantSession(dataset_id=dataset.id, owner_hash=OWNER, created_at=past)
    job = Job(
        dataset_id=dataset.id,
        kind="scenario",
        key="expired-public",
        payload={},
        owner_hash=OWNER,
        created_at=past,
    )
    db.add_all([scenario, conversation, job])
    db.flush()
    with pytest.raises(AppError) as error:
        invoke(db, dataset.id, "get_scenario_result", Arguments(identifier=scenario.id), OWNER)
    assert error.value.status == 404
    with pytest.raises(AppError) as error:
        answer(db, dataset.id, AssistantInput(session_id=conversation.id, text="policy"), OWNER)
    assert error.value.status == 404
    assert claim(db) is None
    db.refresh(job)
    assert job.status == "failed"
    assert job.error == "Demo session expired"

    def database():
        yield db

    app.dependency_overrides[get_session] = database
    try:
        with TestClient(app) as client:
            client.cookies.set("stockpilot_session", TOKEN)
            assert (
                client.get(
                    f"/api/v1/scenario-runs/{scenario.id}?dataset_id={dataset.id}"
                ).status_code
                == 404
            )
            assert client.get(f"/api/v1/jobs/{job.id}?dataset_id={dataset.id}").status_code == 404
            assert (
                client.get(f"/api/v1/datasets/{dataset.id}/summary").json()["last_scenario"] is None
            )
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_cleanup_deletes_expired_children_and_preserves_local_data(
    db, dataset, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    past = utcnow() - timedelta(hours=25)
    plan = base_plan(db, dataset)
    product = Product(dataset_id=dataset.id, sku="CLEANUP", description="Fixture")
    expired = ScenarioRun(
        base_run_id=plan.id,
        name="Expired",
        inputs={},
        results={},
        owner_hash=OWNER,
        expires_at=past,
    )
    local = ScenarioRun(base_run_id=plan.id, name="Local", inputs={}, results={})
    old = AssistantSession(dataset_id=dataset.id, owner_hash=OWNER, created_at=past)
    local_chat = AssistantSession(dataset_id=dataset.id, created_at=past)
    db.add_all([product, expired, local, old, local_chat])
    db.flush()
    db.add_all(
        [
            ScenarioDaily(
                scenario_id=expired.id,
                product_id=product.id,
                day=dataset.as_of_date,
                policy="no_purchase",
                values={},
            ),
            AssistantMessage(session_id=old.id, question="old", answer="old", references=[]),
        ]
    )
    db.flush()
    cleanup(db)
    db.expire_all()
    assert db.get(ScenarioRun, expired.id) is None
    assert db.scalar(select(ScenarioDaily).where(ScenarioDaily.scenario_id == expired.id)) is None
    assert db.get(AssistantSession, old.id) is None
    assert db.scalar(select(AssistantMessage).where(AssistantMessage.session_id == old.id)) is None
    assert db.get(ScenarioRun, local.id) is not None
    assert db.get(AssistantSession, local_chat.id) is not None
