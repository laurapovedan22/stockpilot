export type Numeric = number | string;
export interface List<T> {
  items: T[];
  total?: number;
  page?: number;
  page_size?: number;
}
export interface Dataset {
  id: string;
  name: string;
  mode: 'synthetic' | 'historical';
  currency: string;
  timezone: string;
  as_of_date: string;
  provenance: Record<string, unknown>;
  seed: number | null;
}
export interface Product {
  id: string;
  dataset_id: string;
  sku: string;
  description: string;
  active: boolean;
  provenance: Record<string, unknown>;
  inventory?: Inventory | null;
  inbound?: Inbound[];
}
export interface Inventory {
  id: string;
  product_id: string;
  snapshot_id: string;
  on_hand: number;
  reserved: number;
  unit_cost: Numeric;
  lead_time_days: number;
  supplier_code: string;
  pack_size: number;
  minimum_order_units: number;
  provenance: string;
}
export interface Inbound {
  id: string;
  product_id: string;
  quantity: number;
  arrival: string;
}
export interface Snapshot {
  id: string;
  version: number;
  as_of_date: string;
  origin: string;
}
export interface Metrics {
  mae: number;
  rmse: number;
  wape: number | null;
  bias: number | null;
  coverage_90?: number | null;
  null_reason?: string | null;
}
export interface Fold {
  id: string;
  fold: string;
  product_id: string;
  model: string;
  metrics: Metrics & { start: string; end: string; train_days: number };
}
export interface Forecast {
  id: string;
  cutoff_date: string;
  horizon: number;
  model: string;
  metrics: {
    validation: Record<string, Metrics>;
    test: Metrics;
    warnings: string[];
    calibration_samples_per_product: Record<string, number>;
  };
  folds?: Fold[];
}
export interface Point {
  day: string;
  yhat: Numeric;
  lower: Numeric | null;
  upper: Numeric | null;
}
export interface Sale {
  day: string;
  units: number;
}
export interface Explanation {
  sku: string;
  description: string;
  target: number;
  available: number;
  on_hand: number;
  reserved: number;
  eligible_inbound: number;
  position: number;
  raw: number;
  pack_size: number;
  minimum_order_units: number;
  requested_units: number;
  allocated_units: number;
  unit_cost: string;
  lead_time_days: number;
  protection_days: number;
  service_level: number;
  trajectory_count: number;
  risk: number | null;
  risk_after: number | null;
  arrival_warning: boolean | null;
  forecast_version: string;
  method: string;
  unmet_units: number;
  cause: string | null;
}
export interface Decision {
  id: string;
  version: number;
  action: 'accepted' | 'rejected' | 'adjusted';
  final_units: number;
  reason: string;
  created_at: string;
}
export interface Recommendation {
  id: string;
  product_id: string;
  requested_units: number;
  allocated_units: number;
  cost: Numeric;
  risk: Numeric | null;
  explanation: Explanation;
  decisions?: Decision[];
}
export interface RecommendationRun {
  id: string;
  forecast_run_id: string;
  snapshot_id: string;
  budget: Numeric | null;
  policy: { service_level: number; review_days: number };
}
export interface Distribution {
  mean: number;
  p10: number;
  p90: number;
}
export interface Scenario {
  id: string;
  name: string;
  created_at: string;
  inputs: Record<string, unknown>;
  results: {
    trajectory_count: number;
    assumptions: string[];
    policies: Record<string, { metrics: Record<string, Distribution | null> }>;
  };
}
export interface Job {
  id: string;
  dataset_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  stage: string;
  progress: number;
  result_id: string | null;
  error: string | null;
}
export interface Issue {
  row: number;
  message: string;
}
export interface Report {
  received: number;
  valid: number;
  written?: number;
  errors: Issue[];
  warnings: Issue[];
  exclusions: Issue[];
  min_date: string | null;
  max_date: string | null;
  rows?: { row: number; values: Record<string, string> }[];
  headers?: string[];
}
export interface Batch {
  id: string;
  kind: string;
  status: string;
  report: Report;
  checksum: string;
  created_at: string;
}
export interface Preview {
  token: string;
  checksum: string;
  status: string;
  report: Report;
}
export interface Summary {
  dataset: Dataset;
  active_products: number;
  high_risk_products: number;
  recommended_cost: Numeric | null;
  forecast_run: Forecast | null;
  snapshot: Snapshot | null;
  recommendation_run: RecommendationRun | null;
  last_scenario: Scenario | null;
  risk_items: Recommendation[];
  quality: Batch[];
}
export interface Source {
  type: string;
  id: string;
  title?: string;
  section?: string;
  version?: string;
  excerpt?: string;
  date?: string;
}
export interface AssistantAnswer {
  session_id: string;
  text: string;
  mode: string;
  tools: string[];
  sources: Source[];
}
