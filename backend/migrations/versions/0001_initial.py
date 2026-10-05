"""Initial relational schema and append-only decision guard."""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(Path(__file__).resolve().parents[1].joinpath("0001.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TRIGGER decisions_append_only ON decisions")
    op.execute("DROP FUNCTION prevent_decision_mutation()")
    op.execute(
        "DROP TABLE assistant_messages, assistant_sessions, policy_chunks, policy_documents, jobs, scenario_daily_results, scenario_runs, decisions, recommendation_items, recommendation_runs, evaluation_results, forecast_points, forecast_runs, inbound_orders, inventory_items, inventory_snapshots, daily_sales, sales_transactions, import_batches, suppliers, products, datasets"
    )
