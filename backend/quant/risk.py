"""Historical risk statistics. Returns are decimal simple returns."""
import numpy as np
from ._validation import confidence_level, integer, scalar, vector


def _returns(values, minimum=1):
    values = vector(values, 'returns', minimum=minimum)
    if np.any(values < -1):
        raise ValueError('simple returns cannot be below -1')
    return values


def _excess(returns, risk_free_rate, periods_per_year):
    values = _returns(returns, minimum=2)
    periods = integer(periods_per_year, 'periods_per_year')
    rate = scalar(risk_free_rate, 'risk_free_rate', minimum=-1, strict=True)
    return values - np.expm1(np.log1p(rate) / periods), periods


def sharpe_ratio(returns, risk_free_rate=0.0, periods_per_year=252):
    excess, periods = _excess(returns, risk_free_rate, periods_per_year)
    denominator = np.std(excess, ddof=1)
    if denominator <= np.finfo(float).eps:
        return None
    return float(np.mean(excess) / denominator * np.sqrt(periods))


def sortino_ratio(returns, risk_free_rate=0.0, periods_per_year=252):
    excess, periods = _excess(returns, risk_free_rate, periods_per_year)
    denominator = np.sqrt(np.mean(np.minimum(excess, 0) ** 2))
    if denominator <= np.finfo(float).eps:
        return None
    return float(np.mean(excess) / denominator * np.sqrt(periods))


def value_at_risk(returns, confidence=0.95):
    losses = -_returns(returns)
    return float(np.quantile(losses, confidence_level(confidence)))


def conditional_value_at_risk(returns, confidence=0.95):
    """Mean of the worst (1-confidence) empirical mass, with fractional boundary weight."""
    losses = np.sort(-_returns(returns))[::-1]
    mass = len(losses) * (1 - confidence_level(confidence))
    count = int(np.floor(mass))
    total = np.sum(losses[:count])
    if count < len(losses):
        total += (mass - count) * losses[count]
    return float(total / mass)


def maximum_drawdown(returns):
    values = _returns(returns)
    with np.errstate(over='raise', invalid='raise'):
        try:
            wealth = np.concatenate(([1.0], np.cumprod(1 + values)))
        except FloatingPointError as exc:
            raise ValueError('return history exceeds numerical range') from exc
    peaks = np.maximum.accumulate(wealth)
    return float(np.max(1 - wealth / peaks))
