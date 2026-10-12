import { fireEvent, render, screen, waitFor, renderHook, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import App from './App';
import { useJob } from './ui';

// Test chart input integration without relying on JSDOM's nonexistent layout engine.
vi.mock('recharts', () => {
  const Wrapper = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  const Empty = () => null;
  return { ResponsiveContainer: Wrapper, LineChart: Wrapper, BarChart: Wrapper,
    CartesianGrid: Empty, Line: Empty, XAxis: Empty, YAxis: Empty, Tooltip: Empty, Legend: Empty, Bar: Empty };
});
function mockApi(result: unknown, status = 200) {
  const fetcher = vi.fn().mockImplementation((url: string) => Promise.resolve(new Response(
    JSON.stringify(url.endsWith('/health') ? { status: 'ok' } : url.includes('/saved-portfolios?') ? { items: [], total: 0, offset: 0, limit: 10 } : result),
    { status: url.endsWith('/health') ? 200 : status, headers: { 'Content-Type': 'application/json' } })));
  vi.stubGlobal('fetch', fetcher); return fetcher;
}
it('shows all research views without fabricated market data', async () => {
  const fetcher = mockApi({}); render(<App />);
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('See the market clearly');
  expect(screen.getByText('Your next insight starts here')).toBeVisible();
  expect(screen.getByRole('navigation')).toBeVisible();
  await screen.findByText('API connected');
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it('prices options and scales Greek units for display', async () => {
  const fetcher = mockApi({ price: 10.45, delta: .637, gamma: .018, vega: 37.5, theta: -6.4, rho: 53.2 });
  render(<App />); const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'Options pricing' }));
  await user.click(screen.getByRole('button', { name: /Price option/ }));
  expect(await screen.findByText('10.45')).toBeVisible();
  const call = fetcher.mock.calls.find(call => call[0].includes('black-scholes'))!;
  expect(JSON.parse(call[1].body)).toMatchObject({ rate: .05, volatility: .2, option_type: 'call' });
  expect(screen.getByText('0.375')).toBeVisible();
  await user.clear(screen.getByLabelText('Spot price'));
  expect(screen.queryByText('10.45')).not.toBeInTheDocument();
});
it('renders provider failure and allows another attempt', async () => {
  mockApi({ detail: { code: 'provider_rate_limited', message: 'Provider is rate limited; retry later.' } }, 503);
  render(<App />); await userEvent.click(screen.getByRole('button', { name: /Load market history/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('rate limited');
  expect(screen.getByRole('button', { name: /Load market history/ })).toBeEnabled();
});
it('submits normalized portfolio CSV and optimizer constraints', async () => {
  const fetcher = mockApi({ assets: ['AAA','BBB'], weights: [.8,.2], expected_annual_return: 0, annualized_volatility: .1 });
  render(<App />); const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'Portfolios' }));
  await user.selectOptions(screen.getByLabelText('Analysis mode'), 'optimize');
  await user.click(screen.getByRole('button', { name: /Optimize allocation/ }));
  expect(await screen.findByText('80%')).toBeVisible();
  const call = fetcher.mock.calls.find(call => call[0].includes('/optimize'))!;
  expect(JSON.parse(call[1].body)).toMatchObject({ assets: ['AAA','BBB'], max_weight: 1, target_return: null });
});
it('rejects malformed CSV before making an analytics request', async () => {
  const fetcher = mockApi({}); render(<App />); const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: 'Backtesting' }));
  fireEvent.change(screen.getByLabelText('Data CSV'), { target: { value: 'bad input' } });
  await user.click(screen.getByRole('button', { name: /Run backtest/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('CSV needs');
  expect(fetcher.mock.calls.filter(call => call[0].includes('/backtests'))).toHaveLength(0);
});
it('does not let a late response replace a newer result', async () => {
  const { result } = renderHook(() => useJob<string>());
  let resolveOld!: (value: string) => void;
  act(() => { void result.current.run(() => new Promise(resolve => { resolveOld = resolve; })); });
  await act(async () => { await result.current.run(async () => 'new'); });
  await act(async () => { resolveOld('old'); });
  await waitFor(() => expect(result.current.data).toBe('new'));
  expect(result.current.busy).toBe(false);
});
