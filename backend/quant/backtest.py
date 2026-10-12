"""Single-asset close-only simulation with next-close execution."""
import numpy as np
import pandas as pd
from ._validation import integer, scalar, vector
from .returns import annualized_volatility
from .risk import maximum_drawdown, sharpe_ratio


def moving_average_signals(prices, short_window=20, long_window=50):
    prices = vector(prices, 'prices', minimum=3, positive=True)
    short_window = integer(short_window, 'short_window')
    long_window = integer(long_window, 'long_window')
    if short_window >= long_window or long_window >= len(prices):
        raise ValueError('windows must satisfy short_window < long_window < number of prices')
    series = pd.Series(prices)
    short = series.rolling(short_window, min_periods=short_window).mean()
    long = series.rolling(long_window, min_periods=long_window).mean()
    return (short > long).astype(int).to_numpy()


def _execute(prices, signals, capital, cost):
    cash, shares = capital, 0.
    equity, positions, fees, trades = [], [], [], []
    for index, price in enumerate(prices):
        fee = 0.
        # Signal from yesterday is executed at today's close, after today's move.
        target = signals[index-1] if index else 0
        if target == 1 and shares == 0:
            quantity = cash / (price * (1+cost))
            fee = quantity * price * cost
            cash, shares = 0., quantity
            trades.append(dict(index=index, side='buy', price=float(price),
                               quantity=float(quantity), fee=float(fee)))
        elif target == 0 and shares > 0:
            fee = shares * price * cost
            cash = shares * price - fee
            trades.append(dict(index=index, side='sell', price=float(price),
                               quantity=float(shares), fee=float(fee)))
            shares = 0.
        equity.append(float(cash + shares * price))
        positions.append(int(shares > 0))
        fees.append(float(fee))
    return np.asarray(equity), positions, fees, trades


def backtest_sma(prices, short_window=20, long_window=50, initial_capital=10000.,
                 transaction_cost_bps=10., periods_per_year=252, risk_free_rate=0.):
    prices = vector(prices, 'prices', minimum=3, positive=True)
    if len(prices) > 10000:
        raise ValueError('at most 10000 prices are supported')
    capital = scalar(initial_capital, 'initial_capital', minimum=0, strict=True)
    cost = scalar(transaction_cost_bps, 'transaction_cost_bps', minimum=0) / 10000
    if cost >= 1:
        raise ValueError('transaction costs must be less than 10000 bps')
    periods = integer(periods_per_year, 'periods_per_year')
    signals = moving_average_signals(prices, short_window, long_window)
    equity, positions, fees, trades = _execute(prices, signals, capital, cost)
    # Benchmark uses the same one-close execution delay and cost model.
    benchmark, _, _, _ = _execute(prices, np.ones(len(prices), dtype=int), capital, cost)
    if not np.isfinite(equity).all() or not np.isfinite(benchmark).all() or np.any(equity <= 0):
        raise ValueError('backtest exceeds numerical range')
    returns = equity[1:] / equity[:-1] - 1
    return dict(equity=equity.tolist(), benchmark_equity=benchmark.tolist(),
        signals=signals.tolist(), positions=positions, fees=fees, trades=trades,
        returns=returns.tolist(), total_return=float(equity[-1]/capital-1),
        benchmark_total_return=float(benchmark[-1]/capital-1),
        annualized_volatility=annualized_volatility(returns, periods),
        sharpe_ratio=sharpe_ratio(returns, risk_free_rate, periods),
        maximum_drawdown=maximum_drawdown(returns), total_fees=float(sum(fees)))
