import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from stockpilot.api.routers.planning import csv_text
from stockpilot.api.schemas import ScenarioInput
from stockpilot.config import settings
from stockpilot.domain.assistant.tools import Arguments
from stockpilot.main import app


def test_public_demo_direct_write_endpoints_block(monkeypatch):
    monkeypatch.setattr(settings, "app_mode", "public_demo")
    client = TestClient(app)
    response = client.post("/api/v1/datasets/unused/forecast-runs", json={"horizon": 28})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "READ_ONLY_DEMO"
    response = client.post(
        "/api/v1/recommendation-items/unused/decisions?dataset_id=unused",
        json={"action": "accepted", "expected_version": 0},
    )
    assert response.status_code == 403


def test_live_health_does_not_require_database():
    assert TestClient(app).get("/api/v1/health/live").json() == {"status": "alive"}


def test_invalid_enums_size_and_tool_arguments():
    with pytest.raises(ValidationError):
        ScenarioInput(base_run_id="id", demand_multiplier=9)
    with pytest.raises(ValidationError):
        Arguments(identifier="p", sql="DROP TABLE products")
    response = TestClient(app).get("/api/v1/datasets?page_size=101")
    assert response.status_code == 422
    assert "request_id" in response.json()["error"]


def test_csv_formula_neutralization():
    assert csv_text("=SUM(A1)").startswith("'")
    assert csv_text(" +cmd").startswith("'")
    assert csv_text("Ceramic mug") == "Ceramic mug"
