"""Build with the active Python and an existing GCC/Clang-compatible compiler."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import pybind11

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiler', default=os.getenv('CXX', 'g++'))
    args = parser.parse_args()
    compiler = shutil.which(args.compiler)
    if not compiler:
        parser.error('Compiler not found. Pass --compiler with an existing GCC/Clang executable.')
    output = ROOT / 'backend' / 'quant' / ('_gbm_native' + sysconfig.get_config_var('EXT_SUFFIX'))
    command = [compiler, '-O3', '-std=c++17', '-shared', '-Wall', '-Wextra',
               '-ffp-contract=off', '-I'+pybind11.get_include(),
               '-I'+sysconfig.get_path('include'), str(ROOT / 'native' / 'gbm.cpp'), '-o', str(output)]
    if sys.platform == 'win32':
        dll = Path(sys.base_prefix) / f'python{sys.version_info.major}{sys.version_info.minor}.dll'
        if not dll.exists():
            parser.error('The active CPython DLL was not found')
        command += [str(dll), '-static', '-static-libgcc', '-static-libstdc++']
    elif sys.platform == 'darwin':
        command += ['-fPIC', '-undefined', 'dynamic_lookup']
    else:
        command += ['-fPIC']
    subprocess.run(command, check=True, cwd=ROOT)
    subprocess.run([sys.executable, '-c', 'from backend.quant import _gbm_native; print("Native import verified")'], check=True, cwd=ROOT)
    metadata = {'compiler': subprocess.check_output([compiler, '--version'], text=True).splitlines()[0],
                'python': platform.python_version(), 'platform': platform.platform(),
                'pybind11': pybind11.__version__, 'flags': ['-O3', '-std=c++17', '-ffp-contract=off'],
                'source': 'native/gbm.cpp'}
    directory = ROOT / 'work' / 'native'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'build.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print('Built optional engine:', output)


if __name__ == '__main__':
    main()
