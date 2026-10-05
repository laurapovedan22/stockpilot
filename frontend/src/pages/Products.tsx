import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useWorkspace } from '../app/Workspace';
import { DemandChart } from '../components/charts/DemandChart';
import { Empty, ErrorState, Loading } from '../components/ui/States';
import { api, scope } from '../lib/api';
import { date, money, number } from '../lib/format';
import type { List, Point, Product, Sale } from '../types/api';

export function Products() {
  const { dataset } = useWorkspace();
  const [search, setSearch] = useState(''),
    [risk, setRisk] = useState(''),
    [supplier, setSupplier] = useState(''),
    [page, setPage] = useState(1);
  const result = useQuery({
    queryKey: ['products', dataset.id, search, risk, supplier, page],
    queryFn: () =>
      api<List<Product>>(
        `/datasets/${dataset.id}/products?q=${encodeURIComponent(search)}${risk ? `&risk=${risk}` : ''}${supplier ? `&supplier=${encodeURIComponent(supplier)}` : ''}&page=${page}`,
      ),
  });
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">CATALOG & OPERATIONS</p>
          <h1>Products</h1>
          <p>Inspect the demand, stock and assumptions behind each SKU.</p>
        </div>
      </div>
      <section className="panel">
        <div className="controls">
          <label>
            Search products
            <input
              placeholder="SKU or product name"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </label>
          <label>
            Risk
            <select
              value={risk}
              onChange={(e) => {
                setRisk(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All risk levels</option>
              {['low', 'medium', 'high'].map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <label>
            Supplier code
            <input
              placeholder="e.g. SIM-1"
              value={supplier}
              onChange={(e) => {
                setSupplier(e.target.value);
                setPage(1);
              }}
            />
          </label>
        </div>
        <ErrorState error={result.error} />
        {result.isLoading && <Loading />}
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Scrollable data table">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>SKU</th>
                <th>Forecast scope</th>
                <th>Provenance</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {result.data?.items.map((p) => (
                <tr key={p.id}>
                  <td>
                    <strong>{p.description}</strong>
                  </td>
                  <td className="mono">{p.sku}</td>
                  <td>{p.active ? 'Active' : 'Outside active selection'}</td>
                  <td>
                    <span className="badge mode">{String(p.provenance.sales ?? dataset.mode)}</span>
                  </td>
                  <td>
                    <Link className="text-link" to={`/products/${p.id}`}>
                      Inspect →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {result.data?.items.length === 0 && <Empty>No products match these filters.</Empty>}
        <div className="pagination">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </button>
          <span>
            Page {page} · {result.data?.total ?? 0} products
          </span>
          <button
            disabled={page * 25 >= (result.data?.total ?? 0)}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </section>
    </>
  );
}

export function ProductDetail() {
  const { id } = useParams();
  const { dataset, summary, readOnly, refresh } = useWorkspace();
  const product = useQuery({
    queryKey: ['product', id, dataset.id],
    queryFn: () => api<Product>(scope(`/products/${id}`, dataset.id)),
  });
  const sales = useQuery({
    queryKey: ['sales', id, dataset.id],
    queryFn: () => api<List<Sale>>(scope(`/products/${id}/sales`, dataset.id)),
  });
  const points = useQuery({
    queryKey: ['points', id, summary.forecast_run?.id],
    queryFn: () =>
      api<List<Point>>(
        scope(`/forecast-runs/${summary.forecast_run?.id}/points?product_id=${id}`, dataset.id),
      ),
    enabled: !!summary.forecast_run,
  });
  const update = useMutation({
    mutationFn: (inputs: { on_hand: number; reserved: number }) =>
      api(scope(`/inventory/${product.data?.inventory?.id}`, dataset.id), {
        method: 'PATCH',
        body: JSON.stringify({ ...inputs, expected_version: summary.snapshot?.version }),
      }),
    onSuccess: () => {
      void product.refetch();
      refresh();
    },
  });
  if (product.isLoading) return <Loading />;
  const p = product.data;
  return (
    <>
      <Link to="/products" className="text-link">
        ← All products
      </Link>
      <ErrorState error={product.error || sales.error || points.error || update.error} />
      {p && (
        <>
          <div className="page-heading">
            <div>
              <p className="eyebrow">{p.sku}</p>
              <h1>{p.description}</h1>
              <p>
                Sales: {String(p.provenance.sales ?? dataset.mode)} · Operations:{' '}
                {p.inventory?.provenance ?? 'Not available'}
              </p>
            </div>
            <Link to="/replenishment" className="button primary">
              View purchase explanation →
            </Link>
          </div>
          <div className="kpi-grid">
            <article className="kpi">
              <span>On hand</span>
              <strong>{number(p.inventory?.on_hand)}</strong>
              <small>Physical units in snapshot</small>
            </article>
            <article className="kpi">
              <span>Available</span>
              <strong>
                {p.inventory ? number(p.inventory.on_hand - p.inventory.reserved) : 'Not available'}
              </strong>
              <small>On hand − reserved</small>
            </article>
            <article className="kpi">
              <span>Unit purchase cost</span>
              <strong>{money(p.inventory?.unit_cost)}</strong>
              <small>{p.inventory?.provenance ?? 'Not available'}</small>
            </article>
            <article className="kpi">
              <span>Lead time</span>
              <strong>
                {p.inventory ? `${p.inventory.lead_time_days} days` : 'Not available'}
              </strong>
              <small>Supplier {p.inventory?.supplier_code ?? 'Not available'}</small>
            </article>
          </div>
          <section className="panel">
            <h2>Observed sales & forecast</h2>
            <DemandChart
              sales={sales.data?.items.slice(-84) ?? []}
              points={points.data?.items.slice(0, 28) ?? []}
              cutoff={dataset.as_of_date}
            />
          </section>
          <div className="two-columns">
            <section className="panel">
              <h2>Pending inbound</h2>
              {p.inbound?.length ? (
                <ul>
                  {p.inbound.map((o) => (
                    <li key={o.id}>
                      {o.quantity} units · arrival {date(o.arrival)}
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty>No pending orders in this snapshot.</Empty>
              )}
            </section>
            {!readOnly && p.inventory && (
              <section className="panel">
                <h2>Edit local stock</h2>
                <p>Saving creates a new snapshot; historical plans keep their inputs.</p>
                <form
                  className="controls"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = new FormData(e.currentTarget);
                    update.mutate({
                      on_hand: Number(form.get('on_hand')),
                      reserved: Number(form.get('reserved')),
                    });
                  }}
                >
                  <label>
                    On hand
                    <input
                      name="on_hand"
                      type="number"
                      min="0"
                      defaultValue={p.inventory.on_hand}
                      required
                    />
                  </label>
                  <label>
                    Reserved
                    <input
                      name="reserved"
                      type="number"
                      min="0"
                      defaultValue={p.inventory.reserved}
                      required
                    />
                  </label>
                  <button className="primary" disabled={update.isPending}>
                    Save snapshot
                  </button>
                </form>
                {update.isSuccess && <p role="status">Snapshot saved.</p>}
              </section>
            )}
          </div>
        </>
      )}
    </>
  );
}
