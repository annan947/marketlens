"""Long-only, fully invested portfolio estimates and constrained optimization."""
import numpy as np
from scipy.optimize import minimize
from ._validation import integer, scalar, vector
from .returns import annualized_volatility
from .risk import maximum_drawdown, sharpe_ratio


def return_matrix(values):
    try:
        data = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError('returns must be a rectangular numeric matrix') from exc
    if data.ndim != 2 or data.shape[0] < 2 or not 1 <= data.shape[1] <= 50:
        raise ValueError('returns must have at least two observations and 1 to 50 assets')
    if data.shape[0] > 10000 or not np.isfinite(data).all() or np.any(data < -1):
        raise ValueError('returns must be finite, >= -1, and have at most 10000 observations')
    return data


def portfolio_metrics(returns, weights, periods_per_year=252, risk_free_rate=0.):
    data = return_matrix(returns)
    weights = vector(weights, 'weights')
    if len(weights) != data.shape[1] or np.any(weights < 0) or not np.isclose(weights.sum(), 1, atol=1e-8, rtol=0):
        raise ValueError('weights must match the assets, be nonnegative and sum to one')
    periods = integer(periods_per_year, 'periods_per_year')
    series = data @ weights
    covariance = np.atleast_2d(np.cov(data, rowvar=False, ddof=1)) * periods
    with np.errstate(over='raise', invalid='raise'):
        try:
            equity = np.concatenate(([1.], np.cumprod(1 + series)))
        except FloatingPointError as exc:
            raise ValueError('portfolio history exceeds numerical range') from exc
    return dict(weights=weights.tolist(), returns=series.tolist(), equity=equity.tolist(),
        expected_annual_return=float(series.mean() * periods),
        annualized_volatility=annualized_volatility(series, periods),
        sharpe_ratio=sharpe_ratio(series, risk_free_rate, periods),
        maximum_drawdown=maximum_drawdown(series), total_return=float(equity[-1]-1),
        annualized_covariance=covariance.tolist())


def optimize_portfolio(returns, periods_per_year=252, max_weight=1., target_return=None):
    data = return_matrix(returns)
    periods = integer(periods_per_year, 'periods_per_year')
    cap = scalar(max_weight, 'max_weight', minimum=0, strict=True)
    n = data.shape[1]
    if cap > 1 or n * cap < 1 - 1e-10:
        raise ValueError('max_weight must be <= 1 and permit weights summing to one')
    means = data.mean(axis=0) * periods
    covariance = np.atleast_2d(np.cov(data, rowvar=False, ddof=1)) * periods
    constraints = [{'type': 'eq', 'fun': lambda w: w.sum()-1,
                    'jac': lambda w: np.ones(n)}]
    if target_return is not None:
        target_return = scalar(target_return, 'target_return')
        remaining, highest = 1., 0.
        for mean in sorted(means, reverse=True):
            allocation = min(cap, remaining)
            highest += allocation * mean
            remaining -= allocation
        if target_return > highest + 1e-9:
            raise ValueError('target_return is infeasible under the weight cap')
        constraints.append({'type': 'ineq', 'fun': lambda w: w @ means-target_return,
                            'jac': lambda w: means})
    # Scale the objective so low-variance daily data does not trigger early convergence.
    scale = max(float(np.max(np.abs(covariance))), 1e-12)
    result = minimize(lambda w: float(w @ covariance @ w / scale), np.full(n, 1/n),
        jac=lambda w: 2 * covariance @ w / scale, method='SLSQP',
        bounds=[(0., cap)]*n, constraints=constraints,
        options={'ftol': 1e-12, 'maxiter': 1000})
    weights = result.x
    if (not result.success or not np.isfinite(weights).all()
            or abs(weights.sum()-1) > 1e-7 or np.any(weights < -1e-8)
            or np.any(weights > cap+1e-8)
            or (target_return is not None and weights @ means < target_return-1e-7)):
        raise ValueError('optimizer could not find a verified feasible solution')
    weights = np.clip(weights, 0, cap)
    weights /= weights.sum()
    return dict(weights=weights.tolist(), expected_annual_return=float(weights @ means),
        annualized_volatility=float(np.sqrt(max(0., weights @ covariance @ weights))),
        objective='minimum_variance', target_return=target_return,
        max_weight=cap, iterations=int(result.nit))
