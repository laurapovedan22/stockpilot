import hashlib

import pytest
from fastapi.testclient import TestClient

from stockpilot.config import settings
from stockpilot.db.models import AssistantSession, Job, Product
from stockpilot.db.session import get_session
from stockpilot.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db):
    def database():
        yield db

    app.dependency_overrides[get_session] = database
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


def test_create_dataset_and_read_summary_contract(client):
    response = client.post(
        "/api/v1/datasets",
        json={"name": "Own observations", "as_of_date": "2025-01-01"},
    )
    assert response.status_code == 201
    dataset = response.json()
    assert dataset["mode"] == "historical"
    assert dataset["provenance"]["operations"] == "Not imported"
    result = client.get(f"/api/v1/datasets/{dataset['id']}/summary").json()
    assert result["dataset"]["id"] == dataset["id"]
    assert result["snapshot"] is None
    assert result["recommended_cost"] is None
    assert result["active_products"] == 0


def test_planning_product_filter_includes_active_skus_beyond_first_catalog_page(
    client, db, dataset
):
    db.add_all(
        [
            Product(
                dataset_id=dataset.id,
                sku=f"{index:05d}",
                description="Outside planning",
                active=False,
            )
            for index in range(30)
        ]
    )
    planned = Product(
        dataset_id=dataset.id, sku="99999", description="Selected product", active=True
    )
    db.add(planned)
    db.flush()
    response = client.get(f"/api/v1/datasets/{dataset.id}/products?active=true&page_size=100")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == planned.id


def test_public_cookie_and_job_conversation_isolation(client, db, dataset, monkeypatch):
    monkeypatch.setattr(settings, "app_mode", "public_demo")
    session = client.post("/api/v1/session")
    assert session.status_code == 200
    assert "HttpOnly" in session.headers["set-cookie"]
    token = client.cookies.get("stockpilot_session")
    owner = hashlib.sha256(token.encode()).hexdigest()
    job = Job(dataset_id=dataset.id, kind="scenario", key="owned", payload={}, owner_hash=owner)
    conversation = AssistantSession(dataset_id=dataset.id, owner_hash=owner)
    db.add_all([job, conversation])
    db.flush()
    url = f"/api/v1/jobs/{job.id}?dataset_id={dataset.id}"
    assert client.get(url).status_code == 200
    client.cookies.clear()
    client.post("/api/v1/session")
    assert client.get(url).status_code == 404
    answer = client.post(
        f"/api/v1/datasets/{dataset.id}/assistant/messages",
        json={"session_id": conversation.id, "text": "What is the buying policy?"},
    )
    assert answer.status_code == 404
    create = client.post("/api/v1/datasets", json={"name": "Forbidden", "as_of_date": "2025-01-01"})
    assert create.status_code == 403
