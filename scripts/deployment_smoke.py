"""Exercise a running deployment without Yahoo access; delete only our own test row."""
import argparse
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def request(base, path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(base+path, data=data, method=method, headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as exc:
        return exc.code, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    args = parser.parse_args()
    base = args.url.rstrip('/')
    deadline = time.monotonic()+90
    while True:
        try:
            if request(base, '/ready')[0] == 200:
                break
        except (URLError, TimeoutError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError('Deployment readiness did not succeed within 90 seconds')
        time.sleep(1)
    with urlopen(base+'/', timeout=10) as response:
        assert response.status == 200 and b'id="root"' in response.read(), 'Frontend not served'
    status, option = request(base, '/api/v1/options/black-scholes',
        dict(spot=100, strike=100, years=1, rate=.05, volatility=.2))
    assert status == 200 and abs(option['price']-10.4505835722) < 1e-8
    status, simulation = request(base, '/api/v1/simulations/gbm',
        dict(spot=100, drift=.05, volatility=.2, steps=5, paths=20, seed=42))
    assert status == 200 and sum(simulation['terminal_distribution']['counts']) == 20
    body = dict(name='Deployment smoke '+str(uuid4()), definition=dict(
        assets=['TEST'], dates=['2025-01-02','2025-01-03'], returns=[[.01],[-.01]], weights=[1]))
    status, created = request(base, '/api/v1/saved-portfolios', body)
    assert status == 201, 'Portfolio creation failed'
    path = '/api/v1/saved-portfolios/'+created['id']
    try:
        status, loaded = request(base, path)
        assert status == 200 and loaded['definition']['weights'] == [1]
        status, updated = request(base, path, {**body, 'version': created['version'], 'notes': 'Updated by smoke test'}, 'PUT')
        assert status == 200 and updated['version'] == created['version']+1
        assert request(base, path, {**body, 'version': created['version']}, 'PUT')[0] == 409
    finally:
        status, current = request(base, path)
        if status == 200:
            assert request(base, path+f"?version={current['version']}", method='DELETE')[0] == 204
    assert request(base, path)[0] == 404
    print('Deployment smoke passed: frontend, readiness, options, simulation, portfolio CRUD and stale-write rejection.')


if __name__ == '__main__':
    main()
