import { useEffect, useRef, useState } from 'react';
import PortfolioStorage, { type PortfolioDefinition } from './PortfolioStorage';
import { api, type History, type Risk, type Simulation, type Option, type Portfolio, type Backtest } from './api';
import { number, pct, numeric, text, numericList, parseCsv, portfolioExample, backtestExample } from './data';
import { Chart, CsvInput, Field, Metrics, Num, Panel, Status, Submit, formData, useJob } from './ui';

function Market() {
  const search = useJob<{ results: { symbol: string; name: string; exchange: string | null }[] }>();
  const history = useJob<History>();
  const [symbol, setSymbol] = useState('AAPL');
  const end = new Date().toISOString().slice(0, 10);
  const start = new Date(Date.now() - 365 * 86400000).toISOString().slice(0, 10);
  return <><div className="workspace"><Panel title="Find an asset" note="Equities & ETFs"><form onSubmit={event => { const f = formData(event); search.run(signal => api(`/api/v1/stocks/search?q=${encodeURIComponent(text(f, 'query'))}&limit=6`, undefined, signal)); }}>
    <Field label="Company or ticker" name="query" placeholder="Search Apple, Microsoft…" maxLength={80} /><Submit busy={search.busy}>Search assets</Submit></form>
    <Status busy={search.busy} error={search.error} />{search.data && <div className="search-results">{search.data.results.length ? search.data.results.map(item => <button key={item.symbol} onClick={() => { setSymbol(item.symbol); history.clear(); }}><strong>{item.symbol}</strong><span>{item.name}</span><small>{item.exchange}</small></button>) : <p>No matching equities or ETFs.</p>}</div>}
    <div className="divider" /><form onChange={history.clear} onSubmit={event => { const f = formData(event); history.run(signal => api(`/api/v1/stocks/${encodeURIComponent(symbol)}/history?start=${text(f, 'start')}&end=${text(f, 'end')}`, undefined, signal)); }}>
      <Field label="Selected symbol" value={symbol} onChange={event => setSymbol(event.target.value.toUpperCase())} pattern="[A-Z0-9^][A-Z0-9.^=\-]{0,19}" />
      <div className="field-row"><Field label="Start date" type="date" name="start" defaultValue={start} /><Field label="End (exclusive)" type="date" name="end" defaultValue={end} /></div><Submit busy={history.busy}>Load market history</Submit></form>
    <p className="footnote">Adjusted daily prices from Yahoo Finance. Availability and freshness may vary.</p></Panel>
    <Panel title={history.data ? `${history.data.symbol} · Market history` : 'Market history'} note="Daily · Adjusted close"><Status busy={history.busy} error={history.error} empty={!history.data} />{history.data && <>
      <Metrics items={[["Latest adjusted close", number(history.data.prices.at(-1)?.close)], ['Annualized volatility', pct(history.data.annualized_volatility)], ['Observations', String(history.data.prices.length)]]} />
      <Chart data={history.data.prices.map(p => ({ x: p.date, close: p.close }))} series={[{ key: 'close', name: 'Adjusted close (quote currency)' }]} />
      <p className="footnote">Fetched {new Date(history.data.fetched_at).toLocaleString()} · {history.data.source}</p>
      <Chart data={history.data.returns.map(p => ({ x: p.date, returns: p.value * 100 }))} series={[{ key: 'returns', name: 'Daily return (%)' }]} /></>}</Panel></div></>;
}

function Simulations() {
  const job = useJob<Simulation>();
  return <div className="workspace"><Panel title="Simulation parameters" note="Geometric Brownian Motion"><form onChange={job.clear} onSubmit={event => { const f = formData(event); job.run(signal => api('/api/v1/simulations/gbm', {
    spot: numeric(f, 'spot'), drift: numeric(f, 'drift') / 100, volatility: numeric(f, 'volatility') / 100,
    years: numeric(f, 'years'), steps: numeric(f, 'steps'), paths: numeric(f, 'paths'), seed: numeric(f, 'seed'), confidence: numeric(f, 'confidence') / 100, sample_paths: 5 }, signal)); }}>
    <Num label="Initial price" name="spot" value={100} min={0.000001} /><div className="field-row"><Num label="Annual drift (%)" name="drift" value={7} min={-500} max={500} /><Num label="Volatility (%)" name="volatility" value={20} min={0} max={500} /></div>
    <div className="field-row"><Num label="Horizon (years)" name="years" value={1} min={0.001} max={30} /><Num label="Time steps" name="steps" value={252} min={1} max={2520} step={1} /></div>
    <div className="field-row"><Num label="Paths" name="paths" value={1000} min={1} max={100000} step={1} /><Num label="Random seed" name="seed" value={42} min={0} max={9007199254740991} step={1} /></div><Num label="Prediction interval (%)" name="confidence" value={95} min={0.01} max={99.99} /><Submit busy={job.busy}>Run simulation</Submit></form><p className="footnote">Constant drift and volatility. No jumps or transaction costs. The seed makes runs reproducible; these are model scenarios, not forecasts.</p></Panel>
    <Panel title="Simulated outcomes" note="Prediction bands & terminal distribution"><Status busy={job.busy} error={job.error} empty={!job.data} />{job.data && <>
      <Metrics items={[["Mean terminal price", number(job.data.summary.mean_terminal_price)], ['Loss probability', pct(job.data.summary.loss_probability)], ['Terminal interval', `${number(job.data.summary.lower_terminal_price)} – ${number(job.data.summary.upper_terminal_price)}`]]} />
      <Chart data={job.data.times.map((t, i) => ({ x: Number(t.toFixed(3)), lower: job.data!.lower_band[i], median: job.data!.median_band[i], upper: job.data!.upper_band[i] }))} series={[{ key: 'median', name: 'Median' }, { key: 'lower', name: 'Lower bound' }, { key: 'upper', name: 'Upper bound' }]} />
      <p className="footnote">Horizon in years · Pointwise prediction bounds, not confidence intervals for a fitted mean.</p>
      <Chart data={job.data.times.map((t, i) => ({ x: Number(t.toFixed(3)), ...Object.fromEntries(job.data!.sample_paths.map((path, j) => [`path${j}`, path[i]])) }))} series={job.data.sample_paths.map((_, i) => ({ key: `path${i}`, name: `Sample path ${i+1}` }))} />
      <Chart histogram data={job.data.terminal_distribution.counts.map((count, i) => ({ x: number((job.data!.terminal_distribution.bin_edges[i] + job.data!.terminal_distribution.bin_edges[i+1]) / 2), count }))} series={[{ key: 'count', name: 'Paths per terminal-price bin' }]} />
      <p className="footnote">{job.data.paths.toLocaleString()} simulated paths · Seed {job.data.seed}</p></>}</Panel></div>;
}

function RiskView() {
  const job = useJob<Risk>();
  return <div className="workspace"><Panel title="Return history" note="Decimal simple returns"><form onChange={job.clear} onSubmit={event => { const f = formData(event); job.run(signal => api('/api/v1/analytics/risk', { returns: numericList(text(f, 'returns')), risk_free_rate: numeric(f, 'rate') / 100, confidence: numeric(f, 'confidence') / 100, periods_per_year: numeric(f, 'periods') }, signal)); }}>
    <label className="field"><span>Returns (comma or space separated)</span><textarea name="returns" rows={7} required defaultValue="0.01, -0.02, 0.015, -0.005, 0.012, 0.003" /></label><p className="footnote">Synthetic sample inputs · 0.01 represents a 1% return.</p>
    <Num label="Annual risk-free rate (%)" name="rate" value={0} min={-99.99} max={1000} /><Num label="Observations per year" name="periods" value={252} min={1} max={365} step={1} /><Num label="Tail confidence (%)" name="confidence" value={95} min={0.01} max={99.99} /><Submit busy={job.busy}>Calculate risk</Submit></form></Panel>
    <Panel title="Risk profile" note="Historical estimates"><Status busy={job.busy} error={job.error} empty={!job.data} />{job.data && <><Metrics items={[
      ['Annualized volatility', pct(job.data.annualized_volatility)], ['Sharpe ratio', number(job.data.sharpe_ratio)], ['Sortino ratio', number(job.data.sortino_ratio)], ['Value at risk', pct(job.data.value_at_risk)], ['Conditional VaR', pct(job.data.conditional_value_at_risk)], ['Maximum drawdown', pct(job.data.maximum_drawdown)]]} />
      <div className="explanation"><h3>Reading the results</h3><p>VaR and CVaR are one-observation losses. A negative value represents a gain. Drawdown measures the largest fall from peak compounded wealth.</p><p>Undefined ratios appear as —. Historical tail estimates are especially sensitive to small samples.</p></div></>}</Panel></div>;
}

function Options() {
  const job = useJob<Option>();
  return <div className="workspace"><Panel title="European option" note="Black–Scholes–Merton"><form onChange={job.clear} onSubmit={event => { const f = formData(event); job.run(signal => api('/api/v1/options/black-scholes', { spot: numeric(f, 'spot'), strike: numeric(f, 'strike'), years: numeric(f, 'years'), rate: numeric(f, 'rate') / 100, volatility: numeric(f, 'volatility') / 100, dividend_yield: numeric(f, 'yield') / 100, option_type: text(f, 'type') }, signal)); }}>
    <label className="field"><span>Contract type</span><select name="type"><option value="call">Call option</option><option value="put">Put option</option></select></label>
    <div className="field-row"><Num label="Spot price" name="spot" value={100} min={0.000001} /><Num label="Strike price" name="strike" value={100} min={0.000001} /></div><Num label="Time to expiry (years)" name="years" value={1} min={0.000001} max={30} /><Num label="Volatility (%)" name="volatility" value={20} min={0.000001} max={500} /><div className="field-row"><Num label="Risk-free rate (%)" name="rate" value={5} min={-100} max={100} /><Num label="Dividend yield (%)" name="yield" value={0} min={-100} max={100} /></div><Submit busy={job.busy}>Price option</Submit></form><p className="footnote">European exercise, continuous dividend yield, constant rates and volatility. Expired and zero-volatility contracts are excluded.</p></Panel>
    <Panel title="Valuation & sensitivities" note="Per option unit"><Status busy={job.busy} error={job.error} empty={!job.data} />{job.data && <><div className="price-hero"><span>Theoretical value</span><strong>{number(job.data.price)}</strong><small>In the same currency as spot and strike</small></div><Metrics items={[["Delta", number(job.data.delta)], ['Gamma', number(job.data.gamma)], ['Vega / 1% vol', number(job.data.vega / 100)], ['Theta / day', number(job.data.theta / 365)], ['Rho / 1% rate', number(job.data.rho / 100)]]} /><p className="footnote">Theta uses 365 calendar days. Vega and rho are scaled to a one-percentage-point change.</p></>}</Panel></div>;
}

function Portfolios() {
  const job = useJob<Portfolio>();
  const [csv, setCsv] = useState(portfolioExample);
  const [mode, setMode] = useState('analyze');
  const form = useRef<HTMLFormElement>(null);
  const [defaults, setDefaults] = useState({ weights: '0.6, 0.4', periods: 252, rate: 0, revision: 0 });
  const loadDefinition = (definition: PortfolioDefinition) => {
    job.clear(); setMode('analyze');
    setCsv([['date', ...definition.assets].join(','), ...definition.dates.map((date, i) => [date, ...definition.returns[i]].join(','))].join('\n'));
    setDefaults(previous => ({ weights: definition.weights.join(', '), periods: definition.periods_per_year, rate: definition.risk_free_rate*100, revision: previous.revision+1 }));
  };
  const getDefinition = (): PortfolioDefinition => {
    if (!form.current) throw new Error('Portfolio form is unavailable.');
    const f = new FormData(form.current), data = parseCsv(csv, 'portfolio');
    return { assets: data.assets, dates: data.dates, returns: data.returns,
      weights: numericList(text(f, 'weights')), periods_per_year: numeric(f, 'periods'), risk_free_rate: numeric(f, 'risk_free_rate')/100 };
  };
  return <div className="workspace"><Panel title="Portfolio laboratory" note="Aligned return observations"><form ref={form} key={defaults.revision} onChange={job.clear} onSubmit={event => { const f = formData(event); job.run(signal => {
    const parsed = parseCsv(csv, 'portfolio');
    const common = { assets: parsed.assets, dates: parsed.dates, returns: parsed.returns, periods_per_year: numeric(f, 'periods') };
    return api(`/api/v1/portfolios/${mode}`, mode === 'analyze' ? { ...common, weights: numericList(text(f, 'weights')), risk_free_rate: numeric(f, 'risk_free_rate')/100 } : { ...common, max_weight: numeric(f, 'cap') / 100, target_return: text(f, 'target') ? numeric(f, 'target') / 100 : null }, signal);
  }); }}>
    <label className="field"><span>Analysis mode</span><select value={mode} onChange={event => { setMode(event.target.value); job.clear(); }}><option value="analyze">Analyze allocation</option><option value="optimize">Optimize minimum variance</option></select></label>
    <CsvInput value={csv} onChange={value => { setCsv(value); job.clear(); }} /><p className="footnote">Synthetic example. CSV: date, then one column per asset containing decimal returns. Align the holding intervals and currency.</p>
    {mode === 'analyze' ? <><Field label="Weights in asset order (sum to 1)" name="weights" defaultValue={defaults.weights} /><Num label="Annual risk-free rate (%)" name="risk_free_rate" value={defaults.rate} min={-99.99} max={1000} /></> : <><Num label="Maximum asset weight (%)" name="cap" value={100} min={0.01} max={100} /><Field label="Minimum annual return (%) — optional" type="number" name="target" step="any" required={false} placeholder="No target" /></>}
    <Num label="Observations per year" name="periods" value={defaults.periods} min={1} max={365} step={1} /><Submit busy={job.busy}>{mode === 'analyze' ? 'Analyze portfolio' : 'Optimize allocation'}</Submit></form>
    <PortfolioStorage canSave={mode === 'analyze'} getDefinition={getDefinition} onLoad={loadDefinition} /></Panel>
    <Panel title="Allocation & performance" note="Long-only · Fully invested"><Status busy={job.busy} error={job.error} empty={!job.data} />{job.data && <><Metrics items={[["Expected annual return", pct(job.data.expected_annual_return)], ['Annualized volatility', pct(job.data.annualized_volatility)], ...(job.data.total_return === undefined ? [] : [['Total historical return', pct(job.data.total_return)] as [string, string]])]} />
      <div className="allocation">{job.data.assets.map((asset, i) => <div key={asset}><div><strong>{asset}</strong><span>{pct(job.data!.weights[i])}</span></div><div className="weight-track"><div style={{ width: `${job.data!.weights[i]*100}%` }} /></div></div>)}</div>
      {mode === 'optimize' && <button type="button" className="secondary" onClick={() => { const data = parseCsv(csv, 'portfolio'); const periods = numeric(new FormData(form.current!), 'periods'); loadDefinition({ assets: data.assets, dates: data.dates, returns: data.returns, weights: job.data!.weights, periods_per_year: periods, risk_free_rate: 0 }); }}>Use optimized weights in analysis</button>}
      {job.data.equity && <Chart data={job.data.equity.map((value, i) => ({ x: i === 0 ? 'Initial' : job.data!.dates![i-1], equity: value }))} series={[{ key: 'equity', name: 'Normalized wealth' }]} />}
      <p className="footnote">In-sample estimates, not forecasts. Analysis assumes costless rebalancing every period. Optimization does not constitute an out-of-sample backtest.</p></>}</Panel></div>;
}

function Backtests() {
  const job = useJob<Backtest>();
  const [csv, setCsv] = useState(backtestExample);
  return <div className="workspace"><Panel title="Strategy inputs" note="Moving-average crossover"><form onChange={job.clear} onSubmit={event => { const f = formData(event); job.run(signal => { const data = parseCsv(csv, 'prices'); return api('/api/v1/backtests/sma', { dates: data.dates, prices: data.prices, short_window: numeric(f, 'short'), long_window: numeric(f, 'long'), initial_capital: numeric(f, 'capital'), transaction_cost_bps: numeric(f, 'cost'), periods_per_year: numeric(f, 'periods') }, signal); }); }}>
    <CsvInput value={csv} onChange={value => { setCsv(value); job.clear(); }} /><p className="footnote">Synthetic example. Import chronological, consistently adjusted prices with date,price headers.</p>
    <div className="field-row"><Num label="Short window" name="short" value={1} min={1} max={9999} step={1} /><Num label="Long window" name="long" value={2} min={2} max={9999} step={1} /></div>
    <Num label="Initial capital" name="capital" value={10000} min={1} max={1e12} /><Num label="Cost per trade (bps)" name="cost" value={10} min={0} max={1000} /><Num label="Observations per year" name="periods" value={252} min={1} max={365} step={1} /><Submit busy={job.busy}>Run backtest</Submit></form></Panel>
    <Panel title="Strategy performance" note="Next-close execution"><Status busy={job.busy} error={job.error} empty={!job.data} />{job.data && <><Metrics items={[["Strategy return", pct(job.data.total_return)], ['Buy & hold return', pct(job.data.benchmark_total_return)], ['Maximum drawdown', pct(job.data.maximum_drawdown)], ['Total fees', number(job.data.total_fees)]]} />
      <Chart data={job.data.dates.map((date, i) => ({ x: date, strategy: job.data!.equity[i], benchmark: job.data!.benchmark_equity[i] }))} series={[{ key: 'strategy', name: 'SMA strategy' }, { key: 'benchmark', name: 'Buy & hold' }]} />
      <h3 className="table-title">Trade ledger <span>{job.data.trades.length} executions</span></h3><div className="table-scroll"><table><thead><tr><th>Date</th><th>Side</th><th>Price</th><th>Quantity</th><th>Fee</th></tr></thead><tbody>{job.data.trades.slice(0, 200).map((trade, i) => <tr key={i}><td>{job.data!.dates[trade.index]}</td><td>{trade.side}</td><td>{number(trade.price)}</td><td>{number(trade.quantity)}</td><td>{number(trade.fee)}</td></tr>)}</tbody></table>{job.data.trades.length === 0 && <p>No trades were triggered.</p>}{job.data.trades.length > 200 && <p>Showing the first 200 executions.</p>}</div>
      <p className="footnote">Signals execute at the following close. Cash earns zero; open holdings are marked to market without forced liquidation. Buy & hold enters at the second close and does not wait for SMA warm-up.</p></>}</Panel></div>;
}

const pages = [
  { name: 'Market overview', icon: '◈', title: 'See the market clearly.', description: 'Explore adjusted prices and the risk behind every return.', component: Market },
  { name: 'Monte Carlo', icon: '⌁', title: 'Explore the range of possibilities.', description: 'Turn explicit assumptions into reproducible price scenarios.', component: Simulations },
  { name: 'Risk analytics', icon: '◫', title: 'Understand the downside.', description: 'Measure historical volatility, tail losses and risk-adjusted returns.', component: RiskView },
  { name: 'Options pricing', icon: 'ƒ', title: 'Price the possibilities.', description: 'European option valuation and sensitivities, with clear assumptions.', component: Options },
  { name: 'Portfolios', icon: '▥', title: 'Build a considered allocation.', description: 'Analyze portfolio risk and explore constrained minimum variance.', component: Portfolios },
  { name: 'Backtesting', icon: '↶', title: 'Put a strategy to the test.', description: 'Follow the signals, account for costs and inspect every execution.', component: Backtests },
];
export default function App() {
  const [page, setPage] = useState(0);
  const [health, setHealth] = useState('Checking API');
  const [healthTick, setHealthTick] = useState(0);
  useEffect(() => { const control = new AbortController(); api<{ status: string }>('/health', undefined, control.signal).then(result => { if (!control.signal.aborted) setHealth(result.status === 'ok' ? 'API connected' : 'API unavailable'); }).catch(() => { if (!control.signal.aborted) setHealth('API unavailable'); }); return () => control.abort(); }, [healthTick]);
  const Page = pages[page].component;
  return <div className="app-shell"><a className="skip-link" href="#main">Skip to workspace</a><aside className="sidebar"><a className="brand" href="#" onClick={event => { event.preventDefault(); setPage(0); }}><span className="brand-mark">M<span>↗</span></span>MarketLens<span className="brand-dot">.</span></a><div className="nav-label">RESEARCH WORKSPACE</div><nav aria-label="Main navigation">{pages.map((item, index) => <button key={item.name} aria-current={page === index ? 'page' : undefined} onClick={() => setPage(index)}><span aria-hidden="true">{item.icon}</span>{item.name}{page === index && <i />}</button>)}</nav><div className="sidebar-bottom"><div className="lab-badge">◉ QUANT RESEARCH LAB</div><p>Models to explore.<br />Evidence to understand.</p><small>Simulation only · No live trading</small></div></aside>
    <div className="main-shell"><header className="topbar"><span>Workspace <span className="slash">/</span> <strong>{pages[page].name}</strong></span><button className="connection" onClick={() => { setHealth('Checking API'); setHealthTick(t => t+1); }} title="Check backend connection"><span className={health === 'API connected' ? 'dot online' : 'dot'} />{health}</button></header><main id="main"><div className="intro"><div><div className="eyebrow">MARKETLENS / ANALYTICS</div><h1>{pages[page].title}</h1><p>{pages[page].description}</p></div><span className="research-tag">RESEARCH MODE</span></div><Page key={page} /><footer>MarketLens <span>Quantitative research · Transparent assumptions · Reproducible results</span></footer></main></div></div>;
}
