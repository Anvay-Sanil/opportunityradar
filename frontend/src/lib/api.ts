export function getApiBase(value = ''): string {
  const base = value.trim().replace(/\/+$/, '');
  if (!base) return '/api';
  return base.endsWith('/api') ? base : `${base}/api`;
}

const API_BASE = getApiBase(import.meta.env.VITE_API_URL);

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.';
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token');
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...options, headers, signal: options.signal ?? AbortSignal.timeout(45000),
    });
  } catch {
    throw new ApiError('Unable to reach the service. Check your connection and try again.', 0);
  }
  if (res.status === 204) return undefined as T;
  if (!res.headers.get('content-type')?.includes('json')) {
    throw new ApiError('The service is unavailable. Please try again shortly.', res.ok ? 502 : res.status);
  }
  let body: any;
  try { body = await res.json(); }
  catch { throw new ApiError('The service returned an incomplete response. Please try again.', 502); }
  if (!res.ok) {
    const detail = Array.isArray(body?.detail)
      ? body.detail.map((item: any) => item.msg || 'Invalid input').join('; ')
      : body?.detail;
    throw new ApiError(typeof detail === 'string' ? detail : 'Request failed. Please try again.', res.status);
  }
  return body as T;
}

export const api = {
  auth: {
    register: (data: { email: string; password: string; full_name: string }) =>
      request<{ access_token: string; user: any }>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    login: (data: { email: string; password: string }) =>
      request<{ access_token: string; user: any }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    me: () => request<any>('/auth/me'),
  },
  profile: {
    get: () => request<any>('/profile'),
    upsert: (data: any) =>
      request<any>('/profile', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    delete: () =>
      request<void>('/profile', { method: 'DELETE' }),
  },
  opportunities: {
    list: (params?: Record<string, string | number>) => {
      const qs = params
        ? '?' + new URLSearchParams(
            Object.entries(params).map(([k, v]) => [k, String(v)])
          ).toString()
        : '';
      return request<{ items: any[]; total: number; page: number; page_size: number; total_pages: number; catalog_total?: number }>(
        `/opportunities${qs}`
      );
    },
    getMatches: (params?: Record<string, string | number>) => {
      const qs = params
        ? '?' + new URLSearchParams(
            Object.entries(params).map(([k, v]) => [k, String(v)])
          ).toString()
        : '';
      return request<{ items: any[]; total: number }>(`/opportunities/match${qs}`);
    },
    get: (id: string) => request<any>(`/opportunities/${id}`),
  },
  applications: {
    list: (params?: Record<string, string>) => {
      const qs = params ? '?' + new URLSearchParams(params).toString() : '';
      return request<{ items: any[]; total: number }>(`/applications${qs}`);
    },
    create: (data: { opportunity_id: string; notes?: string }) =>
      request<any>('/applications', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (id: string, data: any) =>
      request<any>(`/applications/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<void>(`/applications/${id}`, { method: 'DELETE' }),
    stats: () => request<any>('/applications/stats'),
  },
  digest: {
    checkUnsubscribe: (token: string) => request<{ message: string }>(`/digest/unsubscribe?token=${encodeURIComponent(token)}`),
    unsubscribe: (token: string) => request<{ message: string }>('/digest/unsubscribe', {
      method: 'POST', body: JSON.stringify({ token }),
    }),
    getPreferences: () => request<any>('/digest/preferences'),
    updatePreferences: (data: any) =>
      request<any>('/digest/preferences', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    getLogs: (limit = 10) =>
      request<any[]>(`/digest/logs?limit=${limit}`),
  },
  admin: {
    triggerScrape: () =>
      request<{ message: string; task_id: string }>('/admin/scrape', {
        method: 'POST',
      }),
  },
};
