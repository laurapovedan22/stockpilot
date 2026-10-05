import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useWorkspace } from '../app/Workspace';
import { Empty, ErrorState } from '../components/ui/States';
import { RecommendationRow } from '../features/recommendations/RecommendationRow';
import { api, post, scope } from '../lib/api';
import { money } from '../lib/format';
import type { List, Recommendation, RecommendationRun } from '../types/api';

export function Replenishment() {
  const { dataset, summary, refresh, readOnly } = useWorkspace();
  const [service, setService] = useState(0.95),
    [review, setReview] = useState(7),
    [budget, setBudget] = useState('');
  const id = summary.recommendation_run?.id;
  const items = useQuery({
    queryKey: ['recommendations', id],
    queryFn: () => api<List<Recommendation>>(scope(`/recommendation-runs/${id}/items`, dataset.id)),
    enabled: !!id,
  });
  const create = useMutation({
    mutationFn: () =>
      post<RecommendationRun>(`/datasets/${dataset.id}/recommendation-runs`, {
        forecast_run_id: summary.forecast_run?.id,
        snapshot_id: summary.snapshot?.id,
        policy: { service_level: service, review_days: review },
        budget: budget === '' ? null : budget,
      }),
    onSuccess: refresh,
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">FROM FORECAST TO PURCHASE PLAN</p>
          <h1>Replenishment</h1>
          <p>Every quantity has a calculation. Every decision keeps its history.</p>
        </div>
        {id && (
          <a
            className="button"
            href={`/api/v1${scope(`/recommendation-runs/${id}/export`, dataset.id)}`}
            download
          >
            Download plan CSV ↓
          </a>
        )}
      </div>
      <div className="notice">
        This is a purchase proposal. Accepting records a plan and does not send an order or increase
        physical stock.
      </div>
      <section className="panel">
        <form
          className="controls"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <label>
            Service level
            <select
              value={service}
              onChange={(e) => setService(Number(e.target.value))}
              disabled={readOnly}
            >
              <option value="0.9">90%</option>
              <option value="0.95">95%</option>
              <option value="0.99">99%</option>
            </select>
          </label>
          <label>
            Review interval (days)
            <input
              type="number"
              min="1"
              max="14"
              value={review}
              onChange={(e) => setReview(Number(e.target.value))}
              disabled={readOnly}
            />
          </label>
          <label>
            Budget (GBP, optional)
            <input
              type="number"
              min="0"
              step="0.01"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="Unrestricted"
              disabled={readOnly}
            />
          </label>
          {!readOnly && (
            <button
              className="primary"
              disabled={create.isPending || !summary.forecast_run || !summary.snapshot}
            >
              Calculate new plan
            </button>
          )}
        </form>
        <p className="fineprint">
          Current plan budget:{' '}
          {summary.recommendation_run?.budget == null
            ? 'Unrestricted'
            : money(summary.recommendation_run.budget)}
          . Allocation uses marginal simulated shortage reduction per GBP; it is a heuristic.
        </p>
      </section>
      <ErrorState error={items.error || create.error} />
      {id ? (
        <section className="panel">
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Scrollable data table"
          >
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Available</th>
                  <th>Inbound</th>
                  <th>Lead</th>
                  <th>Target</th>
                  <th>Requested / allocated</th>
                  <th>Cost</th>
                  <th>Risk</th>
                  <th>Calculation</th>
                </tr>
              </thead>
              <tbody>
                {items.data?.items.map((item) => (
                  <RecommendationRow
                    key={item.id}
                    item={item}
                    onSaved={() => {
                      void items.refetch();
                    }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <Empty>Prepare a forecast and inventory snapshot to calculate recommendations.</Empty>
      )}
    </>
  );
}
