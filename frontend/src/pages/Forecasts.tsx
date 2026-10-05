import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useWorkspace } from '../app/Workspace';
import { DemandChart } from '../components/charts/DemandChart';
import { Empty, ErrorState, JobStatus } from '../components/ui/States';
import { api, post, scope, useJob } from '../lib/api';
import { modelName, number, percent } from '../lib/format';
import type { Forecast, Job, List, Point, Product, Sale } from '../types/api';

export function Forecasts() {
  const { dataset, summary, readOnly, refresh } = useWorkspace();
  const [selected, setSelected] = useState(''),
    [frequency, setFrequency] = useState('daily'),
    [jobId, setJobId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState(''),
    [visibleDays, setVisibleDays] = useState(28);
  const runs = useQuery({
    queryKey: ['forecast-runs', dataset.id, summary.forecast_run?.id],
    queryFn: () => api<List<Forecast>>(`/datasets/${dataset.id}/forecast-runs`),
  });
  const products = useQuery({
    queryKey: ['planning-products', dataset.id],
    queryFn: () => api<List<Product>>(`/datasets/${dataset.id}/products?active=true&page_size=100`),
  });
  const id = selected || products.data?.items.find((p) => p.active)?.id || '';
  const runId = selectedRun || summary.forecast_run?.id;
  const run = useQuery({
    queryKey: ['forecast', runId],
    queryFn: () => api<Forecast>(scope(`/forecast-runs/${runId}`, dataset.id)),
    enabled: !!runId,
  });
  const sales = useQuery({
    queryKey: ['sales', id, dataset.id],
    queryFn: () => api<List<Sale>>(scope(`/products/${id}/sales`, dataset.id)),
    enabled: !!id,
  });
  const points = useQuery({
    queryKey: ['forecast-points', runId, id, frequency],
    queryFn: () =>
      api<List<Point>>(
        scope(`/forecast-runs/${runId}/points?product_id=${id}&frequency=${frequency}`, dataset.id),
      ),
    enabled: !!runId && !!id,
  });
  const training = useMutation({
    mutationFn: () =>
      post<Job>(`/datasets/${dataset.id}/forecast-runs`, {
        cutoff_date: dataset.as_of_date,
        horizon: 42,
      }),
    onSuccess: (job) => setJobId(job.id),
  });
  const job = useJob(jobId, dataset.id);
  useEffect(() => {
    if (job.data?.status === 'succeeded') refresh();
  }, [job.data?.status, refresh]);
  const cutoff = run.data?.cutoff_date ?? dataset.as_of_date;
  const history = sales.data?.items.filter((s) => s.day <= cutoff).slice(-84) ?? [];
  const observed =
    frequency === 'daily'
      ? history
      : (() => {
          const buckets = new Map<string, number>();
          for (const s of history) {
            const d = new Date(s.day);
            d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
            const key = d.toISOString().slice(0, 10);
            buckets.set(key, (buckets.get(key) ?? 0) + s.units);
          }
          return [...buckets].map(([day, units]) => ({ day, units }));
        })();
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">DEMAND, WITH UNCERTAINTY</p>
          <h1>Forecasts</h1>
          <p>Temporal evaluation selects the model. The final holdout stays independent.</p>
        </div>
        {!readOnly && (
          <button
            className="primary"
            disabled={
              training.isPending || job.data?.status === 'running' || job.data?.status === 'queued'
            }
            onClick={() => training.mutate()}
          >
            Prepare forecast
          </button>
        )}
      </div>
      <ErrorState error={training.error || run.error || points.error || sales.error} />
      <JobStatus job={job.data} error={job.error} />
      {!runId ? (
        <Empty>No forecast prepared. Use make demo, or prepare one locally.</Empty>
      ) : (
        <>
          <section className="panel">
            <div className="controls">
              <label>
                Product
                <select value={id} onChange={(e) => setSelected(e.target.value)}>
                  {products.data?.items
                    .filter((p) => p.active)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.sku} · {p.description}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Aggregation
                <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </select>
              </label>
              <label>
                Run
                <select value={runId} onChange={(e) => setSelectedRun(e.target.value)}>
                  {runs.data?.items.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.cutoff_date} · {modelName(r.model)} · {r.id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Forecast range
                <select
                  value={visibleDays}
                  onChange={(e) => setVisibleDays(Number(e.target.value))}
                >
                  <option value="28">28 days</option>
                  <option value="42">42 days</option>
                </select>
              </label>
              <div className="run-label">
                Run <code>{runId.slice(0, 8)}</code> ·{' '}
                {modelName(run.data?.model ?? summary.forecast_run!.model)}
              </div>
            </div>
            <DemandChart
              sales={observed}
              points={
                points.data?.items.filter(
                  (p) =>
                    p.day <=
                    new Date(new Date(cutoff).getTime() + visibleDays * 86400000)
                      .toISOString()
                      .slice(0, 10),
                ) ?? []
              }
              cutoff={cutoff}
            />
          </section>
          <div className="kpi-grid">
            {[
              ['Final test MAE', number(run.data?.metrics.test.mae, 2)],
              ['Final test WAPE', percent(run.data?.metrics.test.wape)],
              ['Final test RMSE', number(run.data?.metrics.test.rmse, 2)],
              ['Empirical 90% coverage', percent(run.data?.metrics.test.coverage_90)],
            ].map(([label, value]) => (
              <article className="kpi" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
                <small>Held-out 28 days · all selected products</small>
              </article>
            ))}
          </div>
          <section className="panel">
            <h2>Model comparison · validation only</h2>
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Scrollable data table"
            >
              <table>
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>WAPE</th>
                    <th>MAE</th>
                    <th>RMSE</th>
                    <th>Selection</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(run.data?.metrics.validation ?? {}).map(([model, m]) => (
                    <tr key={model}>
                      <td>{modelName(model)}</td>
                      <td>{percent(m.wape)}</td>
                      <td>{number(m.mae, 2)}</td>
                      <td>{number(m.rmse, 2)}</td>
                      <td>
                        {model === run.data?.model ? (
                          <span className="badge low">Selected</span>
                        ) : (
                          'Compared'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {run.data?.metrics.warnings.map((w) => (
              <p key={w} className="notice">
                {w}
              </p>
            ))}
          </section>
          <section className="panel">
            <h2>Temporal folds · selected product</h2>
            <p>
              Calibration samples: {number(run.data?.metrics.calibration_samples_per_product[id])}.
              Weekly bands aggregate trajectories before taking quantiles.
            </p>
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Scrollable data table"
            >
              <table>
                <thead>
                  <tr>
                    <th>Fold</th>
                    <th>Model</th>
                    <th>Train days</th>
                    <th>Evaluation dates</th>
                    <th>WAPE</th>
                  </tr>
                </thead>
                <tbody>
                  {run.data?.folds
                    ?.filter((f) => f.product_id === id)
                    .map((f) => (
                      <tr key={f.id}>
                        <td>{f.fold}</td>
                        <td>{modelName(f.model)}</td>
                        <td>{f.metrics.train_days}</td>
                        <td>
                          {f.metrics.start} → {f.metrics.end}
                        </td>
                        <td>{percent(f.metrics.wape)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </>
  );
}
