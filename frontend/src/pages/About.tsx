import { useQuery } from '@tanstack/react-query';
import { useWorkspace } from '../app/Workspace';
import { ErrorState } from '../components/ui/States';
import { api } from '../lib/api';

interface Methodology {
  assumptions: string[];
  references: { title: string; url: string }[];
}
export function About() {
  const { dataset } = useWorkspace();
  const query = useQuery({
    queryKey: ['methodology', dataset.id],
    queryFn: () => api<Methodology>(`/datasets/${dataset.id}/methodology`),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">ABOUT & METHODOLOGY</p>
          <h1>Decisions you can inspect.</h1>
          <p>StockPilot is a personal inventory planning project by Laura Poveda Nicolás.</p>
        </div>
      </div>
      <section className="panel prose">
        <h2>The planning question</h2>
        <p>
          Which products should a small distributor replenish, in what quantities, and what changes
          when demand rises or delivery takes longer?
        </p>
        <p>
          StockPilot connects validated sales data, demand forecasts, inventory snapshots and
          reproducible simulations. It is a portfolio project with synthetic operational
          assumptions.
        </p>
        <h2>Architecture</h2>
        <div className="pipeline">
          CSV / generator → validation → PostgreSQL → temporal forecasts → purchase plans → scenario
          comparison
        </div>
        <p>
          A modular Python backend owns the calculations. A persistent PostgreSQL queue processes
          imports, forecasting and simulations. React displays API results and records local
          planning decisions.
        </p>
        <h2>Forecast validation</h2>
        <p>
          Two references — repeating the last week and a 28-day moving average — are compared with
          global recursive XGBoost. Three expanding 28-day windows precede a final 28-day holdout.
          Validation WAPE chooses the model; the final test never selects it. A simple reference can
          win.
        </p>
        <h2>Uncertainty & replenishment</h2>
        <p>
          Signed validation residuals calibrate daily empirical intervals. Seven-day residual blocks
          generate 200 non-negative demand trajectories. The service quantile of cumulative demand
          over lead time plus review interval defines the target. Available inventory and timely
          inbound reduce raw need; pack size and MOQ determine the proposed purchase.
        </p>
        <h2>Assumptions & limits</h2>
        <ErrorState error={query.error} />
        <ul>
          {query.data?.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
        <p>
          Historical retail uses UCI gift and online retail transactions from 2009–2011. Inventory,
          supplier lead times and acquisition costs are simulated; selling prices are never
          presented as acquisition costs. There are no claims of real business savings or production
          use.
        </p>
        <h2>Sources</h2>
        <ul>
          {query.data?.references.map((r) => (
            <li key={r.title}>
              <a href={r.url}>{r.title}</a>
            </li>
          ))}
        </ul>
        <p className="fineprint">
          Code license: MIT. UCI data: Chen, D. (2012), Online Retail II, CC BY 4.0.
        </p>
      </section>
    </>
  );
}
