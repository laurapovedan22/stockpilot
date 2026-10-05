from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("service_level", check_fields=False)
    @classmethod
    def supported_service_level(cls, value: float) -> float:
        if value not in (0.90, 0.95, 0.99):
            raise ValueError("Service level must be 0.90, 0.95 or 0.99")
        return value


class DatasetInput(StrictSchema):
    name: str = Field(min_length=1, max_length=120)
    as_of_date: date
    source: str = Field(default="User-supplied CSV", min_length=1, max_length=300)
    currency: Literal["GBP"] = "GBP"
    timezone: Literal["Europe/London"] = "Europe/London"


class ForecastInput(StrictSchema):
    cutoff_date: date | None = None
    horizon: int = Field(default=42, ge=1, le=42)


class Policy(StrictSchema):
    service_level: float = 0.95
    review_days: int = Field(default=7, ge=1, le=14)


class RecommendationInput(StrictSchema):
    forecast_run_id: str
    snapshot_id: str
    policy: Policy = Field(default_factory=Policy)
    budget: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class ScenarioInput(StrictSchema):
    base_run_id: str
    name: str = Field(default="Untitled scenario", min_length=1, max_length=120)
    demand_multiplier: float = Field(default=1, ge=0.5, le=2)
    lead_time_delay_days: int = Field(default=0, ge=0, le=14)
    horizon_days: int = Field(default=28, ge=7, le=28)
    service_level: float = 0.95
    budget: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    seed: int = Field(default=42, ge=0, le=2147483647)


class ConfirmInput(StrictSchema):
    token: str
    excluded_rows: list[int] = Field(default_factory=list, max_length=100000)
    idempotency_key: str = Field(min_length=1, max_length=120)
    last_day_complete: bool = False


class DecisionInput(StrictSchema):
    action: Literal["accepted", "rejected", "adjusted"]
    final_units: int | None = Field(default=None, ge=0)
    reason: str = Field(default="", max_length=1000)
    expected_version: int = Field(ge=0)


class InventoryInput(StrictSchema):
    expected_version: int = Field(ge=1)
    on_hand: int = Field(ge=0)
    reserved: int = Field(ge=0)


class AssistantInput(StrictSchema):
    session_id: str | None = None
    text: str = Field(min_length=1, max_length=2000)
    context_ids: list[str] = Field(default_factory=list, max_length=4)
