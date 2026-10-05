import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useWorkspace } from '../app/Workspace';
import { ErrorState, JobStatus } from '../components/ui/States';
import { api, post, scope, useJob } from '../lib/api';
import type { Batch, Job, Preview } from '../types/api';

const fields: Record<string, string[]> = {
  sales: [
    'external_row_id',
    'invoice_id',
    'product_sku',
    'description',
    'quantity',
    'unit_price',
    'invoice_datetime',
    'country',
  ],
  inventory: [
    'product_sku',
    'on_hand_units',
    'reserved_units',
    'unit_cost',
    'currency',
    'supplier_code',
    'lead_time_days',
    'pack_size',
    'minimum_order_units',
    'holding_cost_per_unit_day',
    'stockout_penalty_per_unit',
  ],
  inbound: ['external_order_id', 'product_sku', 'quantity_units', 'expected_arrival_date'],
};
export function DataQuality() {
  const { dataset, summary, readOnly, refresh } = useWorkspace();
  const [kind, setKind] = useState('sales'),
    [file, setFile] = useState<File | null>(null),
    [headers, setHeaders] = useState<string[]>([]),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [excluded, setExcluded] = useState<number[]>([]),
    [complete, setComplete] = useState(false),
    [jobId, setJobId] = useState<string | null>(null);
  const preview = useMutation({
    mutationFn: () => {
      const form = new FormData();
      if (file) form.append('file', file);
      form.append('kind', kind);
      form.append('mapping', JSON.stringify(mapping));
      return api<Preview>(`/datasets/${dataset.id}/imports/preview`, {
        method: 'POST',
        body: form,
      });
    },
    onSuccess: () => setExcluded([]),
  });
  const confirm = useMutation({
    mutationFn: () =>
      post<Job>(`/datasets/${dataset.id}/imports/confirm`, {
        token: preview.data?.token,
        excluded_rows: excluded,
        idempotency_key: preview.data?.checksum,
        last_day_complete: complete,
      }),
    onSuccess: (job) => setJobId(job.id),
  });
  const job = useJob(jobId, dataset.id);
  const report = useQuery({
    queryKey: ['import-report', job.data?.result_id],
    queryFn: () => api<Batch>(scope(`/imports/${job.data?.result_id}`, dataset.id)),
    enabled: job.data?.status === 'succeeded' && !!job.data.result_id,
  });
  useEffect(() => {
    if (job.data?.status === 'succeeded') refresh();
  }, [job.data?.status, refresh]);
  async function chooseFile(chosen: File | null) {
    setFile(chosen);
    preview.reset();
    confirm.reset();
    setJobId(null);
    if (!chosen) {
      setHeaders([]);
      return;
    }
    const text = await chosen.slice(0, 8192).text();
    const line = text.split(/\r?\n/)[0].replace(/^\uFEFF/, '');
    const columns = line
      .split(line.includes(';') ? ';' : ',')
      .map((h) => h.replace(/^"|"$/g, '').trim());
    setHeaders(columns);
    setMapping({});
  }
  function downloadTemplate() {
    const url = URL.createObjectURL(
      new Blob([fields[kind].join(',') + '\n'], { type: 'text/csv;charset=utf-8' }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = `stockpilot-${kind}-template.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
  const errors = preview.data?.report.errors ?? [];
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">TRUST STARTS WITH THE SOURCE</p>
          <h1>Data quality</h1>
          <p>Preview, validate and confirm. Import batches keep their provenance.</p>
        </div>
        <button onClick={downloadTemplate}>Download CSV template ↓</button>
      </div>
      <div className="two-columns">
        <section className="panel">
          <h2>Source & coverage</h2>
          <dl>
            <dt>Source</dt>
            <dd>{String(dataset.provenance.source ?? 'Imported CSV')}</dd>
            <dt>License</dt>
            <dd>{String(dataset.provenance.license ?? 'User-supplied; verify permissions')}</dd>
            <dt>Reference date</dt>
            <dd>{dataset.as_of_date} · complete local days</dd>
            <dt>Currency / timezone</dt>
            <dd>
              {dataset.currency} / {dataset.timezone}
            </dd>
            <dt>Operations</dt>
            <dd>Stock, costs, suppliers and lead times in prepared datasets are simulated.</dd>
          </dl>
          <p>
            Returns and cancellations remain in the audit trail; they do not subtract from forecast
            demand.
          </p>
        </section>
        <section className="panel">
          <h2>Import CSV</h2>
          {readOnly ? (
            <p className="notice">
              Shared demo is read-only. Download templates and run locally to import your own files.
            </p>
          ) : (
            <>
              <label>
                File type
                <select
                  value={kind}
                  onChange={(e) => {
                    setKind(e.target.value);
                    setFile(null);
                    setHeaders([]);
                    preview.reset();
                  }}
                >
                  <option value="sales">Sales</option>
                  <option value="inventory">Inventory</option>
                  <option value="inbound">Pending orders</option>
                </select>
              </label>
              <label>
                UTF-8 CSV · maximum 10 MiB
                <input
                  key={kind}
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(e) => {
                    void chooseFile(e.target.files?.[0] ?? null);
                  }}
                />
              </label>
              <p className="fineprint">
                Comma or semicolon delimiter. Decimal point. ISO dates. SKU remains text, including
                leading zeroes.
              </p>
              {file && (
                <>
                  <details open>
                    <summary>Map columns</summary>
                    <div className="mapping">
                      {fields[kind].map((field) => (
                        <label key={field}>
                          {field}
                          <select
                            value={mapping[field] ?? (headers.includes(field) ? field : '')}
                            onChange={(e) => {
                              setMapping({ ...mapping, [field]: e.target.value });
                              preview.reset();
                            }}
                          >
                            <option value="">No column</option>
                            {headers.map((h) => (
                              <option key={h}>{h}</option>
                            ))}
                          </select>
                        </label>
                      ))}
                    </div>
                  </details>
                  <button
                    className="primary"
                    disabled={preview.isPending}
                    onClick={() => preview.mutate()}
                  >
                    Preview & validate
                  </button>
                </>
              )}
              <ErrorState error={preview.error || confirm.error} />
            </>
          )}
        </section>
      </div>
      {preview.data && (
        <section className="panel">
          <h2>Preview · {preview.data.status}</h2>
          <p>
            {preview.data.report.received} received · {preview.data.report.valid} structurally valid
            · {errors.length} blocking errors · {preview.data.report.exclusions.length} demand
            exclusions.
          </p>
          {errors.length > 0 && (
            <div className="notice danger">
              <p>
                Exclude invalid rows explicitly to continue. The report will record these
                exclusions.
              </p>
              {errors.map((error, index) => (
                <label className="checkbox" key={`${error.row}-${index}`}>
                  <input
                    type="checkbox"
                    checked={excluded.includes(error.row)}
                    onChange={(e) =>
                      setExcluded(
                        e.target.checked
                          ? [...excluded, error.row]
                          : excluded.filter((n) => n !== error.row),
                      )
                    }
                  />
                  Row {error.row}: {error.message}
                </label>
              ))}
            </div>
          )}
          {preview.data.report.warnings.map((w, i) => (
            <p className="notice" key={i}>
              Row {w.row}: {w.message}
            </p>
          ))}
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Scrollable data table"
          >
            <table>
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Normalized values · first 25 rows</th>
                </tr>
              </thead>
              <tbody>
                {preview.data.report.rows?.map((row) => (
                  <tr key={row.row}>
                    <td>{row.row}</td>
                    <td>
                      <code>{JSON.stringify(row.values)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {kind === 'sales' && (
            <label className="checkbox">
              <input
                type="checkbox"
                checked={complete}
                onChange={(e) => setComplete(e.target.checked)}
              />
              I confirm the final local sales day is complete. Otherwise it is excluded from
              forecasting.
            </label>
          )}
          <button
            className="primary"
            disabled={confirm.isPending || errors.some((e) => !excluded.includes(e.row)) || !!jobId}
            onClick={() => confirm.mutate()}
          >
            Confirm this preview
          </button>
        </section>
      )}
      <JobStatus job={job.data} error={job.error} />
      {report.data && (
        <div className="notice" role="status">
          Import {report.data.status} · {report.data.report.written} rows written. Reimporting
          identical content and mapping returns this batch.
        </div>
      )}
      <section className="panel">
        <h2>Import audit trail</h2>
        {summary.quality.length ? (
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Scrollable data table"
          >
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Received</th>
                  <th>Written</th>
                  <th>Checksum</th>
                </tr>
              </thead>
              <tbody>
                {summary.quality.map((batch) => (
                  <tr key={batch.id}>
                    <td>{batch.kind}</td>
                    <td>{batch.status}</td>
                    <td>{batch.report.received}</td>
                    <td>{batch.report.written ?? 'Not confirmed'}</td>
                    <td>
                      <code>{batch.checksum.slice(0, 16)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No CSV batches. The prepared dataset was created by the reproducible generator.</p>
        )}
      </section>
    </>
  );
}
