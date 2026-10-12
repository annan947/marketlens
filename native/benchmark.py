"""Compare full Python engine calls, including RNG, allocation and validation."""
import argparse
import json
import platform
from pathlib import Path
import statistics
import sys
from time import perf_counter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.quant.simulation import simulate_gbm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=7)
    parser.add_argument('--output', type=Path, default=ROOT/'work/native/benchmark.json')
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error('Use at least three repetitions')
    report = {'python': platform.python_version(), 'numpy': np.__version__,
              'platform': platform.platform(), 'processor': platform.processor(),
              'seed': 42, 'repeats': args.repeats, 'timing_scope': 'RNG + validation + path allocation/computation; no HTTP, quantiles or JSON', 'cases': []}
    build = ROOT/'work/native/build.json'
    if build.exists():
        report['build'] = json.loads(build.read_text())
    for steps, paths in ((252, 1000), (252, 10000), (1000, 4000)):
        kwargs = dict(spot=100, drift=.07, volatility=.2, steps=steps, paths=paths, seed=42)
        reference = simulate_gbm(**kwargs)
        candidate = simulate_gbm(**kwargs, engine='cpp')
        np.testing.assert_allclose(reference, candidate, rtol=1e-12, atol=1e-12)
        del reference, candidate
        times = {'numpy': [], 'cpp': []}
        for iteration in range(args.repeats):
            for engine in (('numpy', 'cpp') if iteration % 2 == 0 else ('cpp', 'numpy')):
                start = perf_counter()
                result = simulate_gbm(**kwargs, engine=engine)
                times[engine].append(perf_counter()-start)
                del result
        medians = {engine: statistics.median(values) for engine, values in times.items()}
        report['cases'].append({'steps': steps, 'paths': paths, 'seconds': times,
            'median_seconds': medians, 'numpy_time_divided_by_cpp_time': medians['numpy']/medians['cpp']})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
