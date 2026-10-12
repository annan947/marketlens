"""Offline numerical regression tests, runnable with pytest or unittest."""
import math
import unittest
import numpy as np
from numpy.testing import assert_allclose, assert_array_equal
from backend.quant import (
    daily_returns, annualized_volatility, sharpe_ratio, sortino_ratio,
    value_at_risk, conditional_value_at_risk, maximum_drawdown,
    simulate_gbm, summarize_simulation, black_scholes,
)


class ReturnsTests(unittest.TestCase):
    def test_simple_and_log_returns(self):
        assert_allclose(daily_returns([100, 110, 99]), [.1, -.1])
        self.assertAlmostEqual(sum(daily_returns([100, 110, 99], logarithmic=True)), math.log(.99))

    def test_sample_volatility(self):
        self.assertAlmostEqual(annualized_volatility([-.1, .1], 2), .2)

    def test_invalid_prices(self):
        for values in ([], [1], [1, 0], [1, -1], [1, np.nan], [[1, 2]], [1, np.inf]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                daily_returns(values)

    def test_invalid_volatility_inputs(self):
        for values, periods in (([1], 252), ([1, 2], 0), ([1, 2], True)):
            with self.assertRaises(ValueError):
                annualized_volatility(values, periods)


class RiskTests(unittest.TestCase):
    def test_sharpe(self):
        self.assertAlmostEqual(sharpe_ratio([0, .2], periods_per_year=2), 1)

    def test_effective_risk_free_rate(self):
        self.assertAlmostEqual(sharpe_ratio([0, .2], .21, 2), 0)

    def test_sortino_full_sample_denominator(self):
        self.assertAlmostEqual(sortino_ratio([-.1, .2], periods_per_year=2), 1)

    def test_undefined_ratios(self):
        self.assertIsNone(sharpe_ratio([.1, .1]))
        self.assertIsNone(sortino_ratio([.1, .2]))

    def test_tail_risk_fractional_mass(self):
        returns = [-.4, -.2, .1, .2]
        self.assertAlmostEqual(value_at_risk(returns, .625), .1625)
        self.assertAlmostEqual(conditional_value_at_risk(returns, .625), 1 / 3)
        self.assertAlmostEqual(conditional_value_at_risk(returns, .99), .4)

    def test_tied_losses_and_gain_only(self):
        self.assertAlmostEqual(conditional_value_at_risk([-.2, -.2, .1], .5), .2)
        self.assertLess(value_at_risk([.1, .2]), 0)

    def test_drawdown_includes_initial_capital(self):
        self.assertAlmostEqual(maximum_drawdown([-.2, .5, -.5]), .5)
        self.assertAlmostEqual(maximum_drawdown([-.2]), .2)
        self.assertEqual(maximum_drawdown([.1, .2]), 0)
        self.assertEqual(maximum_drawdown([-1, .2]), 1)

    def test_validation(self):
        for func in (sharpe_ratio, sortino_ratio, value_at_risk, conditional_value_at_risk, maximum_drawdown):
            with self.subTest(func=func.__name__), self.assertRaises(ValueError):
                func([-.1, -1.1])
        for confidence in (0, 1, np.nan):
            with self.assertRaises(ValueError):
                value_at_risk([-.1, .1], confidence)


class SimulationTests(unittest.TestCase):
    def test_reproducibility_shape_and_positive_prices(self):
        first = simulate_gbm(100, .05, .2, steps=10, paths=50, seed=7)
        assert_array_equal(first, simulate_gbm(100, .05, .2, steps=10, paths=50, seed=7))
        self.assertEqual(first.shape, (11, 50))
        self.assertTrue(np.all(first > 0))
        self.assertFalse(np.array_equal(first, simulate_gbm(100, .05, .2, steps=10, paths=50, seed=8)))

    def test_deterministic_zero_volatility(self):
        prices = simulate_gbm(100, .05, 0, steps=4, paths=3)
        assert_allclose(prices[:, 0], 100 * np.exp(.05 * np.linspace(0, 1, 5)))

    def test_terminal_moments(self):
        terminal = simulate_gbm(100, .07, .2, steps=1, paths=100000, seed=4)[-1]
        mean = 100 * math.exp(.07)
        variance = mean ** 2 * math.expm1(.2 ** 2)
        self.assertLess(abs(terminal.mean() - mean), 5 * math.sqrt(variance / len(terminal)))
        self.assertLess(abs(terminal.var() / variance - 1), .03)

    def test_summary_prediction_interval(self):
        summary = summarize_simulation([[100]*4, [80, 100, 120, 140]], .5)
        self.assertEqual(summary.loss_probability, .25)
        self.assertEqual(summary.mean_terminal_price, 110)
        self.assertEqual(summary.lower_terminal_price, 95)
        self.assertEqual(summary.upper_terminal_price, 125)

    def test_rng_does_not_change_global_state(self):
        np.random.seed(123)
        state = np.random.get_state()
        simulate_gbm(100, .05, .2, steps=2, paths=2)
        after = np.random.get_state()
        assert_array_equal(state[1], after[1])
        self.assertEqual(state[2:], after[2:])

    def test_invalid_parameters(self):
        for kwargs in ({'steps': 0}, {'paths': True}, {'seed': -1}, {'years': 0},
                       {'paths': 5000000}, {'drift': 1e308}, {'volatility': -1}):
            params = dict(spot=100, drift=.05, volatility=.2)
            params.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                simulate_gbm(**params)
        with self.assertRaises(ValueError):
            summarize_simulation([[100, 101], [110, 120]])


class OptionsTests(unittest.TestCase):
    def test_reference_prices(self):
        self.assertAlmostEqual(black_scholes(100, 100, 1, .05, .2).price, 10.4505835722, places=8)
        self.assertAlmostEqual(black_scholes(100, 100, 1, .05, .2, 'put').price, 5.5735260223, places=8)

    def test_dividend_put_call_parity(self):
        call = black_scholes(105, 100, 2, -.01, .3, dividend_yield=.02)
        put = black_scholes(105, 100, 2, -.01, .3, 'put', .02)
        self.assertAlmostEqual(call.price - put.price, 105 * math.exp(-.04) - 100 * math.exp(.02))

    def test_greeks_against_finite_differences(self):
        for kind in ('call', 'put'):
            args = [105., 100., 1.3, .04, .25, kind, .02]
            base = black_scholes(*args)
            for index, greek, sign in ((0, 'delta', 1), (2, 'theta', -1), (3, 'rho', 1), (4, 'vega', 1)):
                h = 1e-4
                up, down = args.copy(), args.copy()
                up[index] += h
                down[index] -= h
                derivative = sign * (black_scholes(*up).price - black_scholes(*down).price) / (2*h)
                self.assertAlmostEqual(getattr(base, greek), derivative, places=5)
            up, down = args.copy(), args.copy()
            up[0] += .01
            down[0] -= .01
            gamma = (black_scholes(*up).price - 2 * base.price + black_scholes(*down).price) / .01**2
            self.assertAlmostEqual(base.gamma, gamma, places=6)

    def test_invalid_parameters(self):
        for index, value in ((0, 0), (1, -1), (2, 0), (3, np.inf), (4, 0), (5, 'invalid')):
            args = [100, 100, 1, .05, .2, 'call']
            args[index] = value
            with self.subTest(index=index), self.assertRaises(ValueError):
                black_scholes(*args)
