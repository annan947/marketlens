import importlib.util
import sys
from unittest.mock import patch
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.quant.simulation import simulate_gbm

AVAILABLE = importlib.util.find_spec('backend.quant._gbm_native') is not None
native_only = pytest.mark.skipif(not AVAILABLE, reason='Optional native engine not built')


@native_only
@pytest.mark.parametrize('params', [dict(), dict(volatility=0), dict(drift=-.1, years=2),
    dict(steps=1, paths=1), dict(steps=25, paths=400, seed=19)])
def test_engine_parity_and_reproducibility(params):
    kwargs = dict(spot=100, drift=.07, volatility=.2, steps=12, paths=30, seed=42)
    kwargs.update(params)
    native = simulate_gbm(**kwargs, engine='cpp')
    np.testing.assert_allclose(native, simulate_gbm(**kwargs), rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(native, simulate_gbm(**kwargs, engine='cpp'))


@native_only
def test_direct_extension_validation_and_input_immutability():
    from backend.quant import _gbm_native
    shocks = np.zeros((3, 4), dtype=np.float64)
    _gbm_native.paths_from_shocks(100, .1, .2, 1, shocks)
    assert np.all(shocks == 0)
    for values in (np.array([1.]), np.empty((0, 3)), np.array([[np.nan]])):
        with pytest.raises(ValueError):
            _gbm_native.paths_from_shocks(100, .1, .2, 1, values)
    with pytest.raises(TypeError):
        _gbm_native.paths_from_shocks(100, .1, .2, 1, np.ones((2, 2), dtype=np.float32))
    with pytest.raises(ValueError):
        _gbm_native.paths_from_shocks(100, 1e308, .2, 100, shocks)


@native_only
def test_native_api_selection():
    with TestClient(create_app()) as client:
        response = client.post('/api/v1/simulations/gbm', json=dict(spot=100, drift=.05, volatility=.2, steps=5, paths=20, engine='cpp'))
        assert response.status_code == 200
        assert response.json()['engine'] == 'cpp'


def test_unavailable_engine_has_actionable_error():
    # Patch the import at its module boundary even when a binary is installed.
    import backend.quant as quant
    with patch.dict(sys.modules, {'backend.quant._gbm_native': None}):
        previous = quant.__dict__.pop('_gbm_native', None)
        try:
            with pytest.raises(ValueError, match='unavailable'):
                simulate_gbm(100, .1, .2, steps=1, paths=1, engine='cpp')
        finally:
            if previous is not None:
                quant._gbm_native = previous


def test_invalid_engine_is_rejected():
    with pytest.raises(ValueError, match='engine'):
        simulate_gbm(100, .1, .2, engine='unknown')
