"""Synchronous routes run blocking provider and numerical work off the event loop."""
from dataclasses import asdict
from typing import Annotated
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from backend.quant import (annualized_volatility, daily_returns, sharpe_ratio,
    sortino_ratio, value_at_risk, conditional_value_at_risk, maximum_drawdown,
    simulate_gbm, summarize_simulation, black_scholes)
from backend.quant.market_data import MarketDataService
from .schemas import (HistoryQuery, HistoryResponse, SearchResponse, RiskRequest,
    RiskResponse, SimulationRequest, SimulationResponse, OptionRequest, OptionResponse)

router = APIRouter(prefix='/api/v1')


def market_service(request: Request) -> MarketDataService:
    return request.app.state.market_data


@router.get('/stocks/search', response_model=SearchResponse, tags=['Market data'])
def search_stocks(q: Annotated[str, Query(min_length=1, max_length=80)],
                  service: Annotated[MarketDataService, Depends(market_service)],
                  limit: Annotated[int, Query(ge=1, le=20)] = 10):
    query = q.strip()
    if not query or any(ord(char) < 32 for char in query):
        raise HTTPException(422, 'q must contain a nonempty search term without control characters')
    return service.search(query, limit)


@router.get('/stocks/{symbol}/history', response_model=HistoryResponse, tags=['Market data'])
def stock_history(symbol: Annotated[str, Path(pattern=r'^[A-Za-z0-9^][A-Za-z0-9.^=\-]{0,19}$')],
                  dates: Annotated[HistoryQuery, Query()],
                  service: Annotated[MarketDataService, Depends(market_service)]):
    result = service.history(symbol.upper(), dates.start, dates.end)
    bars = result['prices']
    returns = daily_returns([bar['close'] for bar in bars]) if len(bars) > 1 else np.array([])
    result['returns'] = [dict(date=bar['date'], value=float(value))
                         for bar, value in zip(bars[1:], returns)]
    result['annualized_volatility'] = annualized_volatility(returns) if len(returns) >= 2 else None
    return result


def calculate(function, *args, **kwargs):
    """Convert expected numerical-domain failures into actionable client errors."""
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            return function(*args, **kwargs)
    except (ValueError, OverflowError, FloatingPointError) as exc:
        raise HTTPException(422, f'Calculation cannot be completed: {exc}') from exc


@router.post('/analytics/risk', response_model=RiskResponse, tags=['Analytics'])
def risk_metrics(body: RiskRequest):
    values, rate, periods = body.returns, body.risk_free_rate, body.periods_per_year
    return dict(observations=len(values), periods_per_year=periods, confidence=body.confidence,
        annualized_volatility=calculate(annualized_volatility, values, periods),
        sharpe_ratio=calculate(sharpe_ratio, values, rate, periods),
        sortino_ratio=calculate(sortino_ratio, values, rate, periods),
        value_at_risk=calculate(value_at_risk, values, body.confidence),
        conditional_value_at_risk=calculate(conditional_value_at_risk, values, body.confidence),
        maximum_drawdown=calculate(maximum_drawdown, values))


@router.post('/simulations/gbm', response_model=SimulationResponse, tags=['Simulations'])
def gbm_simulation(body: SimulationRequest):
    prices = calculate(simulate_gbm, **body.model_dump(exclude={'confidence', 'sample_paths'}))
    summary = calculate(summarize_simulation, prices, body.confidence)
    tail = (1 - body.confidence) / 2
    bands = np.quantile(prices, [tail, .5, 1-tail], axis=1)
    counts, edges = np.histogram(prices[-1], bins=min(50, max(1, int(np.sqrt(body.paths)))))
    return dict(seed=body.seed, paths=body.paths, engine=body.engine,
        times=np.linspace(0, body.years, body.steps + 1).tolist(),
        sample_paths=prices[:, :body.sample_paths].T.tolist(),
        lower_band=bands[0].tolist(), median_band=bands[1].tolist(), upper_band=bands[2].tolist(),
        summary=asdict(summary), terminal_distribution=dict(bin_edges=edges.tolist(), counts=counts.tolist()))


@router.post('/options/black-scholes', response_model=OptionResponse, tags=['Options'])
def price_option(body: OptionRequest):
    return asdict(calculate(black_scholes, **body.model_dump()))
