import type { ReactNode } from 'react';
import type { Job, Numeric } from '../../types/api';

export function ErrorState({ error }: { error: Error | null | undefined }) {
  return error ? (
    <div className="notice danger" role="alert">
      {error.message}
    </div>
  ) : null;
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
export function Loading() {
  return (
    <div className="loading" role="status">
      Loading your inventory workspace…
    </div>
  );
}
export function Risk({ value }: { value: Numeric | null }) {
  const level =
    value == null
      ? 'unavailable'
      : Number(value) >= 0.5
        ? 'high'
        : Number(value) >= 0.2
          ? 'medium'
          : 'low';
  return (
    <span className={`badge ${level}`}>
      {level === 'unavailable' ? 'Not available' : `${level} risk`}
    </span>
  );
}
export function JobStatus({ job, error }: { job: Job | undefined; error?: Error | null }) {
  return (
    <>
      <ErrorState error={error} />
      {job && (
        <div className={`notice ${job.status === 'failed' ? 'danger' : ''}`} role="status">
          <strong>{job.status}</strong> · {job.stage} · {job.progress}%
          {job.error && <p>{job.error}</p>}
          <progress value={job.progress} max={100} />
        </div>
      )}
    </>
  );
}
