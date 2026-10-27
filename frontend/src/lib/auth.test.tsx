import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { api, ApiError } from './api';
import { AuthProvider, useAuth } from './auth';

function Consumer() {
  const { user, sessionError, retrySession, loading } = useAuth();
  return <><span>{loading ? 'Loading' : user?.full_name || 'Signed out'}</span>
    {sessionError && <p role="alert">{sessionError}</p>}
    <button onClick={retrySession}>Retry</button></>;
}

describe('session recovery', () => {
  it('preserves a token on a temporary outage and recovers on retry', async () => {
    localStorage.setItem('token', 'session');
    const me = vi.spyOn(api.auth, 'me').mockRejectedValueOnce(new ApiError('Service unavailable', 503))
      .mockResolvedValueOnce({ id: 'user', full_name: 'Test User' });
    render(<AuthProvider><Consumer /></AuthProvider>);
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(localStorage.getItem('token')).toBe('session');
    fireEvent.click(screen.getByText('Retry'));
    expect(await screen.findByText('Test User')).toBeTruthy();
    expect(me).toHaveBeenCalledTimes(2);
  });

  it('clears a token only when the API rejects authentication', async () => {
    localStorage.setItem('token', 'invalid');
    vi.spyOn(api.auth, 'me').mockRejectedValue(new ApiError('Invalid credentials', 401));
    render(<AuthProvider><Consumer /></AuthProvider>);
    await screen.findByText('Signed out');
    await waitFor(() => expect(localStorage.getItem('token')).toBeNull());
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
