import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '../lib/api';
import { OpportunitiesPage } from './OpportunitiesPage';
import { UnsubscribePage } from './UnsubscribePage';
import { ApplicationsPage } from './ApplicationsPage';

describe('failure and unsubscribe flows', () => {
  it('distinguishes an empty catalog from filters with no results', async () => {
    vi.spyOn(api.opportunities, 'list').mockResolvedValue({ items: [], total: 0, catalog_total: 0, page: 1, page_size: 20, total_pages: 1 });
    render(<MemoryRouter><OpportunitiesPage /></MemoryRouter>);
    expect(await screen.findByText('No internships have been imported yet')).toBeTruthy();
    expect(screen.queryByText('Try adjusting your filters')).toBeNull();
    expect(screen.getByRole('button', { name: 'Refresh listings' })).toBeTruthy();
  });

  it('lets users clear a search when the catalog has internships', async () => {
    const list = vi.spyOn(api.opportunities, 'list').mockResolvedValue({ items: [], total: 0, catalog_total: 10, page: 1, page_size: 20, total_pages: 1 });
    render(<MemoryRouter><OpportunitiesPage /></MemoryRouter>);
    await screen.findByText('No opportunities match your criteria');
    const search = screen.getByPlaceholderText('Search by title, company, skills...');
    fireEvent.change(search, { target: { value: 'unknown' } });
    await screen.findByText('No opportunities match your criteria');
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect((search as HTMLInputElement).value).toBe('');
    expect(list).toHaveBeenCalledWith(expect.objectContaining({ search: 'unknown' }));
  });

  it('does not disguise a failed listings request as no opportunities', async () => {
    vi.spyOn(api.opportunities, 'list').mockRejectedValue(new ApiError('Service unavailable', 503));
    render(<MemoryRouter><OpportunitiesPage /></MemoryRouter>);
    expect((await screen.findByRole('alert')).textContent).toContain('Service unavailable');
    expect(screen.queryByText('No opportunities match your criteria')).toBeNull();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
  });

  it('requires confirmation before persisting unsubscribe', async () => {
    vi.spyOn(api.digest, 'checkUnsubscribe').mockResolvedValue({ message: 'Confirm' });
    const unsubscribe = vi.spyOn(api.digest, 'unsubscribe').mockResolvedValue({ message: 'Done' });
    render(<MemoryRouter initialEntries={['/unsubscribe?token=signed']}><UnsubscribePage /></MemoryRouter>);
    const button = await screen.findByRole('button', { name: 'Unsubscribe' });
    expect(unsubscribe).not.toHaveBeenCalled();
    fireEvent.click(button);
    expect(await screen.findByText('You are unsubscribed')).toBeTruthy();
    expect(unsubscribe).toHaveBeenCalledWith('signed');
  });

  it('shows a retry instead of an empty application pipeline during an outage', async () => {
    vi.spyOn(api.applications, 'list').mockRejectedValue(new ApiError('Unable to load applications', 503));
    vi.spyOn(api.applications, 'stats').mockResolvedValue({ total: 0 });
    render(<MemoryRouter><ApplicationsPage /></MemoryRouter>);
    expect((await screen.findByRole('alert')).textContent).toContain('Unable to load applications');
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy();
    expect(screen.queryByText('0 applications tracked')).toBeNull();
  });
});
