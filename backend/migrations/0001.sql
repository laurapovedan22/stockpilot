CREATE TABLE datasets (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, name varchar(120) NOT NULL,
 mode varchar(20) NOT NULL CHECK (mode IN ('synthetic','historical')), currency varchar(3) NOT NULL,
 timezone varchar(60) NOT NULL, as_of_date date NOT NULL, provenance jsonb NOT NULL, seed integer
);
CREATE TABLE products (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets,
 sku varchar(80) NOT NULL, description varchar(300) NOT NULL, active boolean NOT NULL,
 provenance jsonb NOT NULL, UNIQUE(dataset_id,sku)
);
CREATE INDEX ix_products_dataset_id ON products(dataset_id);
CREATE TABLE suppliers (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets,
 code varchar(80) NOT NULL, name varchar(120) NOT NULL, provenance varchar(30) NOT NULL,
 UNIQUE(dataset_id,code)
);
CREATE INDEX ix_suppliers_dataset_id ON suppliers(dataset_id);
CREATE TABLE import_batches (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets,
 key varchar(64) NOT NULL, checksum varchar(64) NOT NULL, kind varchar(20) NOT NULL,
 mapping jsonb NOT NULL, status varchar(20) NOT NULL, report jsonb NOT NULL,
 expires_at timestamptz NOT NULL, path varchar(500) NOT NULL, UNIQUE(dataset_id,key)
);
CREATE INDEX ix_import_batches_dataset_id ON import_batches(dataset_id);
CREATE TABLE sales_transactions (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets,
 batch_id uuid REFERENCES import_batches, product_id uuid NOT NULL REFERENCES products,
 external_row_id varchar(160) NOT NULL, invoice_id varchar(120) NOT NULL,
 invoice_datetime timestamptz NOT NULL, day date NOT NULL, quantity integer NOT NULL,
 unit_price numeric(14,4) NOT NULL, cancellation boolean NOT NULL, country varchar(80) NOT NULL, UNIQUE(dataset_id,external_row_id)
);
CREATE INDEX ix_sales_transactions_dataset_id ON sales_transactions(dataset_id);
CREATE INDEX ix_sales_transactions_product_id ON sales_transactions(product_id);
CREATE INDEX ix_sales_transactions_day ON sales_transactions(day);
CREATE TABLE daily_sales (
 product_id uuid NOT NULL REFERENCES products, day date NOT NULL, units integer NOT NULL CHECK(units >= 0),
 PRIMARY KEY(product_id,day)
);
CREATE TABLE inventory_snapshots (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets,
 as_of_date date NOT NULL, version integer NOT NULL, origin varchar(40) NOT NULL,
 UNIQUE(dataset_id,version)
);
CREATE INDEX ix_inventory_snapshots_dataset_id ON inventory_snapshots(dataset_id);
CREATE TABLE inventory_items (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, snapshot_id uuid NOT NULL REFERENCES inventory_snapshots,
 product_id uuid NOT NULL REFERENCES products, supplier_code varchar(80) NOT NULL,
 on_hand integer NOT NULL, reserved integer NOT NULL, unit_cost numeric(14,4) NOT NULL,
 lead_time_days integer NOT NULL, pack_size integer NOT NULL, minimum_order_units integer NOT NULL,
 holding_cost numeric(14,4) NOT NULL, stockout_penalty numeric(14,4) NOT NULL, provenance varchar(40) NOT NULL,
 UNIQUE(snapshot_id,product_id), CHECK(on_hand >= reserved AND reserved >= 0),
 CHECK(unit_cost >= 0 AND pack_size >= 1 AND minimum_order_units >= 0),
 CHECK(lead_time_days BETWEEN 1 AND 30)
);
CREATE INDEX ix_inventory_items_snapshot_id ON inventory_items(snapshot_id);
CREATE INDEX ix_inventory_items_product_id ON inventory_items(product_id);
CREATE TABLE inbound_orders (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, snapshot_id uuid NOT NULL REFERENCES inventory_snapshots,
 product_id uuid NOT NULL REFERENCES products, external_order_id varchar(160) NOT NULL,
 quantity integer NOT NULL CHECK(quantity > 0), arrival date NOT NULL, UNIQUE(snapshot_id,external_order_id)
);
CREATE INDEX ix_inbound_orders_snapshot_id ON inbound_orders(snapshot_id);
CREATE TABLE forecast_runs (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets,
 cutoff_date date NOT NULL, horizon integer NOT NULL CHECK(horizon BETWEEN 1 AND 42),
 model varchar(40) NOT NULL, metrics jsonb NOT NULL, checksum varchar(64) NOT NULL,
 artifact_path varchar(500) NOT NULL, status varchar(20) NOT NULL
);
CREATE INDEX ix_forecast_runs_dataset_id ON forecast_runs(dataset_id);
CREATE TABLE forecast_points (
 run_id uuid NOT NULL REFERENCES forecast_runs, product_id uuid NOT NULL REFERENCES products,
 day date NOT NULL, yhat numeric(16,6) NOT NULL CHECK(yhat >= 0), lower numeric(16,6), upper numeric(16,6),
 PRIMARY KEY(run_id,product_id,day), CHECK(lower IS NULL OR lower <= yhat), CHECK(upper IS NULL OR upper >= yhat)
);
CREATE TABLE evaluation_results (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, run_id uuid NOT NULL REFERENCES forecast_runs,
 fold varchar(30) NOT NULL, product_id uuid REFERENCES products, model varchar(40) NOT NULL, metrics jsonb NOT NULL
);
CREATE INDEX ix_evaluation_results_run_id ON evaluation_results(run_id);
CREATE TABLE recommendation_runs (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, forecast_run_id uuid NOT NULL REFERENCES forecast_runs,
 snapshot_id uuid NOT NULL REFERENCES inventory_snapshots, policy jsonb NOT NULL, budget numeric(14,2)
);
CREATE INDEX ix_recommendation_runs_forecast_run_id ON recommendation_runs(forecast_run_id);
CREATE TABLE recommendation_items (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, run_id uuid NOT NULL REFERENCES recommendation_runs,
 product_id uuid NOT NULL REFERENCES products, requested_units integer NOT NULL CHECK(requested_units >= 0),
 allocated_units integer NOT NULL CHECK(allocated_units >= 0 AND allocated_units <= requested_units),
 cost numeric(14,2) NOT NULL, explanation jsonb NOT NULL, risk numeric(8,6), CHECK(risk BETWEEN 0 AND 1)
);
CREATE INDEX ix_recommendation_items_run_id ON recommendation_items(run_id);
CREATE TABLE decisions (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, item_id uuid NOT NULL REFERENCES recommendation_items,
 action varchar(20) NOT NULL CHECK(action IN ('accepted','rejected','adjusted')),
 final_units integer NOT NULL CHECK(final_units >= 0), reason varchar(1000) NOT NULL,
 actor varchar(60) NOT NULL, version integer NOT NULL, UNIQUE(item_id,version)
);
CREATE INDEX ix_decisions_item_id ON decisions(item_id);
CREATE TABLE scenario_runs (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, base_run_id uuid NOT NULL REFERENCES recommendation_runs,
 name varchar(120) NOT NULL, inputs jsonb NOT NULL, results jsonb NOT NULL,
 owner_hash varchar(64), expires_at timestamptz
);
CREATE INDEX ix_scenario_runs_base_run_id ON scenario_runs(base_run_id);
CREATE TABLE scenario_daily_results (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, scenario_id uuid NOT NULL REFERENCES scenario_runs,
 policy varchar(40) NOT NULL, product_id uuid NOT NULL REFERENCES products, day date NOT NULL, "values" jsonb NOT NULL
);
CREATE INDEX ix_scenario_daily_results_scenario_id ON scenario_daily_results(scenario_id);
CREATE TABLE jobs (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets,
 kind varchar(40) NOT NULL, key varchar(64) NOT NULL, payload jsonb NOT NULL,
 status varchar(20) NOT NULL CHECK(status IN ('queued','running','succeeded','failed')),
 attempts integer NOT NULL CHECK(attempts BETWEEN 0 AND 2), progress integer NOT NULL,
 stage varchar(80) NOT NULL, lease_until timestamptz, owner varchar(36), result_id varchar(36),
 error varchar(500), owner_hash varchar(64), UNIQUE(dataset_id,key)
);
CREATE INDEX ix_jobs_dataset_id ON jobs(dataset_id);
CREATE INDEX ix_jobs_status ON jobs(status);
CREATE TABLE policy_documents (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, title varchar(120) NOT NULL,
 version varchar(30) NOT NULL, source varchar(300) NOT NULL UNIQUE, checksum varchar(64) NOT NULL, content text NOT NULL
);
CREATE TABLE policy_chunks (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, document_id uuid NOT NULL REFERENCES policy_documents,
 section varchar(160) NOT NULL, content text NOT NULL
);
CREATE INDEX ix_policy_chunks_document_id ON policy_chunks(document_id);
CREATE TABLE assistant_sessions (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, dataset_id uuid NOT NULL REFERENCES datasets, owner_hash varchar(64)
);
CREATE INDEX ix_assistant_sessions_dataset_id ON assistant_sessions(dataset_id);
CREATE TABLE assistant_messages (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL, session_id uuid NOT NULL REFERENCES assistant_sessions,
 question varchar(2000) NOT NULL, answer text NOT NULL, "references" jsonb NOT NULL
);
CREATE INDEX ix_assistant_messages_session_id ON assistant_messages(session_id);
CREATE FUNCTION prevent_decision_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'Decisions are append-only'; END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER decisions_append_only BEFORE UPDATE OR DELETE ON decisions
FOR EACH ROW EXECUTE FUNCTION prevent_decision_mutation();
