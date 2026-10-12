"""European Black-Scholes-Merton prices with continuous dividend yield."""
from dataclasses import dataclass
import math
from scipy.stats import norm
from ._validation import scalar


@dataclass(frozen=True)
class OptionResult:
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


def black_scholes(spot, strike, years, rate, volatility, option_type='call', dividend_yield=0.0):
    spot = scalar(spot, 'spot', minimum=0, strict=True)
    strike = scalar(strike, 'strike', minimum=0, strict=True)
    years = scalar(years, 'years', minimum=0, strict=True)
    rate = scalar(rate, 'rate')
    volatility = scalar(volatility, 'volatility', minimum=0, strict=True)
    dividend_yield = scalar(dividend_yield, 'dividend_yield')
    if option_type not in ('call', 'put'):
        raise ValueError("option_type must be 'call' or 'put'")
    sign = 1 if option_type == 'call' else -1
    try:
        root = math.sqrt(years)
        discount = math.exp(-rate * years)
        dividend = math.exp(-dividend_yield * years)
        d1 = (math.log(spot) - math.log(strike) +
              (rate - dividend_yield + volatility ** 2 / 2) * years) / (volatility * root)
        d2 = d1 - volatility * root
        n1, n2 = norm.cdf(sign * d1), norm.cdf(sign * d2)
        density = norm.pdf(d1)
        result = OptionResult(
            float(sign * (spot * dividend * n1 - strike * discount * n2)),
            float(sign * dividend * n1),
            float(dividend * density / (spot * volatility * root)),
            float(spot * dividend * density * root),
            float(-spot * dividend * density * volatility / (2 * root)
                  - sign * rate * strike * discount * n2
                  + sign * dividend_yield * spot * dividend * n1),
            float(sign * strike * years * discount * n2),
        )
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError('option parameters exceed numerical range') from exc
    if not all(math.isfinite(value) for value in vars(result).values()):
        raise ValueError('option parameters exceed numerical range')
    return result
