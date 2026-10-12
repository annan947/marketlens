"""Simulation-only quantitative analytics with no network or trading side effects."""
from .returns import daily_returns, annualized_volatility
from .risk import (sharpe_ratio, sortino_ratio, value_at_risk,
                   conditional_value_at_risk, maximum_drawdown)
from .simulation import simulate_gbm, summarize_simulation, SimulationSummary
from .options import black_scholes, OptionResult
from .portfolio import portfolio_metrics, optimize_portfolio
from .backtest import backtest_sma, moving_average_signals

__all__ = ['daily_returns', 'annualized_volatility', 'sharpe_ratio',
           'sortino_ratio', 'value_at_risk', 'conditional_value_at_risk',
           'maximum_drawdown', 'simulate_gbm', 'summarize_simulation',
           'SimulationSummary', 'black_scholes', 'OptionResult',
           'portfolio_metrics', 'optimize_portfolio', 'backtest_sma', 'moving_average_signals']
