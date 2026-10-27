import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('API transport', () => {
  beforeEach(() => { vi.resetModules(); vi.stubEnv('VITE_API_URL', 'https://backend.example/api/'); });

  it('normalizes origins and preserves the development proxy', async () => {
    const { getApiBase } = await import('./api');
    expect(getApiBase('')).toBe('/api');
    expect(getApiBase('https://backend.example///')).toBe('https://backend.example/api');
    expect(getApiBase('https://backend.example/api/')).toBe('https://backend.example/api');
  });

  it('sends authentication to the configured backend', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"id":"user"}', { headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetch);
    localStorage.setItem('token', 'session');
    const { api } = await import('./api');
    await api.auth.me();
    expect(fetch.mock.calls[0][0]).toBe('https://backend.example/api/auth/me');
    expect(fetch.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer session');
  });

  it('shows a service error for an HTML SPA fallback', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<!doctype html>', { headers: { 'content-type': 'text/html' } })));
    const { api, ApiError } = await import('./api');
    await expect(api.auth.me()).rejects.toMatchObject({ status: 502, name: 'ApiError' });
  });

  it('formats validation errors as readable text', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":[{"msg":"Password is too long"}]}', {
      status: 422, headers: { 'content-type': 'application/json' },
    })));
    const { api } = await import('./api');
    await expect(api.auth.login({ email: 'a@example.com', password: 'long' })).rejects.toMatchObject({ status: 422, message: 'Password is too long' });
  });

  it('handles invalid JSON and network failures without deleting credentials', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response('{', { headers: { 'content-type': 'application/json' } }))
      .mockRejectedValueOnce(new TypeError('network'));
    vi.stubGlobal('fetch', fetch);
    localStorage.setItem('token', 'session');
    const { api } = await import('./api');
    await expect(api.auth.me()).rejects.toMatchObject({ status: 502 });
    await expect(api.auth.me()).rejects.toMatchObject({ status: 0 });
    expect(localStorage.getItem('token')).toBe('session');
  });

  it('accepts an empty 204 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const { api } = await import('./api');
    await expect(api.applications.delete('id')).resolves.toBeUndefined();
  });
});
