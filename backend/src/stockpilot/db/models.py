from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Identity:
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Dataset(Identity, Base):
    __tablename__ = "datasets"
    name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    timezone: Mapped[str] = mapped_column(String(60), default="Europe/London")
    as_of_date: Mapped[date] = mapped_column(Date)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    seed: Mapped[int | None] = mapped_column(Integer)


class Product(Identity, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("dataset_id", "sku"),)
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("datasets.id"), index=True
    )
    sku: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Supplier(Identity, Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("dataset_id", "code"),)
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("datasets.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    provenance: Mapped[str] = mapped_column(String(30), default="simulated")


class ImportBatch(Identity, Base):
    __tablename__ = "import_batches"
    __table_args__ = (UniqueConstraint("dataset_id", "key"),)
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("datasets.id"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))
    checksum: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(20))
    mapping: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="preview")
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    path: Mapped[str] = mapped_column(String(500))


class Sale(Identity, Base):
    __tablename__ = "sales_transactions"
    __table_args__ = (UniqueConstraint("dataset_id", "external_row_id"),)
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("datasets.id"), index=True
    )
    batch_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("import_batches.id")
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("products.id"), index=True
    )
    external_row_id: Mapped[str] = mapped_column(String(160))
    invoice_id: Mapped[str] = mapped_column(String(120))
    invoice_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    day: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    cancellation: Mapped[bool] = mapped_column(Boolean, default=False)
    country: Mapped[str] = mapped_column(String(80), default="")


class DailySale(Base):
    __tablename__ = "daily_sales"
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("products.id"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    units: Mapped[int] = mapped_column(Integer)


class Snapshot(Identity, Base):
    __tablename__ = "inventory_snapshots"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("datasets.id"), index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(40))


class InventoryItem(Identity, Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "product_id"),
        CheckConstraint("on_hand >= reserved AND reserved >= 0"),
        CheckConstraint("unit_cost >= 0 AND pack_size >= 1 AND minimum_order_units >= 0"),
        CheckConstraint("lead_time_days BETWEEN 1 AND 30"),
    )
    snapshot_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("inventory_snapshots.id"), index=True
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("products.id"), index=True
    )
    supplier_code: Mapped[str] = mapped_column(String(80))
    on_hand: Mapped[int] = mapped_column(Integer)
    reserved: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    lead_time_days: Mapped[int] = mapped_column(Integer)
    pack_size: Mapped[int] = mapped_column(Integer)
    minimum_order_units: Mapped[int] = mapped_column(Integer)
    holding_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    stockout_penalty: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    provenance: Mapped[str] = mapped_column(String(40), default="simulated")


class Inbound(Identity, Base):
    __tablename__ = "inbound_orders"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "external_order_id"),
        CheckConstraint("quantity > 0"),
    )
    snapshot_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("inventory_snapshots.id"), index=True
    )
    product_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("products.id"))
    external_order_id: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int] = mapped_column(Integer)
    arrival: Mapped[date] = mapped_column(Date)


class ForecastRun(Identity, Base):
    __tablename__ = "forecast_runs"
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("datasets.id"), index=True
    )
    cutoff_date: Mapped[date] = mapped_column(Date)
    horizon: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(40))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    checksum: Mapped[str] = mapped_column(String(64))
    artifact_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="succeeded")


class ForecastPoint(Base):
    __tablename__ = "forecast_points"
    run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("forecast_runs.id"), primary_key=True
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("products.id"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    yhat: Mapped[float] = mapped_column(Numeric(16, 6))
    lower: Mapped[float | None] = mapped_column(Numeric(16, 6))
    upper: Mapped[float | None] = mapped_column(Numeric(16, 6))


class EvaluationResult(Identity, Base):
    __tablename__ = "evaluation_results"
    run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("forecast_runs.id"), index=True
    )
    fold: Mapped[str] = mapped_column(String(30))
    product_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("products.id"))
    model: Mapped[str] = mapped_column(String(40))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)


class RecommendationRun(Identity, Base):
    __tablename__ = "recommendation_runs"
    forecast_run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("forecast_runs.id"), index=True
    )
    snapshot_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("inventory_snapshots.id")
    )
    policy: Mapped[dict[str, Any]] = mapped_column(JSONB)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class RecommendationItem(Identity, Base):
    __tablename__ = "recommendation_items"
    run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recommendation_runs.id"), index=True
    )
    product_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("products.id"))
    requested_units: Mapped[int] = mapped_column(Integer)
    allocated_units: Mapped[int] = mapped_column(Integer)
    cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    risk: Mapped[float | None] = mapped_column(Numeric(8, 6))


class Decision(Identity, Base):
    __tablename__ = "decisions"
    item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recommendation_items.id"), index=True
    )
    action: Mapped[str] = mapped_column(String(20))
    final_units: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(1000))
    actor: Mapped[str] = mapped_column(String(60), default="local")
    version: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("item_id", "version"), CheckConstraint("final_units >= 0"))


class ScenarioRun(Identity, Base):
    __tablename__ = "scenario_runs"
    base_run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("recommendation_runs.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    results: Mapped[dict[str, Any]] = mapped_column(JSONB)
    owner_hash: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScenarioDaily(Identity, Base):
    __tablename__ = "scenario_daily_results"
    scenario_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("scenario_runs.id"), index=True
    )
    policy: Mapped[str] = mapped_column(String(40))
    product_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("products.id"))
    day: Mapped[date] = mapped_column(Date)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Job(Identity, Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("dataset_id", "key"),)
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("datasets.id"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    key: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(80), default="queued")
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner: Mapped[str | None] = mapped_column(String(36))
    result_id: Mapped[str | None] = mapped_column(String(36))
    error: Mapped[str | None] = mapped_column(String(500))
    owner_hash: Mapped[str | None] = mapped_column(String(64))


class PolicyDocument(Identity, Base):
    __tablename__ = "policy_documents"
    title: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(300), unique=True)
    checksum: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(String)


class PolicyChunk(Identity, Base):
    __tablename__ = "policy_chunks"
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("policy_documents.id"), index=True
    )
    section: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(String)


class AssistantSession(Identity, Base):
    __tablename__ = "assistant_sessions"
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("datasets.id"), index=True
    )
    owner_hash: Mapped[str | None] = mapped_column(String(64))


class AssistantMessage(Identity, Base):
    __tablename__ = "assistant_messages"
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("assistant_sessions.id"), index=True
    )
    question: Mapped[str] = mapped_column(String(2000))
    answer: Mapped[str] = mapped_column(String)
    references: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
