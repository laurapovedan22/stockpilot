import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useWorkspace } from '../app/Workspace';
import { Empty, ErrorState, JobStatus } from '../components/ui/States';
import { api, post, scope, useJob } from '../lib/api';
import { date, modelName, money, number, percent } from '../lib/format';
import type { Job, List, Scenario } from '../types/api';

export function Scenarios() {
  const { dataset, summary } = useWorkspace();
  const [multiplier, setMultiplier] = useState(1),
    [delay, setDelay] = useState(0),
    [budget, setBudget] = useState(''),
    [name, setName] = useState('My scenario'),
    [scenarioId, setScenarioId] = useState<string | null>(null),
    [jobId, setJobId] = useState<string | null>(null);
  const history = useQuery({
    queryKey: ['scenarios', dataset.id],
    queryFn: () => api<List<Scenario>>(`/datasets/${dataset.id}/scenario-runs`),
  });
  const run = useMutation({
    mutationFn: () =>
      post<Job>(`/datasets/${dataset.id}/scenario-runs`, {
        base_run_id: summary.recommendation_run?.id,
        name,
        demand_multiplier: multiplier,
        lead_time_delay_days: delay,
        budget: budget === '' ? null : budget,
        horizon_days: 28,
        service_level: 0.95,
        seed: 42,
      }),
    onSuccess: (job) => setJobId(job.id),
  });
  const job = useJob(jobId, dataset.id);
  const refetchHistory = history.refetch;
  useEffect(() => {
    if (job.data?.status === 'succeeded' && job.data.result_id) {
      setScenarioId(job.data.result_id);
      void refetchHistory();
    }
  }, [job.data?.status, job.data?.result_id, refetchHistory]);
  const scenario = useQuery({
    queryKey: ['scenario', scenarioId, dataset.id],
    queryFn: () => api<Scenario>(scope(`/scenario-runs/${scenarioId}`, dataset.id)),
    enabled: !!scenarioId,
  });
  function preset(label: string) {
    setName(label);
    setMultiplier(label === 'Demand surge' || label === 'Combined shock' ? 1.5 : 1);
    setDelay(label === 'Supplier delay' || label === 'Combined shock' ? 4 : 0);
    setBudget(label === 'Tight budget' || label === 'Combined shock' ? '250' : '');
  }
  const blocked =
    !summary.recommendation_run ||
    !summary.forecast_run ||
    Object.values(summary.forecast_run.metrics.calibration_samples_per_product).some((n) => n < 28);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">WHAT IF THE PLAN CHANGES?</p>
          <h1>Scenario lab</h1>
          <p>
            Stress-test demand and delivery. Compare policies on the same simulated trajectories.
          </p>
        </div>
        <span className="badge mode">Projected / simulated</span>
      </div>
      <div className="scenario-grid">
        <section className="panel">
          <h2>Build your scenario</h2>
          <div className="presets">
            {['Demand surge', 'Supplier delay', 'Tight budget', 'Combined shock'].map((label) => (
              <button key={label} onClick={() => preset(label)}>
                {label}
              </button>
            ))}
          </div>
          <form
            className="scenario-form"
            onSubmit={(event) => {
              event.preventDefault();
              run.mutate();
            }}
          >
            <label>
              Scenario name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={120}
                required
              />
            </label>
            <label>
              Demand multiplier <strong>{multiplier.toFixed(2)}×</strong>
              <input
                aria-label="Demand multiplier slider"
                type="range"
                min=".5"
                max="2"
                step=".05"
                value={multiplier}
                onChange={(event) => setMultiplier(Number(event.target.value))}
              />
              <input
                aria-label="Demand multiplier"
                type="number"
                min=".5"
                max="2"
                step=".05"
                value={multiplier}
                onChange={(event) => setMultiplier(Number(event.target.value))}
              />
            </label>
            <label>
              Extra delivery days <strong>{delay} days</strong>
              <input
                aria-label="Delivery delay slider"
                type="range"
                min="0"
                max="14"
                step="1"
                value={delay}
                onChange={(event) => setDelay(Number(event.target.value))}
              />
              <input
                aria-label="Extra delivery days"
                type="number"
                min="0"
                max="14"
                step="1"
                value={delay}
                onChange={(event) => setDelay(Number(event.target.value))}
              />
            </label>
            <label>
              Budget per review (GBP)
              <input
                type="number"
                min="0"
                step=".01"
                placeholder="Unrestricted"
                value={budget}
                onChange={(event) => setBudget(event.target.value)}
              />
            </label>
            <p className="fineprint">
              28 days · service 95% · seed 42. Delay moves pending and new arrivals. Controls do not
              run the calculation automatically.
            </p>
            <button
              className="primary"
              disabled={
                blocked ||
                run.isPending ||
                job.data?.status === 'running' ||
                job.data?.status === 'queued'
              }
            >
              Run simulation →
            </button>
            {blocked && (
              <p className="notice">
                Prepare a recommendation run with calibrated forecast trajectories before
                simulating.
              </p>
            )}
          </form>
          <ErrorState error={run.error} />
          <JobStatus job={job.data} error={job.error} />
        </section>
        <section className="panel">
          <h2>Policy comparison</h2>
          <ErrorState error={scenario.error} />
          {scenario.data ? (
            <>
              <p>
                <strong>{scenario.data.name}</strong> · {scenario.data.results.trajectory_count}{' '}
                trajectories · {date(scenario.data.created_at)}
              </p>
              <p className="fineprint">
                Saved inputs: demand {String(scenario.data.inputs.demand_multiplier)}× · delay{' '}
                {String(scenario.data.inputs.lead_time_delay_days)} days · budget{' '}
                {scenario.data.inputs.budget == null
                  ? 'unrestricted'
                  : `GBP ${String(scenario.data.inputs.budget)}`}
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
                      <th>Metric</th>
                      {Object.keys(scenario.data.results.policies).map((policy) => (
                        <th key={policy}>{modelName(policy)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['fill_rate', 'Fill rate'],
                      ['lost_units', 'Lost units'],
                      ['stockout_product_days', 'Stockout product-days'],
                      ['average_stock', 'Average stock / SKU'],
                      ['purchase_cost', 'Purchases'],
                      ['holding_cost', 'Holding cost'],
                      ['loss_penalty', 'Simulated loss penalty'],
                      ['operating_cost', 'Operating cost'],
                      ['final_stock', 'Final stock'],
                      ['final_pipeline', 'Final pipeline'],
                    ].map(([metric, label]) => (
                      <tr key={metric}>
                        <th>{label}</th>
                        {Object.entries(scenario.data!.results.policies).map(([policy, values]) => {
                          const m = values.metrics[metric];
                          const format =
                            metric === 'fill_rate'
                              ? percent
                              : metric.includes('cost') || metric === 'loss_penalty'
                                ? money
                                : (v: number) => number(v, 1);
                          return (
                            <td key={policy}>
                              <strong>{m ? format(m.mean) : 'Not available'}</strong>
                              {m && (
                                <small>
                                  P10–P90: {format(m.p10)}–{format(m.p90)}
                                </small>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <details>
                <summary>Simulation assumptions</summary>
                <ul>
                  {scenario.data.results.assumptions.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </details>
            </>
          ) : (
            <Empty>
              Choose a preset or edit the controls, then run a simulation. Results will appear here.
            </Empty>
          )}
        </section>
      </div>
      <section className="panel">
        <h2>Saved scenarios</h2>
        <ErrorState error={history.error} />
        {history.data?.items.length ? (
          <div className="saved-runs">
            {history.data.items.map((s) => (
              <button key={s.id} onClick={() => setScenarioId(s.id)}>
                <strong>{s.name}</strong>
                <small>{date(s.created_at)} · open saved result</small>
              </button>
            ))}
          </div>
        ) : (
          <p>No saved simulations yet.</p>
        )}
      </section>
    </>
  );
}
