import { useQuery } from '@tanstack/react-query';
import type { Job } from '../types/api';

export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
    public requestId?: string,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: 'same-origin',
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body: { error?: { message: string; code: string; request_id: string } } = await response
      .json()
      .catch(() => ({}));
    throw new APIError(
      body.error?.message ?? 'Cannot reach StockPilot. Check the API and database.',
      response.status,
      body.error?.code ?? 'NETWORK_ERROR',
      body.error?.request_id,
    );
  }
  return response.json() as Promise<T>;
}
export const post = <T>(path: string, data: unknown) =>
  api<T>(path, { method: 'POST', body: JSON.stringify(data) });
export const scope = (path: string, dataset: string) =>
  `${path}${path.includes('?') ? '&' : '?'}dataset_id=${encodeURIComponent(dataset)}`;

export function useJob(id: string | null, dataset: string) {
  return useQuery({
    queryKey: ['job', id, dataset],
    queryFn: () => api<Job>(scope(`/jobs/${id}`, dataset)),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'failed' || status === 'succeeded') return false;
      return query.state.error ? 8000 : 2000;
    },
    refetchIntervalInBackground: false,
  });
}
