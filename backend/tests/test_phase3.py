from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.quant.portfolio import portfolio_metrics, optimize_portfolio
from backend.quant.backtest import backtest_sma


def test_portfolio_weighted_returns_and_covariance():
    result = portfolio_metrics([[.1, 0], [-.1, .2]], [.5, .5], 2)
    assert result['returns'] == pytest.approx([.05, .05])
    assert result['equity'] == pytest.approx([1, 1.05, 1.1025])
    assert result['expected_annual_return'] == pytest.approx(.1)
    assert result['total_return'] == pytest.approx(.1025)
    np.testing.assert_allclose(result['annualized_covariance'], [[.04, -.04], [-.04, .04]])


@pytest.mark.parametrize('returns,weights', [([[0, 1]], [.5, .5]),
    ([[0, 1], [0]], [.5, .5]), ([[0], [-1.1]], [1]),
    ([[0], [np.nan]], [1]), ([[0], [.1]], [.8]),
    ([[0, .1], [.1, 0]], [-.1, 1.1]), ([[0], [.1]], [1, 0])])
def test_portfolio_invalid(returns, weights):
    with pytest.raises(ValueError):
        portfolio_metrics(returns, weights)


def independent_returns():
    # Orthogonal centered series; asset 2 variance is four times asset 1.
    return np.array([[-.01, -.02], [-.01, .02], [.01, -.02], [.01, .02]])


def test_optimizer_analytic_inverse_variance():
    result = optimize_portfolio(independent_returns())
    assert result['weights'] == pytest.approx([.8, .2], abs=1e-7)


def test_optimizer_cap_and_target():
    data = independent_returns() + [.001, .002]
    capped = optimize_portfolio(data, max_weight=.6)
    assert capped['weights'] == pytest.approx([.6, .4], abs=1e-7)
    target = optimize_portfolio(data, target_return=.4284)
    assert target['weights'] == pytest.approx([.3, .7], abs=1e-6)


@pytest.mark.parametrize('data,cap', [(independent_returns(), .5),
    (np.array([[.01], [.02], [.03]]), 1.), (np.zeros((4, 2)), 1.)])
def test_degenerate_and_fixed_allocations(data, cap):
    result = optimize_portfolio(data, max_weight=cap)
    assert sum(result['weights']) == pytest.approx(1)
    assert max(result['weights']) <= cap + 1e-8


@pytest.mark.parametrize('kwargs', [{'max_weight': .4}, {'target_return': 100}, {'max_weight': 2}])
def test_infeasible_optimization(kwargs):
    with pytest.raises(ValueError):
        optimize_portfolio(independent_returns(), **kwargs)


def test_failed_solver_is_not_reported_as_success():
    with patch('backend.quant.portfolio.minimize', return_value=SimpleNamespace(success=False, x=np.array([.5,.5]))):
        with pytest.raises(ValueError, match='verified feasible'):
            optimize_portfolio(independent_returns())


def test_next_close_execution_and_no_same_bar_gain():
    result = backtest_sma([100, 100, 200, 400, 800], 1, 2, 1000, 0)
    assert result['signals'] == [0, 0, 1, 1, 1]
    assert result['positions'] == [0, 0, 0, 1, 1]
    assert result['equity'] == pytest.approx([1000, 1000, 1000, 1000, 2000])
    assert result['trades'][0]['index'] == 3


def test_exact_cash_ledger_and_fees():
    result = backtest_sma([100, 110, 120, 90, 80], 1, 2, 1000, 100)
    shares = 1000 / (120 * 1.01)
    assert [trade['side'] for trade in result['trades']] == ['buy', 'sell']
    assert [trade['index'] for trade in result['trades']] == [2, 4]
    assert result['equity'][-1] == pytest.approx(shares * 80 * .99)
    assert result['total_fees'] == pytest.approx(shares * (120+80) * .01)
    assert result['fees'][2] == pytest.approx(shares*120*.01)


def test_future_changes_cannot_change_past():
    prices = [100, 110, 120, 90, 80, 100, 120, 130]
    changed = prices[:5] + [1000, 10, 500]
    a, b = [backtest_sma(p, 1, 2) for p in (prices, changed)]
    for key in ('signals', 'positions', 'equity', 'fees'):
        assert a[key][:5] == b[key][:5]
    prefix = backtest_sma(prices[:5], 1, 2)
    assert a['equity'][:5] == prefix['equity']


def test_flat_prices_stay_cash_and_pending_signal_not_filled():
    result = backtest_sma([100]*5, 1, 2)
    assert result['trades'] == [] and result['total_return'] == 0
    assert result['sharpe_ratio'] is None
    result = backtest_sma([100, 100, 100, 200], 1, 2)
    assert result['signals'][-1] == 1 and result['trades'] == []


@pytest.mark.parametrize('kwargs', [{'short_window': 2, 'long_window': 2},
    {'short_window': 1, 'long_window': 10}, {'transaction_cost_bps': -1},
    {'transaction_cost_bps': 10000}, {'initial_capital': 0}])
def test_invalid_backtest(kwargs):
    params = dict(short_window=1, long_window=2)
    params.update(kwargs)
    with pytest.raises(ValueError):
        backtest_sma([100]*5, **params)


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


def history():
    return dict(assets=['a', 'b'], dates=['2025-01-01','2025-01-02','2025-01-03','2025-01-04'],
                returns=independent_returns().tolist())


def test_portfolio_api(client):
    response = client.post('/api/v1/portfolios/analyze', json=dict(**history(), weights=[.5,.5]))
    assert response.status_code == 200
    assert response.json()['assets'] == ['A', 'B']
    assert len(response.json()['equity']) == 5
    response = client.post('/api/v1/portfolios/optimize', json=history())
    assert response.status_code == 200
    assert response.json()['weights'] == pytest.approx([.8, .2])


@pytest.mark.parametrize('changes', [{'assets':['a','A']}, {'dates':['2025-01-01']*4},
    {'returns':[[.1],[.2]]}, {'max_weight':.4}, {'target_return':100},
    {'periods_per_year':True}, {'unknown':1}])
def test_optimizer_api_validation(client, changes):
    payload = history()
    payload.update(changes)
    assert client.post('/api/v1/portfolios/optimize', json=payload).status_code == 422


def test_backtest_api(client):
    payload = dict(dates=history()['dates'], prices=[100,110,120,130], short_window=1, long_window=2)
    response = client.post('/api/v1/backtests/sma', json=payload)
    assert response.status_code == 200
    assert response.json()['trades'][0]['index'] == 2
    payload['dates'] = payload['dates'][::-1]
    assert client.post('/api/v1/backtests/sma', json=payload).status_code == 422


def test_new_openapi_contracts(client):
    schema = client.get('/openapi.json').json()
    assert '/api/v1/backtests/sma' in schema['paths']
    assert 'OptimizationResponse' in schema['components']['schemas']
