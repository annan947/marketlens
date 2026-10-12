"""Portfolio and backtest HTTP contracts; histories are explicitly supplied."""
from datetime import date
from typing import Annotated
from fastapi import APIRouter
from pydantic import Field, model_validator
from .schemas import Contract, Finite, Positive
from .routes import calculate
from backend.quant.portfolio import portfolio_metrics, optimize_portfolio
from backend.quant.backtest import backtest_sma

router = APIRouter(prefix='/api/v1', tags=['Portfolios and backtests'])
Weight = Annotated[Finite, Field(ge=0, le=1)]
Row = Annotated[list[Annotated[Finite, Field(ge=-1, le=100)]], Field(min_length=1, max_length=50)]


class PortfolioHistory(Contract):
    assets: Annotated[list[Annotated[str, Field(min_length=1, max_length=20)]], Field(min_length=1, max_length=50)]
    dates: Annotated[list[date], Field(min_length=2, max_length=10000)]
    returns: Annotated[list[Row], Field(min_length=2, max_length=10000)]
    periods_per_year: Annotated[int, Field(strict=True, ge=1, le=365)] = 252

    @model_validator(mode='after')
    def alignment(self):
        self.assets = [asset.strip().upper() for asset in self.assets]
        if any(not asset for asset in self.assets) or len(set(self.assets)) != len(self.assets):
            raise ValueError('asset names must be nonempty and unique')
        if len(self.dates) != len(self.returns) or any(a >= b for a, b in zip(self.dates, self.dates[1:])):
            raise ValueError('dates must be strictly increasing and align with return rows')
        if any(len(row) != len(self.assets) for row in self.returns):
            raise ValueError('each return row must match the assets in order')
        return self


class PortfolioRequest(PortfolioHistory):
    weights: Annotated[list[Weight], Field(min_length=1, max_length=50)]
    risk_free_rate: Annotated[Finite, Field(gt=-1, le=10)] = 0.


class PortfolioResponse(Contract):
    assets: list[str]
    dates: list[date]
    weights: list[Finite]
    returns: list[Finite]
    equity: list[Finite]
    expected_annual_return: Finite
    annualized_volatility: Finite
    sharpe_ratio: Finite | None
    maximum_drawdown: Finite
    total_return: Finite
    annualized_covariance: list[list[Finite]]


class OptimizationRequest(PortfolioHistory):
    max_weight: Annotated[Positive, Field(le=1)] = 1.
    target_return: Annotated[Finite, Field(ge=-365, le=36500)] | None = None


class OptimizationResponse(Contract):
    assets: list[str]
    weights: list[Finite]
    expected_annual_return: Finite
    annualized_volatility: Finite
    objective: str
    target_return: Finite | None
    max_weight: Finite
    iterations: int


class BacktestRequest(Contract):
    dates: Annotated[list[date], Field(min_length=3, max_length=10000)]
    prices: Annotated[list[Annotated[Positive, Field(ge=1e-8, le=1e9)]], Field(min_length=3, max_length=10000)]
    short_window: Annotated[int, Field(strict=True, ge=1, le=9999)] = 20
    long_window: Annotated[int, Field(strict=True, ge=2, le=9999)] = 50
    initial_capital: Annotated[Positive, Field(ge=1, le=1e12)] = 10000.
    transaction_cost_bps: Annotated[Finite, Field(ge=0, le=1000)] = 10.
    periods_per_year: Annotated[int, Field(strict=True, ge=1, le=365)] = 252
    risk_free_rate: Annotated[Finite, Field(gt=-1, le=10)] = 0.

    @model_validator(mode='after')
    def chronology(self):
        if len(self.dates) != len(self.prices) or any(a >= b for a,b in zip(self.dates, self.dates[1:])):
            raise ValueError('dates must be strictly increasing and align with prices')
        if not self.short_window < self.long_window < len(self.prices):
            raise ValueError('windows must satisfy short_window < long_window < number of prices')
        return self


class Trade(Contract):
    index: int
    side: str
    price: Finite
    quantity: Finite
    fee: Finite


class BacktestResponse(Contract):
    dates: list[date]
    equity: list[Finite]
    benchmark_equity: list[Finite]
    signals: list[int]
    positions: list[int]
    fees: list[Finite]
    trades: list[Trade]
    returns: list[Finite]
    total_return: Finite
    benchmark_total_return: Finite
    annualized_volatility: Finite
    sharpe_ratio: Finite | None
    maximum_drawdown: Finite
    total_fees: Finite


@router.post('/portfolios/analyze', response_model=PortfolioResponse)
def analyze(body: PortfolioRequest):
    result = calculate(portfolio_metrics, **body.model_dump(exclude={'assets', 'dates'}))
    return dict(assets=body.assets, dates=body.dates, **result)


@router.post('/portfolios/optimize', response_model=OptimizationResponse)
def optimize(body: OptimizationRequest):
    result = calculate(optimize_portfolio, **body.model_dump(exclude={'assets', 'dates'}))
    return dict(assets=body.assets, **result)


@router.post('/backtests/sma', response_model=BacktestResponse)
def backtest(body: BacktestRequest):
    return dict(dates=body.dates, **calculate(backtest_sma, **body.model_dump(exclude={'dates'})))
