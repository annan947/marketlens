"""Provider-mocked integration tests: no Yahoo requests or wall-clock sleeps."""
from datetime import date
from unittest.mock import Mock, patch
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.quant.market_data import MarketDataService, YahooProvider
from yfinance.exceptions import YFRateLimitError, YFPricesMissingError


def frame():
    return pd.DataFrame({'Open': [100., 110., 99.], 'High': [101., 111., 100.],
                         'Low': [99., 109., 98.], 'Close': [100., 110., 99.],
                         'Volume': [10, 20, 30]},
        index=pd.date_range('2025-01-06', periods=3, tz='America/New_York'))


@pytest.fixture
def provider():
    provider = Mock()
    provider.history.return_value = frame()
    provider.search.return_value = [
        {'symbol': 'AAPL', 'longname': 'Apple Inc.', 'quoteType': 'EQUITY', 'exchange': 'NMS'},
        {'symbol': 'SPY', 'shortname': 'S&P ETF', 'quoteType': 'ETF'},
        {'symbol': 'BTC-USD', 'quoteType': 'CRYPTOCURRENCY'},
        {'symbol': 'AAPL', 'quoteType': 'EQUITY'}]
    return provider


@pytest.fixture
def client(provider):
    with TestClient(create_app(Settings(), provider)) as client:
        yield client


HISTORY = '/api/v1/stocks/aapl/history?start=2025-01-01&end=2025-02-01'


def test_search_filter_and_cache(client, provider):
    response = client.get('/api/v1/stocks/search', params={'q': ' Apple ', 'limit': 5})
    assert response.status_code == 200
    body = response.json()
    assert [item['symbol'] for item in body['results']] == ['AAPL', 'SPY']
    assert body['query'] == 'Apple'
    assert body['fetched_at'].endswith('Z')
    assert client.get('/api/v1/stocks/search?q=Apple&limit=5').json() == body
    provider.search.assert_called_once_with('Apple', 5)


def test_history_adjusted_returns_and_cache(client, provider):
    response = client.get(HISTORY)
    assert response.status_code == 200
    body = response.json()
    assert body['symbol'] == 'AAPL' and body['adjusted'] is True
    assert [item['value'] for item in body['returns']] == pytest.approx([.1, -.1])
    assert [item['date'] for item in body['returns']] == ['2025-01-07', '2025-01-08']
    assert body['annualized_volatility'] == pytest.approx(np.std([.1, -.1], ddof=1)*np.sqrt(252))
    assert client.get(HISTORY).json() == body
    provider.history.assert_called_once_with('AAPL', date(2025, 1, 1), date(2025, 2, 1))


@pytest.mark.parametrize('rows', [1, 2])
def test_short_histories(client, provider, rows):
    provider.history.return_value = frame().iloc[:rows]
    body = client.get(HISTORY).json()
    assert len(body['returns']) == rows - 1
    assert body['annualized_volatility'] is None


@pytest.mark.parametrize('url', [
    '/api/v1/stocks/search?q=%20%20', '/api/v1/stocks/search?q=x&limit=21',
    '/api/v1/stocks/search?q=x&limit=0', '/api/v1/stocks/search',
    '/api/v1/stocks/AAPL/history?start=2025-02-01&end=2025-01-01',
    '/api/v1/stocks/AAPL/history?start=2025-01-01&end=2025-01-01',
    '/api/v1/stocks/AAPL/history?start=2000-01-01&end=2025-01-01',
    '/api/v1/stocks/AAPL/history?start=invalid&end=2025-01-01',
    '/api/v1/stocks/AAPL/history?start=2025-01-01&end=2025-02-01&extra=1',
    '/api/v1/stocks/AAPL!/history?start=2025-01-01&end=2025-02-01'])
def test_market_validation_before_provider(client, provider, url):
    assert client.get(url).status_code == 422
    provider.search.assert_not_called()
    provider.history.assert_not_called()


@pytest.mark.parametrize('error,status,code', [
    (YFRateLimitError(), 503, 'provider_rate_limited'),
    (YFPricesMissingError('AAPL', ''), 404, 'no_market_data'),
    (TimeoutError('secret upstream URL'), 502, 'provider_unavailable')])
def test_provider_error_mapping_and_no_failure_cache(client, provider, error, status, code):
    provider.history.side_effect = error
    response = client.get(HISTORY)
    assert response.status_code == status
    assert response.json()['detail']['code'] == code
    assert 'secret' not in response.text
    if status == 503:
        assert response.headers['retry-after'] == '60'
    provider.history.side_effect = None
    assert client.get(HISTORY).status_code == 200
    assert provider.history.call_count == 2


def test_empty_history_and_empty_search(client, provider):
    provider.history.return_value = pd.DataFrame()
    assert client.get(HISTORY).status_code == 404
    provider.search.return_value = []
    assert client.get('/api/v1/stocks/search?q=unknown').json()['results'] == []


@pytest.mark.parametrize('fault', ['nan', 'zero', 'duplicate', 'missing_column', 'ohlc', 'volume'])
def test_malformed_history_is_not_silently_repaired(client, provider, fault):
    data = frame()
    if fault == 'nan': data.iloc[1, data.columns.get_loc('Close')] = np.nan
    if fault == 'zero': data.iloc[1, data.columns.get_loc('Close')] = 0
    if fault == 'duplicate': data = pd.concat([data, data.iloc[:1]])
    if fault == 'missing_column': data = data.drop(columns='Close')
    if fault == 'ohlc': data.iloc[1, data.columns.get_loc('High')] = 1
    if fault == 'volume': data.iloc[1, data.columns.get_loc('Volume')] = -1
    provider.history.return_value = data
    assert client.get(HISTORY).status_code == 502


def test_history_sorting_and_exclusive_end(client, provider):
    provider.history.return_value = frame().iloc[::-1]
    body = client.get('/api/v1/stocks/AAPL/history?start=2025-01-06&end=2025-01-08').json()
    assert [bar['date'] for bar in body['prices']] == ['2025-01-06', '2025-01-07']


def test_cache_expiry_eviction_and_copy_isolation(provider):
    clock = Mock(return_value=0.)
    service = MarketDataService(provider, ttl=10, max_entries=1, clock=clock)
    first = service.search('A', 2)
    first['results'].clear()
    assert len(service.search('A', 2)['results']) == 2
    assert provider.search.call_count == 1
    clock.return_value = 10.
    service.search('A', 2)
    assert provider.search.call_count == 2
    service.search('B', 2)
    service.search('A', 2)
    assert provider.search.call_count == 4


def test_cache_disabled(provider):
    service = MarketDataService(provider, ttl=0)
    service.search('A', 1)
    service.search('A', 1)
    assert provider.search.call_count == 2


def test_yahoo_adapter_contract():
    with patch('backend.quant.market_data.yf.Ticker') as ticker, patch('backend.quant.market_data.yf.Search') as search:
        adapter = YahooProvider(timeout=4)
        adapter.history('AAPL', date(2025, 1, 1), date(2025, 2, 1))
        ticker.return_value.history.assert_called_once_with(start='2025-01-01', end='2025-02-01',
            interval='1d', auto_adjust=True, actions=False, keepna=True, timeout=4, raise_errors=True)
        adapter.search('Apple', 5)
        assert search.call_args.kwargs['raise_errors'] is True
        assert search.call_args.kwargs['news_count'] == 0


def test_risk_response(client):
    response = client.post('/api/v1/analytics/risk', json={'returns': [-.1, .2], 'periods_per_year': 2})
    assert response.status_code == 200
    body = response.json()
    assert body['sortino_ratio'] == pytest.approx(1)
    assert body['maximum_drawdown'] == pytest.approx(.1)
    body = client.post('/api/v1/analytics/risk', json={'returns': [.1, .1]}).json()
    assert body['sharpe_ratio'] is None and body['sortino_ratio'] is None


def test_simulation_chart_contract_and_reproducibility(client):
    payload = dict(spot=100, drift=.05, volatility=.2, steps=10, paths=100, seed=7, sample_paths=3)
    response = client.post('/api/v1/simulations/gbm', json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body == client.post('/api/v1/simulations/gbm', json=payload).json()
    assert len(body['sample_paths']) == 3
    assert all(len(path) == 11 and path[0] == 100 for path in body['sample_paths'])
    assert len(body['times']) == len(body['median_band']) == 11
    assert np.all(np.array(body['lower_band']) <= body['median_band'])
    assert np.all(np.array(body['upper_band']) >= body['median_band'])
    histogram = body['terminal_distribution']
    assert sum(histogram['counts']) == 100
    assert len(histogram['bin_edges']) == len(histogram['counts']) + 1
    payload.update(volatility=0, sample_paths=0)
    body = client.post('/api/v1/simulations/gbm', json=payload).json()
    assert body['sample_paths'] == []
    assert body['summary']['loss_probability'] == 0


def test_option_endpoint(client):
    response = client.post('/api/v1/options/black-scholes',
        json=dict(spot=100, strike=100, years=1, rate=.05, volatility=.2))
    assert response.status_code == 200
    assert response.json()['price'] == pytest.approx(10.4505835722)


@pytest.mark.parametrize('path,payload', [
    ('analytics/risk', {'returns': [0]}),
    ('analytics/risk', {'returns': [0, -1.1]}),
    ('analytics/risk', {'returns': [0, 1], 'confidence': 1}),
    ('analytics/risk', {'returns': [0, 1], 'extra': True}),
    ('analytics/risk', {'returns': [True, .1]}),
    ('simulations/gbm', {'spot': 100, 'drift': .05, 'volatility': .2, 'paths': 100000}),
    ('simulations/gbm', {'spot': 100, 'drift': .05, 'volatility': .2, 'steps': True}),
    ('simulations/gbm', {'spot': 100, 'drift': .05, 'volatility': .2, 'seed': -1}),
    ('options/black-scholes', {'spot': 100, 'strike': 100, 'years': 0, 'rate': .05, 'volatility': .2}),
    ('options/black-scholes', {'spot': '100', 'strike': 100, 'years': 1, 'rate': .05, 'volatility': .2})])
def test_analytics_validation(client, path, payload):
    response = client.post('/api/v1/' + path, json=payload)
    assert response.status_code == 422
    assert 'detail' in response.json()


def test_nonfinite_json_errors_are_serializable(client):
    response = client.post('/api/v1/analytics/risk', content='{"returns": [NaN, 0.1]}',
                           headers={'Content-Type': 'application/json'})
    assert response.status_code == 422
    assert response.json()['detail']


def test_numerical_range_error(client):
    response = client.post('/api/v1/analytics/risk', json={'returns': [100.] * 1000})
    assert response.status_code == 422


def test_env_config_and_cors(monkeypatch, provider):
    monkeypatch.setenv('MARKETLENS_CACHE_TTL_SECONDS', '0')
    monkeypatch.setenv('MARKETLENS_CORS_ORIGINS', 'http://localhost:5173')
    settings = Settings.from_env()
    assert settings.cache_ttl_seconds == 0
    with TestClient(create_app(settings, provider)) as client:
        response = client.options('/api/v1/analytics/risk', headers={
            'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST'})
        assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
        response = client.options('/api/v1/analytics/risk', headers={
            'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'POST'})
        assert response.status_code == 400
    monkeypatch.setenv('MARKETLENS_CACHE_TTL_SECONDS', '-1')
    with pytest.raises(ValueError):
        Settings.from_env()


def test_openapi_contains_response_contracts(client):
    body = client.get('/openapi.json').json()
    assert '/api/v1/stocks/{symbol}/history' in body['paths']
    assert 'SimulationResponse' in body['components']['schemas']
