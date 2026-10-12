"""Exact-discretization geometric Brownian motion simulation."""
from dataclasses import dataclass
import numpy as np
from ._validation import confidence_level, integer, scalar

MAX_PATH_VALUES = 5_000_000


@dataclass(frozen=True)
class SimulationSummary:
    mean_terminal_price: float
    median_terminal_price: float
    lower_terminal_price: float
    upper_terminal_price: float
    loss_probability: float
    confidence: float


def simulate_gbm(spot, drift, volatility, years=1.0, steps=252, paths=1000, seed=42, engine='numpy'):
    spot = scalar(spot, 'spot', minimum=0, strict=True)
    drift = scalar(drift, 'drift')
    volatility = scalar(volatility, 'volatility', minimum=0)
    years = scalar(years, 'years', minimum=0, strict=True)
    steps = integer(steps, 'steps')
    paths = integer(paths, 'paths')
    seed = integer(seed, 'seed', minimum=0)
    if engine not in ('numpy', 'cpp'):
        raise ValueError("engine must be 'numpy' or 'cpp'")
    if (steps + 1) * paths > MAX_PATH_VALUES:
        raise ValueError(f'simulation must contain at most {MAX_PATH_VALUES} path values')
    rng = np.random.default_rng(seed)
    if engine == 'cpp':
        try:
            from . import _gbm_native
        except ImportError as exc:
            raise ValueError('C++ engine is unavailable; build native/build.py or select numpy') from exc
        return _gbm_native.paths_from_shocks(spot, drift, volatility, years,
                                             rng.normal(size=(steps, paths)))
    dt = years / steps
    try:
        with np.errstate(over='raise', invalid='raise', under='ignore'):
            increments = rng.normal(size=(steps, paths))
            increments *= volatility * np.sqrt(dt)
            increments += (drift - 0.5 * volatility ** 2) * dt
            result = np.empty((steps + 1, paths))
            result[0] = spot
            result[1:] = np.exp(np.log(spot) + np.cumsum(increments, axis=0))
    except (FloatingPointError, OverflowError) as exc:
        raise ValueError('simulation parameters exceed numerical range') from exc
    if not np.isfinite(result).all() or np.any(result <= 0):
        raise ValueError('simulation parameters exceed numerical range')
    return result


def summarize_simulation(prices, confidence=0.95):
    prices = np.asarray(prices, dtype=float)
    confidence = confidence_level(confidence)
    if prices.ndim != 2 or prices.shape[0] < 2 or prices.shape[1] < 1:
        raise ValueError('prices must be a (steps + 1, paths) matrix')
    if not np.isfinite(prices).all() or np.any(prices <= 0):
        raise ValueError('prices must be finite and positive')
    if not np.all(prices[0] == prices[0, 0]):
        raise ValueError('all paths must have the same initial price')
    terminal = prices[-1]
    tail = (1 - confidence) / 2
    lower, upper = np.quantile(terminal, [tail, 1 - tail])
    return SimulationSummary(float(np.mean(terminal)), float(np.median(terminal)),
                             float(lower), float(upper),
                             float(np.mean(terminal < prices[0, 0])), confidence)
