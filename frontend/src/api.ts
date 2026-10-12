const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export function errorMessage(payload: unknown): string {
  if (!payload || typeof payload !== 'object' || !('detail' in payload)) return 'The request failed. Please try again.';
  const detail = payload.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => `${item.loc?.slice(1).join('.') || 'Input'}: ${item.msg}`).join('; ');
  if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message);
  return 'The request failed. Please try again.';
}

export async function api<T>(path: string, body?: unknown, signal?: AbortSignal, method?: 'PUT' | 'DELETE'): Promise<T> {
  const timeout = AbortSignal.timeout(90_000);
  let response: Response;
  try {
    response = await fetch(base + path, {
      method: method ?? (body === undefined ? 'GET' : 'POST'),
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error(timeout.aborted ? 'Request timed out. Try fewer observations or retry later.' : 'Cannot reach MarketLens. Check that the backend is running.');
  }
  if (response.status === 204 && response.ok) return undefined as T;
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorMessage(payload));
  if (payload === null) throw new Error('The server returned an unreadable response.');
  return payload as T;
}

export interface History {
  symbol: string; fetched_at: string; source: string; annualized_volatility: number | null;
  prices: { date: string; close: number; volume: number | null }[];
  returns: { date: string; value: number }[];
}
export interface Risk {
  annualized_volatility: number; sharpe_ratio: number | null; sortino_ratio: number | null;
  value_at_risk: number; conditional_value_at_risk: number; maximum_drawdown: number;
}
export interface Simulation {
  seed: number; paths: number; times: number[]; lower_band: number[]; median_band: number[]; upper_band: number[];
  sample_paths: number[][];
  summary: { mean_terminal_price: number; lower_terminal_price: number; upper_terminal_price: number; loss_probability: number };
  terminal_distribution: { bin_edges: number[]; counts: number[] };
}
export interface Option { price: number; delta: number; gamma: number; theta: number; vega: number; rho: number }
export interface Portfolio extends Partial<Risk> {
  assets: string[]; weights: number[]; expected_annual_return: number; annualized_volatility: number;
  equity?: number[]; dates?: string[]; total_return?: number;
}
export interface Backtest {
  dates: string[]; equity: number[]; benchmark_equity: number[]; total_return: number;
  benchmark_total_return: number; maximum_drawdown: number; total_fees: number;
  trades: { index: number; side: string; price: number; quantity: number; fee: number }[];
}
