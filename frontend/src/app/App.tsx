import { useQuery } from '@tanstack/react-query';
import { useCallback, useEffect, useState } from 'react';
import { NavLink, Route, Routes } from 'react-router-dom';
import { ErrorState, Loading, Empty } from '../components/ui/States';
import { api, post } from '../lib/api';
import { date } from '../lib/format';
import type { Dataset, List, Summary } from '../types/api';
import { Dashboard } from '../pages/Dashboard';
import { Products, ProductDetail } from '../pages/Products';
import { Forecasts } from '../pages/Forecasts';
import { Replenishment } from '../pages/Replenishment';
import { Scenarios } from '../pages/Scenarios';
import { DataQuality } from '../pages/DataQuality';
import { Assistant } from '../pages/Assistant';
import { About } from '../pages/About';
import { WorkspaceProvider } from './Workspace';
import { AssistantDrawer } from '../features/assistant/AssistantDrawer';
import { NewDataset } from '../features/imports/NewDataset';

const navigation = [
  ['/', 'Overview', '◫'],
  ['/products', 'Products', '▦'],
  ['/forecasts', 'Forecasts', '⌁'],
  ['/replenishment', 'Replenishment', '↗'],
  ['/scenarios', 'Scenario lab', '◇'],
  ['/quality', 'Data quality', '✓'],
  ['/assistant', 'Assistant', '✦'],
  ['/about', 'Methodology', '≡'],
];

export function App() {
  const [selected, setSelected] = useState('');
  const session = useQuery({
    queryKey: ['session'],
    queryFn: () => post<{ mode: string }>('/session', {}),
    staleTime: Infinity,
  });
  const datasets = useQuery({
    queryKey: ['datasets'],
    queryFn: () => api<List<Dataset> & { app_mode: string }>('/datasets?page_size=100'),
    enabled: session.isSuccess,
  });
  const id = selected || datasets.data?.items[0]?.id || '';
  const summary = useQuery({
    queryKey: ['summary', id],
    queryFn: () => api<Summary>(`/datasets/${id}/summary`),
    enabled: !!id,
  });
  const refetchSummary = summary.refetch;
  const refresh = useCallback(() => {
    void refetchSummary();
  }, [refetchSummary]);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [id]);
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <div className="shell">
        <aside className="sidebar">
          <NavLink to="/" className="brand">
            <span className="brand-mark">
              S<span>↗</span>
            </span>
            <span>
              StockPilot<small>INVENTORY WORKSPACE</small>
            </span>
          </NavLink>
          <p className="nav-caption">WORKSPACE</p>
          <nav aria-label="Main navigation">
            {navigation.map(([path, label, icon]) => (
              <NavLink key={path} to={path} end={path === '/'}>
                <span aria-hidden="true">{icon}</span>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-footer">
            <span className="badge low">Portfolio demo</span>
            <p>
              Clear forecasts.
              <br />
              Explainable decisions.
            </p>
            <small>Laura Poveda Nicolás</small>
          </div>
        </aside>
        <div className="workspace">
          <header className="topbar">
            <span className="breadcrumb">
              Workspace <span>/</span> Inventory planning
            </span>
            <label className="dataset-label">
              Dataset
              <select
                aria-label="Selected dataset"
                value={id}
                onChange={(e) => setSelected(e.target.value)}
              >
                {datasets.data?.items.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            {datasets.data?.app_mode === 'local' && (
              <NewDataset
                onCreated={(dataset) => {
                  setSelected(dataset.id);
                  void datasets.refetch();
                }}
              />
            )}
          </header>
          <main id="main" tabIndex={-1}>
            <ErrorState error={session.error || datasets.error || summary.error} />
            {(datasets.isLoading || summary.isLoading || session.isLoading) && <Loading />}
            {datasets.data?.items.length === 0 && (
              <Empty>
                No dataset yet. Create a CSV dataset above, or run <code>make demo</code> to prepare
                the reproducible synthetic workspace.
              </Empty>
            )}
            {summary.data && (
              <WorkspaceProvider
                key={id}
                value={{
                  dataset: summary.data.dataset,
                  summary: summary.data,
                  readOnly: datasets.data?.app_mode === 'public_demo',
                  refresh,
                }}
              >
                <div className="context">
                  <span className="badge mode">{summary.data.dataset.mode} data</span>
                  <span>As of {date(summary.data.dataset.as_of_date)}</span>
                  <span>GBP · Europe/London</span>
                  <span title="Origin of the current inventory snapshot">
                    Operations: {summary.data.snapshot?.origin || 'No inventory imported'}
                  </span>
                </div>
                <AssistantDrawer />
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/products" element={<Products />} />
                  <Route path="/products/:id" element={<ProductDetail />} />
                  <Route path="/forecasts" element={<Forecasts />} />
                  <Route path="/replenishment" element={<Replenishment />} />
                  <Route path="/scenarios" element={<Scenarios />} />
                  <Route path="/quality" element={<DataQuality />} />
                  <Route path="/assistant" element={<Assistant />} />
                  <Route path="/about" element={<About />} />
                  <Route
                    path="*"
                    element={<Empty>Page not found. Select a workspace page.</Empty>}
                  />
                </Routes>
              </WorkspaceProvider>
            )}
          </main>
          <footer className="page-footer">
            StockPilot · A personal project by Laura Poveda Nicolás{' '}
            <span>Sales are a proxy for demand.</span>
          </footer>
        </div>
      </div>
    </>
  );
}
