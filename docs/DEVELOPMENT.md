# MarketLens

Simulation-only quantitative finance portfolio project. Phases 1 through 4 implement
the Python analytics engine, market-data integration and versioned FastAPI
endpoints. The original welcome and health routes are preserved. No brokerage or
live execution functionality is provided.

## Run locally (PowerShell, repository root)

```powershell
.\backend\.venv\Scripts\python.exe -m pytest
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Runtime dependencies are in `backend/requirements.txt`; development dependencies
are in `backend/requirements-dev.txt`. These are version ranges, not a deployment
lockfile. The existing virtual environment is preserved and ignored by Git.
The phase 1 tests also support unittest; the full suite requires pytest. Tests
mock Yahoo and do not depend on an internet connection. On Windows, the async
test loop still needs permission to create local sockets.

```python
from backend.quant import daily_returns, simulate_gbm, summarize_simulation, black_scholes

returns = daily_returns([100, 102, 101])
paths = simulate_gbm(spot=100, drift=0.07, volatility=0.2, seed=42)
summary = summarize_simulation(paths)
option = black_scholes(100, 100, 1, 0.05, 0.2)
```

## Calculation conventions and limitations

- Inputs use decimal rates (0.20 means 20%) and years. Prices must be positive,
  finite and chronological. Supply consistently adjusted observations; the engine
  numerical functions do not sort, fill missing observations, or fetch data. The
  separate market-data service sorts provider history and validates its contents.
- `daily_returns` produces adjacent simple returns, or log returns when requested.
  Daily spacing is the caller's responsibility. Sample volatility uses `ddof=1`
  and square-root annualization, defaulting to 252 observations per year.
- Risk functions consume simple returns. Sharpe uses sample standard deviation;
  Sortino uses the root mean square of negative excess returns over **all**
  observations. The annual effective risk-free rate is compounded down to each
  period. Undefined ratios return `None`, not infinity. Square-root scaling assumes
  sufficiently independent, stable returns and may mislead with serial correlation.
- Historical VaR is the linearly interpolated quantile of losses (`-returns`).
  CVaR averages the worst empirical tail mass, weighting its boundary fractionally.
  Both are one-observation-horizon decimal losses and may be negative for gain-only
  samples. Small samples provide unreliable tail estimates.
- Maximum drawdown is a nonnegative fraction of peak compounded wealth and includes
  initial capital. A -100% return is ruin; returns below -100% are rejected.
- GBM uses exact lognormal time increments with annual arithmetic drift and constant
  annual volatility. Output shape is `(steps + 1, paths)`, including initial prices.
  It ignores jumps, stochastic volatility, transaction costs, and regime shifts.
  Default seed is 42; a local NumPy generator avoids global RNG side effects.
  Reproducibility assumes the same dependencies and parameters. Five million path
  values is the allocation limit; intermediate arrays require additional memory.
- Simulation interval bounds are central empirical **prediction intervals** for
  terminal prices, not confidence intervals for a fitted parameter or mean.
  Loss probability counts prices strictly below the initial price. Monte Carlo
  sampling error and parameter-estimation uncertainty remain.
- Black-Scholes-Merton assumes European exercise, continuous dividend yield,
  constant rates/volatility, frictionless markets, and lognormal dynamics. Rates
  and dividend yields are continuously compounded. Delta and gamma are per price
  unit; vega and rho are per absolute 1.0 change (divide by 100 for a percentage
  point); theta is per calendar year (divide by 365 for a day). Expired options and
  zero volatility are rejected because this API returns smooth-model Greeks too.
- Nonfinite inputs and invalid dimensions raise `ValueError`. Extreme simulation
  and option inputs outside floating-point range are rejected. This engine is not
  investment advice or a validated production risk system.

Implementation references: [NumPy random generators](https://numpy.org/doc/2.1/reference/random/)
and [SciPy normal distribution](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.norm.html).

## Incremental roadmap

1. **Complete:** returns, volatility, historical risk, seeded GBM, options/Greeks,
   numerical regression tests and existing-route integration tests.
2. **Complete:** market data/search and validated FastAPI analytics endpoints; provider mocking,
   useful error responses, caching and environment-based configuration.
3. **Complete:** portfolio management calculations, constrained mean-variance optimization, and
   backtesting with lagged signals, costs and explicit look-ahead checks.
4. **Complete:** responsive React/TypeScript dashboard, Tailwind, Recharts and frontend tests.
5. **Implemented; PostgreSQL/Docker runtime verification pending:** SQLAlchemy saved
   portfolios, Alembic migrations, frontend persistence controls and Docker Compose.
6. Optional C++/pybind11 GBM implementation, parity tests and reproducible benchmarks
   before making performance claims.

Major new dependency installations and destructive changes require approval.
Secrets belong in environment variables; do not commit credentials or build outputs.

## Phase 2 HTTP API

Start the server from the repository root using the command above, then open
`http://127.0.0.1:8000/docs` for interactive request and response schemas.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Existing welcome response |
| GET | `/health` | Process health (does not probe Yahoo) |
| GET | `/api/v1/stocks/search?q=Apple&limit=10` | Equity/ETF symbol search |
| GET | `/api/v1/stocks/AAPL/history?start=2025-01-01&end=2025-02-01` | Adjusted OHLC, volume, simple returns and annualized volatility |
| POST | `/api/v1/analytics/risk` | Historical risk metrics from supplied simple returns |
| POST | `/api/v1/simulations/gbm` | Seeded simulation, prediction bands and histogram |
| POST | `/api/v1/options/black-scholes` | European option price and Greeks |

Example requests in PowerShell:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/stocks/search?q=Apple&limit=5'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/stocks/AAPL/history?start=2025-01-01&end=2025-02-01'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/analytics/risk' -Method Post -ContentType 'application/json' -Body '{"returns":[0.01,-0.02,0.015],"confidence":0.95}'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/simulations/gbm' -Method Post -ContentType 'application/json' -Body '{"spot":100,"drift":0.07,"volatility":0.2,"steps":252,"paths":1000,"seed":42}'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/options/black-scholes' -Method Post -ContentType 'application/json' -Body '{"spot":100,"strike":100,"years":1,"rate":0.05,"volatility":0.2,"option_type":"call"}'
```

History uses an inclusive start and exclusive end, with a maximum range of 3660
calendar days. Symbols are normalized to uppercase; search supports company names.
Bars retain the exchange-local trading date, are sorted, and use yfinance's explicit
`auto_adjust=True`. Adjusted prices may change with corporate actions; volume is
provider-reported. Currency is not converted or inferred. Missing volume is null;
missing/nonpositive OHLC or duplicate dates cause a provider-data error instead of
fabricated returns. Returns align with the later observation. A single bar has no
returns; fewer than three bars has null sample volatility. No calendar gap filling
is performed. Yahoo coverage, freshness and availability are not guaranteed.

Market responses carry a UTC `fetched_at` timestamp and source label. The bounded,
thread-safe cache stores successful results (including empty searches), expires
after its TTL and is separate for each process. Cached timestamps reflect the
original download. Cache misses are serialized to avoid duplicate fetches and
concurrent provider-state changes; this limits market-data throughput. The provider
timeout applies to individual requests, not an overall endpoint deadline or queue
wait. There are no automatic retries. A shared cache and stronger concurrency
controls are deferred to deployment work.

Simulation responses contain at most 20 sample paths, each as a time series, plus
pointwise lower/median/upper prediction bands from **all** paths. Bands are not
simultaneous path confidence bands. `times` is in years. Terminal histograms use
counts and bin edges (last bin includes its right edge). Counts sum to `paths`;
they are not density values. Full path matrices are not transmitted. Limits are
2520 steps, 100000 paths, five million total path values, and a 30-year horizon;
the product limit applies even if no sample paths are requested. API constraints
also bound rates, prices and returns; OpenAPI documents every bound. These limits
do not replace deployment-level request-size, concurrency and rate limits.

Errors use a `detail` property: input validation returns 422 with field locations,
and numerical-domain errors return 422 with a calculation message. Market errors
return `{ "detail": { "code": "...", "message": "..." } }`: 404 for unavailable
history, 502 for invalid/unavailable upstream responses, and 503 with `Retry-After`
for upstream rate limits. A missing-data response is not proof that a ticker is
delisted. Internal provider exception details are not exposed. Undefined risk
ratios serialize as JSON null. No analytics endpoint silently downloads data or
estimates GBM parameters; clients explicitly provide inputs.

### Environment configuration

`.env.example` documents supported variables. Configuration reads the process
environment at application creation; `.env` files are not loaded automatically.

| Variable | Default | Meaning |
| --- | --- | --- |
| `MARKETLENS_MARKET_TIMEOUT_SECONDS` | `10` | Per-provider-request timeout, >0 and <=60 |
| `MARKETLENS_CACHE_TTL_SECONDS` | `300` | Cache lifetime; 0 disables caching |
| `MARKETLENS_CACHE_MAX_ENTRIES` | `128` | Maximum cached query/range results |
| `MARKETLENS_CORS_ORIGINS` | empty | Comma-separated permitted browser origins |

For the later Vite frontend, set `$env:MARKETLENS_CORS_ORIGINS='http://localhost:5173'`
before starting the backend. Invalid settings fail startup. CORS allows only GET
and POST with Content-Type and does not enable credentials. These endpoints are
currently unauthenticated; deployment controls remain a later phase.

Phase 2 verification: 68 pytest tests pass, including provider-mocked integration
tests, cache expiry/eviction, invalid/missing data, error mapping, request bounds,
OpenAPI and CORS. A live Yahoo download has not been verified. The existing
Starlette/httpx test-client deprecation warning remains; no dependency upgrade was
performed solely to silence it.

Provider contract references: [yfinance history implementation](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py),
[yfinance search implementation](https://github.com/ranaroussi/yfinance/blob/main/yfinance/search.py),
and [FastAPI parameter validation](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/).

## Phase 3: portfolios and historical backtesting

Three additional POST endpoints are documented interactively in `/docs`:

| Path | Purpose |
| --- | --- |
| `/api/v1/portfolios/analyze` | Analyze supplied weights and aligned asset returns |
| `/api/v1/portfolios/optimize` | Minimum variance with an optional minimum target return |
| `/api/v1/backtests/sma` | Long/cash moving-average crossover with next-close execution |

Portfolio example (body for `portfolios/analyze`):

```json
{
  "assets": ["AAA", "BBB"],
  "dates": ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"],
  "returns": [[-0.01, -0.02], [-0.01, 0.02], [0.01, -0.02], [0.01, 0.02]],
  "weights": [0.6, 0.4],
  "periods_per_year": 252
}
```

For `portfolios/optimize`, omit `weights` and optionally add `max_weight` (default
1) and `target_return` (annual arithmetic return, default null). Each return row
must follow the asset order and refer to the same holding interval across all
assets. Dates label interval ends; input must be strictly chronological with no
duplicates. The API checks shape and chronology but cannot verify that the supplied
returns were actually calculated over matching intervals. Missing observations
must be aligned by the caller, without forward-looking fills. Up to 50 assets and
10000 observations are accepted. Assets must use a common currency; no FX conversion
is performed. Inputs are supplied explicitly and are not saved in this phase.

Portfolio weights are long-only, nonnegative and sum to one. Analytics applies
these weights every period, assuming costless rebalancing, not fixed-share holdings.
`equity` starts with initial normalized capital 1 and therefore has one more entry
than `dates`; subsequent entries align with the return dates. Expected annual return
is the sample mean times periods per year, not CAGR. Covariance uses sample `ddof=1`
and linear annualization. Risk metrics use the same conventions as phase 1.

Optimization minimizes annualized sample variance with sum-to-one and per-asset
weight-cap constraints. An optional target imposes a **minimum**, not an exact
expected return. The maximum achievable return under the cap is checked first;
solver failure and infeasible results return 422. Singular covariance matrices are
supported, but solutions may be nonunique. No inverse covariance, shrinkage or
forecast model is assumed. The solver uses
[SciPy SLSQP](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html).
Outputs are in-sample estimates sensitive to the chosen history. They are not a
walk-forward strategy evaluation; fitting on a full history and evaluating those
weights on the same history would introduce selection bias.

Backtest example:

```json
{
  "dates": ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08"],
  "prices": [100, 110, 120, 90, 80],
  "short_window": 1,
  "long_window": 2,
  "initial_capital": 10000,
  "transaction_cost_bps": 10
}
```

The SMA signal is 1 when the trailing short mean exceeds the trailing long mean,
otherwise 0. Warm-up and equal means produce cash signals. A signal observed after
close `t` executes at close `t+1`; exposure earns the move from `t+1` to `t+2`.
Orders use the prior signal, with no access to the execution day's closing price
when deciding whether to trade. This intentionally skips the first move after a
new signal and does not pretend a close-derived signal can fill at that same close.
No parameter optimization or future-dependent signal calculation is performed.

The ledger buys fractional shares with available cash including the fee, or sells
all shares and deducts the fee. Costs are basis points of traded notional per side
(10 bps = 0.1%), with no daily charge when holding. Cash earns zero. There is no
leverage, short selling, tax, volume limit, spread or market-impact model; fees may
serve as a simple friction approximation. Adjusted prices can be used as synthetic
total-return prices, but quantities then are not literal corporate-action-adjusted
brokerage holdings. Price history must be positive, consistent and already adjusted
as desired. Timing protection does not remove survivorship bias, historical-data
revisions, parameter selection bias or unrealistic fill assumptions.

`equity`, `signals`, post-trade `positions`, `fees`, and benchmark equity align with
input dates; interval `returns` aligns with dates starting at the second date.
Trade `index` identifies its execution date in that array. The last signal remains
unfilled when no later close exists. Open holdings are marked to market at the
final close without forced liquidation or a hypothetical exit fee. The buy-and-hold
benchmark signals immediately at the first observation, buys at the second close
with identical costs, and holds; it does not wait for strategy warm-up. Summary
metrics include the full sample, including time spent in cash.

Phase 3 validation: **104 tests pass**, plus 25 subtests, covering analytic portfolio
solutions, caps and targets, degenerate covariance, rejected solver failures,
cash/share accounting, future-data perturbations, prefix invariance and API input
validation. No new dependencies were installed. Portfolio CRUD/persistence remains
in the PostgreSQL phase; this phase provides the calculation and simulation APIs.

## Phase 4: research dashboard

The `frontend` directory contains a React/TypeScript/Vite application with Tailwind
CSS and Recharts. Six views cover market search/history, seeded GBM simulations,
historical risk, European options, portfolio analysis/optimization and SMA
backtesting. Loading, empty, validation and provider-error states are explicit.
Editing inputs clears previous results, and superseded requests are aborted.

Start the backend from the repository root in one PowerShell terminal:

```powershell
Set-Location D:\marketlens
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Start the frontend in a second terminal:

```powershell
Set-Location D:\marketlens\frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The development proxy forwards `/api` and `/health`
to port 8000, so CORS configuration is unnecessary for this setup. If that backend
port is occupied, start Uvicorn with `--port 8001` and set
`$env:MARKETLENS_DEV_API_URL='http://127.0.0.1:8001'` before `npm run dev`.
The connection badge can be clicked to recheck backend health. It does not measure
Yahoo availability. Requests have a 90-second client timeout; aborting a request
does not guarantee already-running server calculations stop.

For a separately hosted backend, set `VITE_API_BASE_URL` at build time and configure
the backend's `MARKETLENS_CORS_ORIGINS`. Vite-prefixed variables are public; never
put secrets in them. Production hosting must reverse-proxy `/api` and `/health`
when the base URL is blank. `npm run preview` serves the build for inspection, but
is not a production deployment server. Docker deployment remains the next phase.

```powershell
npm test
npm run build
```

The committed `package-lock.json` supports repeatable installs with `npm ci`.
Dependencies, npm cache and build output are ignored. No global packages were
installed. The production build performs a strict TypeScript check first and
loads charting code on demand.

Portfolio and backtest views accept editable CSV or a local file (maximum 5 MB).
CSV is parsed in the browser; parsed observations are sent to the backend only
when an analysis is submitted. Use plain comma-separated columns without quoted
fields: portfolio headers are `date,AAA,BBB`, backtest headers are `date,price`.
Dates must be ISO dates in increasing order. Empty numeric cells and duplicate
dates/assets are rejected. Prefilled CSV and return inputs are clearly labeled
synthetic examples, not downloaded market data. Portfolios are not persisted yet.

Forms display rates and volatility as percentages and convert them to API decimal
fractions. CSV returns and portfolio weights remain decimal fractions. Option
Greeks display vega/rho per percentage point and theta per calendar day. Prices
are shown without an assumed currency symbol. Simulation charts distinguish
pointwise prediction bounds, sample paths and terminal-price bin counts.

Validation: frontend interaction/parser/network tests, production TypeScript/Vite
build and all 104 backend tests pass. Local frontend and backend HTTP smoke checks
also passed. Browser screenshot/layout verification was attempted but Chrome's
debugging endpoint was unavailable in the sandbox; visual browser QA remains
unverified. Component tests mock chart layout because JSDOM has no layout engine.
The prior backend test-client deprecation warning remains.

## Phase 5: saved portfolios and deployment

The portfolio dashboard now supports save, load, update and confirmed deletion,
including applying optimized weights before saving. SQLAlchemy models and Alembic
migrations support PostgreSQL; an explicit SQLite development configuration is also
provided. Updates and deletes use optimistic version checks to prevent silent
overwrites. The remaining analytics APIs continue to work without storage configured.

See **`deploy/README.md`** for the D-drive directory map, database setup, local start
script, API contracts, Compose commands, storage limitations and backup procedures.
All newly installed packages and their caches were placed under `D:\marketlens`.
No Docker installation or disk migration has been performed.

Validation: **119 backend tests passed, one PostgreSQL test skipped; 21 frontend
tests and the production build passed.** Docker/PostgreSQL execution still requires
an installed runtime and a verified D-drive disk location. Do not treat SQLite test
results as proof that the Docker/PostgreSQL deployment has run.
