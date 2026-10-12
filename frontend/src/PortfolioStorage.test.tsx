import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import PortfolioStorage, { type PortfolioDefinition } from './PortfolioStorage';

const definition: PortfolioDefinition = { assets: ['AAA'], dates: ['2025-01-01','2025-01-02'], returns: [[.01],[.02]], weights: [1], periods_per_year: 252, risk_free_rate: 0 };
const saved = { id: 'abc', name: 'Saved research', notes: '', version: 3, updated_at: '2025-01-01T00:00:00Z', definition };
function setup() {
  const onLoad = vi.fn();
  const fetcher = vi.fn().mockImplementation((url: string, options: RequestInit) => {
    const payload = options.method === 'DELETE' ? null : url.includes('?limit=') ? { items: [saved], total: 1, offset: 0, limit: 10 } : saved;
    return Promise.resolve(new Response(payload ? JSON.stringify(payload) : null, { status: options.method === 'DELETE' ? 204 : 200 }));
  });
  vi.stubGlobal('fetch', fetcher);
  render(<PortfolioStorage canSave getDefinition={() => definition} onLoad={onLoad} />);
  return { fetcher, onLoad, user: userEvent.setup() };
}
it('loads saved inputs and sends the original version when updating', async () => {
  const { fetcher, onLoad, user } = setup();
  await user.click(await screen.findByRole('button', { name: /Saved research/ }));
  expect(onLoad).toHaveBeenCalledWith(definition);
  await user.click(screen.getByRole('button', { name: 'Update selected' }));
  await screen.findByText('Portfolio updated.');
  const call = fetcher.mock.calls.find(call => call[1].method === 'PUT')!;
  expect(JSON.parse(call[1].body)).toMatchObject({ version: 3, definition });
});
it('requires explicit confirmation before deleting', async () => {
  const { fetcher, user } = setup();
  await user.click(await screen.findByRole('button', { name: /Saved research/ }));
  await user.click(screen.getByRole('button', { name: 'Delete selected' }));
  expect(fetcher.mock.calls.some(call => call[1].method === 'DELETE')).toBe(false);
  await user.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(screen.queryByRole('button', { name: 'Confirm delete' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Delete selected' }));
  await user.click(screen.getByRole('button', { name: 'Confirm delete' }));
  await screen.findByText(/Saved portfolio deleted/);
  expect(fetcher.mock.calls.find(call => call[1].method === 'DELETE')![0]).toContain('?version=3');
});
it('shows conflict errors without silently overwriting', async () => {
  const { fetcher, user } = setup();
  await user.click(await screen.findByRole('button', { name: /Saved research/ }));
  fetcher.mockImplementationOnce(() => Promise.resolve(new Response(JSON.stringify({ detail: 'Reload before saving.' }), { status: 409 })));
  await user.click(screen.getByRole('button', { name: 'Update selected' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Reload before saving.');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Update selected' })).toBeEnabled());
});
