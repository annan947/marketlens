"""Shared validation for numerical entry points."""
import numpy as np


def scalar(value, name, *, minimum=None, strict=False):
    if isinstance(value, (bool, str)) or not np.isscalar(value):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and (value < minimum or (strict and value == minimum)):
        raise ValueError(f"{name} must be {'greater than' if strict else 'at least'} {minimum}")
    return value


def integer(value, name, minimum=1):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def vector(values, name, minimum=1, positive=False):
    try:
        data = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a numeric vector") from exc
    if data.ndim != 1 or data.size < minimum or not np.isfinite(data).all():
        raise ValueError(f"{name} must contain at least {minimum} finite values in one dimension")
    if positive and np.any(data <= 0):
        raise ValueError(f"{name} must be strictly positive")
    return data


def confidence_level(value):
    value = scalar(value, 'confidence', minimum=0, strict=True)
    if value >= 1:
        raise ValueError('confidence must be between 0 and 1 exclusively')
    return value
