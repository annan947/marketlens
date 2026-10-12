"""Explicit input and response contracts for OpenAPI and frontend clients."""
from datetime import date, datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Finite = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Positive = Annotated[Finite, Field(gt=0)]
Confidence = Annotated[Finite, Field(gt=0, lt=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class HistoryQuery(Contract):
    start: date
    end: date

    @model_validator(mode='after')
    def check_dates(self):
        if self.start >= self.end:
            raise ValueError('start must be earlier than end (exclusive)')
        if (self.end - self.start).days > 3660:
            raise ValueError('history range must not exceed 3660 days')
        return self


class SearchResult(Contract):
    symbol: str
    name: str
    exchange: str | None = None
    quote_type: Literal['EQUITY', 'ETF']


class SearchResponse(Contract):
    query: str
    results: list[SearchResult]
    source: str = 'Yahoo Finance via yfinance'
    fetched_at: datetime


class PriceBar(Contract):
    date: date
    open: Positive
    high: Positive
    low: Positive
    close: Positive
    volume: Annotated[int, Field(ge=0)] | None = None


class ReturnPoint(Contract):
    date: date
    value: Finite


class HistoryResponse(Contract):
    symbol: str
    start: date
    end: date
    source: str = 'Yahoo Finance via yfinance'
    fetched_at: datetime
    adjusted: bool = True
    prices: list[PriceBar]
    returns: list[ReturnPoint]
    annualized_volatility: Finite | None
    periods_per_year: int = 252


class RiskRequest(Contract):
    returns: Annotated[list[Annotated[Finite, Field(ge=-1, le=100)]], Field(min_length=2, max_length=10000)]
    risk_free_rate: Annotated[Finite, Field(gt=-1, le=10)] = 0.0
    periods_per_year: Annotated[int, Field(strict=True, ge=1, le=365)] = 252
    confidence: Confidence = .95


class RiskResponse(Contract):
    observations: int
    periods_per_year: int
    confidence: Confidence
    annualized_volatility: Finite
    sharpe_ratio: Finite | None
    sortino_ratio: Finite | None
    value_at_risk: Finite
    conditional_value_at_risk: Finite
    maximum_drawdown: Finite


class SimulationRequest(Contract):
    spot: Annotated[Positive, Field(le=1e9)]
    drift: Annotated[Finite, Field(ge=-5, le=5)]
    volatility: Annotated[Finite, Field(ge=0, le=5)]
    years: Annotated[Positive, Field(le=30)] = 1.0
    steps: Annotated[int, Field(strict=True, ge=1, le=2520)] = 252
    paths: Annotated[int, Field(strict=True, ge=1, le=100000)] = 1000
    seed: Annotated[int, Field(strict=True, ge=0, le=2**63-1)] = 42
    confidence: Confidence = .95
    sample_paths: Annotated[int, Field(strict=True, ge=0, le=20)] = 10

    @model_validator(mode='after')
    def allocation_limit(self):
        if (self.steps + 1) * self.paths > 5_000_000:
            raise ValueError('simulation must contain at most 5000000 path values')
        return self


class SimulationSummary(Contract):
    mean_terminal_price: Finite
    median_terminal_price: Finite
    lower_terminal_price: Finite
    upper_terminal_price: Finite
    loss_probability: Finite
    confidence: Confidence


class Histogram(Contract):
    bin_edges: list[Finite]
    counts: list[int]


class SimulationResponse(Contract):
    seed: int
    paths: int
    times: list[Finite]
    sample_paths: list[list[Finite]]
    lower_band: list[Finite]
    median_band: list[Finite]
    upper_band: list[Finite]
    summary: SimulationSummary
    terminal_distribution: Histogram


class OptionRequest(Contract):
    spot: Annotated[Positive, Field(ge=1e-8, le=1e9)]
    strike: Annotated[Positive, Field(ge=1e-8, le=1e9)]
    years: Annotated[Positive, Field(ge=1e-8, le=30)]
    rate: Annotated[Finite, Field(ge=-1, le=1)]
    volatility: Annotated[Positive, Field(ge=1e-8, le=5)]
    option_type: Literal['call', 'put'] = 'call'
    dividend_yield: Annotated[Finite, Field(ge=-1, le=1)] = 0.0


class OptionResponse(Contract):
    price: Finite
    delta: Finite
    gamma: Finite
    vega: Finite
    theta: Finite
    rho: Finite
