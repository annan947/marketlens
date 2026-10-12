# Optional C++ Monte Carlo engine

The C++17/pybind11 extension evaluates exact-discretization GBM paths. NumPy still
generates seeded normal shocks, so both engines consume identical randomness.
NumPy remains the default and the application does not require a compiler to run.

## Build on the development machine

```powershell
Set-Location D:\marketlens
$env:TEMP = 'D:\marketlens\work\temp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'D:\marketlens\downloads\pip-cache'
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-native.txt
.\backend\.venv\Scripts\python.exe native/build.py
```

The script reuses an existing GCC/Clang-compatible compiler (`CXX` or `--compiler`).
It installs no system toolchain. On Windows it links to the active Python DLL and
statically links the GCC/C++/thread runtimes; on Linux/macOS it uses their native
extension-linking conventions. Only the Windows/MSYS2 UCRT64 build has been verified.
MSVC is not accepted by this helper; adding a portable wheel/CMake pipeline remains
future work. The result is placed beside the Python quant modules and ignored by Git.
Rebuild for every Python ABI/platform change. Do not copy this `.pyd` to a Linux host.

Select **C++** in the Monte Carlo dashboard or send `"engine":"cpp"` to
`POST /api/v1/simulations/gbm`. The response records the engine used. If the binary
cannot load, the API returns an actionable 422; it does not silently relabel a
NumPy result as C++. Docker/Render images currently use NumPy unless a compatible
native extension is explicitly built into them.

## Numerical behavior and safety

The native binding validates dimensions, finite values and the five-million-value
allocation limit. It takes a snapshot of the input shocks before releasing the
Python GIL, so mutation from another thread cannot affect the calculation. Input
arrays are never modified. It rejects overflow/underflow that produces nonpositive
or nonfinite prices. Compiler fast-math is disabled and contraction is disabled.
Parity is checked with relative/absolute tolerances of `1e-12`; library math may
prevent bitwise equality across platforms. Repeat runs of a given engine are
deterministic under the same dependencies. RNG remains Python/NumPy work; the
native kernel itself is single-threaded.

## Benchmark

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_native.py -q
.\backend\.venv\Scripts\python.exe native/benchmark.py --repeats 7
```

The benchmark verifies parity, warms both engines once, alternates execution order
and measures seven complete `simulate_gbm` calls per engine/case with seed 42. It
includes RNG, validation, allocations and the input snapshot. It excludes imports,
HTTP, quantiles, histogram construction, JSON and chart rendering. Raw individual
measurements and environment metadata are in [benchmark-results.json](benchmark-results.json).

Measured locally on 2026-10-12 using Windows 11, CPython 3.14.7, NumPy 2.5.4,
pybind11 3.1.0 and MSYS2 GCC 15.2.0 (`-O3`, C++17, no FP contraction):

| Steps × paths | NumPy median | C++ median | NumPy time / C++ time |
| --- | ---: | ---: | ---: |
| 252 × 1,000 | 5.842 ms | 4.535 ms | 1.29× |
| 252 × 10,000 | 65.013 ms | 45.732 ms | 1.42× |
| 1,000 × 4,000 | 106.166 ms | 74.337 ms | 1.43× |

These are one-machine observations, not an API-wide performance guarantee. CPU
load, compilers, libraries and deployment hardware can change the comparison. No
memory benchmark or confidence interval over independent machine runs is claimed.
