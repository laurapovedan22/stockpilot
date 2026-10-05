import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useWorkspace } from '../../app/Workspace';
import { ErrorState, Risk } from '../../components/ui/States';
import { post, scope } from '../../lib/api';
import { money, number, percent } from '../../lib/format';
import type { Recommendation } from '../../types/api';

export function RecommendationRow({
  item,
  onSaved,
}: {
  item: Recommendation;
  onSaved: () => void;
}) {
  const { dataset, readOnly } = useWorkspace();
  const [open, setOpen] = useState(false),
    [action, setAction] = useState('accepted'),
    [units, setUnits] = useState(item.allocated_units),
    [reason, setReason] = useState('');
  const e = item.explanation,
    last = item.decisions?.at(-1);
  const save = useMutation({
    mutationFn: () =>
      post(scope(`/recommendation-items/${item.id}/decisions`, dataset.id), {
        action,
        final_units: action === 'adjusted' ? units : null,
        reason,
        expected_version: last?.version ?? 0,
      }),
    onSuccess: onSaved,
  });
  return (
    <>
      <tr>
        <td>
          <Link to={`/products/${item.product_id}`}>
            <strong>{e.description}</strong>
            <small>{e.sku}</small>
          </Link>
        </td>
        <td>{e.available}</td>
        <td>{e.eligible_inbound}</td>
        <td>{e.lead_time_days}d</td>
        <td>{number(e.target, 1)}</td>
        <td>
          {item.requested_units} / <strong>{item.allocated_units}</strong>
        </td>
        <td>{money(item.cost)}</td>
        <td>
          <Risk value={item.risk} />
        </td>
        <td>
          <button
            className="small"
            aria-expanded={open}
            aria-controls={`explain-${item.id}`}
            onClick={() => setOpen(!open)}
          >
            {open ? 'Close' : 'Explain'}
          </button>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={9}>
            <div id={`explain-${item.id}`} className="explanation">
              <h3>{e.sku} · purchase calculation</h3>
              <div className="formula">
                <span>
                  Target <b>{number(e.target, 1)}</b>
                </span>
                <span>
                  − position <b>{e.position}</b>
                </span>
                <span>
                  → raw need <b>{e.raw}</b>
                </span>
                <span>
                  → requested <b>{e.requested_units}</b>
                </span>
              </div>
              <p>
                Protection = lead {e.lead_time_days} + review {e.protection_days - e.lead_time_days}{' '}
                = {e.protection_days} days. Target is the {percent(e.service_level)} cumulative
                demand quantile.
              </p>
              <p>
                Position = ({e.on_hand} on hand − {e.reserved} reserved) + {e.eligible_inbound}{' '}
                eligible inbound. Packs of {e.pack_size}; MOQ {e.minimum_order_units}. Unit cost{' '}
                {money(e.unit_cost)}.
              </p>
              <p>
                {e.method} · {e.trajectory_count} trajectories. Shortage risk before purchase:{' '}
                {percent(e.risk)}; after purchase: {percent(e.risk_after)}.
              </p>
              {e.arrival_warning && (
                <p className="notice">
                  Demand may be lost before the next arrival, even when total inbound covers the
                  period.
                </p>
              )}
              {e.unmet_units > 0 && (
                <p className="notice">
                  Budget constraint: {e.unmet_units} requested units remain unallocated.
                </p>
              )}
              <small>Forecast version {e.forecast_version} · proposal only</small>
              {!readOnly && (
                <form
                  className="decision-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    save.mutate();
                  }}
                >
                  <label>
                    Decision
                    <select value={action} onChange={(event) => setAction(event.target.value)}>
                      <option value="accepted">Accept plan</option>
                      <option value="rejected">Reject</option>
                      <option value="adjusted">Adjust quantity</option>
                    </select>
                  </label>
                  {action === 'adjusted' && (
                    <label>
                      Final units
                      <input
                        type="number"
                        min="0"
                        step={e.pack_size}
                        value={units}
                        onChange={(event) => setUnits(Number(event.target.value))}
                        required
                      />
                    </label>
                  )}
                  <label>
                    Reason
                    <input
                      value={reason}
                      maxLength={1000}
                      onChange={(event) => setReason(event.target.value)}
                      required={action === 'adjusted'}
                      placeholder="Record your reasoning"
                    />
                  </label>
                  <button className="primary" disabled={save.isPending}>
                    Save decision
                  </button>
                </form>
              )}
              <ErrorState error={save.error} />
              {item.decisions?.length ? (
                <details>
                  <summary>
                    Decision history ({item.decisions.length}) · latest {last?.action}
                  </summary>
                  <ul>
                    {item.decisions.map((d) => (
                      <li key={d.id}>
                        Version {d.version}: {d.action} · {d.final_units} units ·{' '}
                        {d.reason || 'No reason provided'}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : (
                <p className="fineprint">No decision recorded.</p>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
