import { expect, it, vi } from 'vitest';
import { api, errorMessage } from './api';
it('preserves provider error messages', () => {
  expect(errorMessage({ detail: { code: 'provider_unavailable', message: 'Retry later.' } })).toBe('Retry later.');
  expect(errorMessage({ detail: [{ loc: ['body', 'returns', 0], msg: 'Invalid value' }] })).toContain('returns.0: Invalid value');
});
it('serializes POST inputs and rejects unsuccessful responses', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Invalid weights' }), { status: 422 }));
  vi.stubGlobal('fetch', fetcher);
  await expect(api('/api/v1/portfolios/analyze', { weights: [2] })).rejects.toThrow('Invalid weights');
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ weights: [2] });
});
it('explains connection failures', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
  await expect(api('/health')).rejects.toThrow('Check that the backend is running');
});
