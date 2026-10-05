import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useWorkspace } from '../app/Workspace';
import { DemandChart } from '../components/charts/DemandChart';
import { Empty, ErrorState, Risk } from '../components/ui/States';
import { api, scope } from '../lib/api';
import { money, number, percent, modelName } from '../lib/format';
import type { List, Point, Product, Sale } from '../types/api';

export function Dashboard() {
  const { dataset, summary } = useWorkspace();
  const products = useQuery({
    queryKey: ['planning-products', dataset.id],
    queryFn: () => api<List<Product>>(`/datasets/${dataset.id}/products?active=true&page_size=100`),
  });
  const product = products.data?.items.find((item) => item.active);
  const sales = useQuery({
    queryKey: ['dashboard-sales', product?.id],
    queryFn: () => api<List<Sale>>(scope(`/products/${product?.id}/sales`, dataset.id)),
    enabled: !!product,
  });
  const forecast = useQuery({
    queryKey: ['dashboard-points', product?.id, summary.forecast_run?.id],
    queryFn: () =>
      api<List<Point>>(
        scope(
          `/forecast-runs/${summary.forecast_run?.id}/points?product_id=${product?.id}`,
          dataset.id,
        ),
      ),
    enabled: !!product && !!summary.forecast_run,
  });
  const fill = summary.last_scenario?.results.policies.selected_model.metrics.fill_rate;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR INVENTORY, IN FOCUS</p>
          <h1>Inventory overview</h1>
          <p>Know what to replenish. Understand why.</p>
        </div>
        <Link to="/scenarios" className="button primary">
          Explore a scenario <span>↗</span>
        </Link>
      </div>
      <div className="kpi-grid">
        <article className="kpi">
          <span>Active products</span>
          <strong>{number(summary.active_products)}</strong>
          <small>Selected before evaluation</small>
        </article>
        <article className="kpi">
          <span>High shortage risk</span>
          <strong>
            {number(summary.high_risk_products)}
            <span className="kpi-dot amber" />
          </strong>
          <small>Projected · before new purchases</small>
        </article>
        <article className="kpi">
          <span>Recommended purchase</span>
          <strong>{money(summary.recommended_cost)}</strong>
          <small>Pack and MOQ constraints included</small>
        </article>
        <article className="kpi">
          <span>Latest simulated fill rate</span>
          <strong>{percent(fill?.mean)}</strong>
          <small>
            {fill ? 'Forecast policy · latest scenario' : 'Run a scenario to estimate service'}
          </small>
        </article>
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Demand outlook</h2>
              <p>
                {product?.description ?? 'Observed sales and demand forecast'} · {product?.sku}
              </p>
            </div>
            <Link to="/forecasts" className="text-link">
              View forecasts ↗
            </Link>
          </div>
          <ErrorState error={sales.error || forecast.error} />
          <DemandChart
            sales={sales.data?.items.slice(-84) ?? []}
            points={forecast.data?.items.slice(0, 28) ?? []}
            cutoff={dataset.as_of_date}
          />
          <div className="panel-foot">
            <span className="badge mode">
              {summary.forecast_run
                ? modelName(summary.forecast_run.model)
                : 'No forecast prepared'}
            </span>
            <span>Next 28 days · units sold</span>
          </div>
        </section>
        <section className="panel insight">
          <p className="eyebrow">PLANNING NOTE</p>
          <h2>A plan you can explain.</h2>
          <p>
            Each purchase starts with forecast demand over the lead time and review period.
            Available stock and eligible inbound orders reduce the quantity needed.
          </p>
          <ol>
            <li>Check shortage risk</li>
            <li>Review the calculation</li>
            <li>Stress-test supplier delays</li>
          </ol>
          <Link to="/replenishment" className="button">
            Review replenishment →
          </Link>
          <p className="fineprint">
            {dataset.mode === 'synthetic'
              ? 'Synthetic sales. Simulated stock and costs.'
              : `Historical recorded sales. Operations: ${summary.snapshot?.origin || 'not imported'}.`}{' '}
            No orders sent to suppliers.
          </p>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Products to review</h2>
            <p>The highest projected shortage risks in the current plan.</p>
          </div>
          <Link to="/replenishment" className="text-link">
            View full plan →
          </Link>
        </div>
        {summary.risk_items.length ? (
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
                  <th>Lead time</th>
                  <th>Suggested units</th>
                  <th>Purchase cost</th>
                  <th>Shortage risk</th>
                </tr>
              </thead>
              <tbody>
                {summary.risk_items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link to={`/products/${item.product_id}`}>
                        <strong>{item.explanation.description}</strong>
                        <small>{item.explanation.sku}</small>
                      </Link>
                    </td>
                    <td>{number(item.explanation.available)}</td>
                    <td>{item.explanation.lead_time_days} days</td>
                    <td>{number(item.allocated_units)}</td>
                    <td>{money(item.cost)}</td>
                    <td>
                      <Risk value={item.risk} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>No replenishment plan available. Prepare it with make demo.</Empty>
        )}
      </section>
      <div className="bottom-links">
        <Link to="/quality">✓ Inspect data quality</Link>
        <Link to="/about">Read assumptions & methodology ↗</Link>
      </div>
    </>
  );
}
