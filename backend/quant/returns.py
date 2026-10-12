"""Returns and sample volatility for chronologically ordered observations."""
import numpy as np
from ._validation import integer, vector


def daily_returns(prices, *, logarithmic=False):
    prices = vector(prices, 'prices', minimum=2, positive=True)
    if logarithmic:
        return np.diff(np.log(prices))
    return prices[1:] / prices[:-1] - 1


def annualized_volatility(returns, periods_per_year=252):
    returns = vector(returns, 'returns', minimum=2)
    periods_per_year = integer(periods_per_year, 'periods_per_year')
    return float(np.std(returns, ddof=1) * np.sqrt(periods_per_year))
