"""Isolated same-SHA build runner. Does not manage application services."""
import datetime
import hashlib
import importlib.metadata as md
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
EXPECTED = '5cb102190d135e7019f8ced291d853121b060de5995f0943da58611ee0898201'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    model = HERE / 'artifacts/yolov8n_2class_640_UNTRAINED_raw6_rknn_preflight.onnx'
    out = model.with_suffix('.rknn')
    preflight = json.loads((HERE / 'reports/deployment_preflight.json').read_text())
    assert sha(model) == EXPECTED == preflight['onnx_sha256']
    versions = {}
    for name in ['rknn-toolkit2', 'rknn-toolkit-lite2', 'onnx', 'onnxruntime', 'numpy', 'torch']:
        try:
            versions[name] = md.version(name)
        except md.PackageNotFoundError:
            versions[name] = None
    environment = {
        'time': datetime.datetime.now().astimezone().isoformat(),
        'python': sys.version, 'executable': sys.executable,
        'platform': platform.platform(), 'packages': versions,
        'system_runtime_sha256': sha('/usr/lib/librknnrt.so'),
        'driver_modinfo': subprocess.run(['modinfo', 'rknpu'], capture_output=True, text=True).stdout,
        'processes_before': subprocess.run(['ps', '-eo', 'pid,args'], capture_output=True, text=True).stdout,
        'listeners_before': subprocess.run(['ss', '-lntup'], capture_output=True, text=True).stdout,
        'onnx_sha256': sha(model), 'untrained': True,
    }
    (HERE / 'reports/environment.json').write_text(json.dumps(environment, indent=2))
    command = [sys.executable, '-u', str(HERE / 'scripts/convert_rknn.py'), str(model), str(out)]
    started = time.perf_counter()
    with (HERE / 'reports/build.log').open('w') as log:
        log.write(json.dumps({'command': command, 'environment': environment}, indent=2) + '\n')
        log.flush()
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=HERE)
    report = {'passed': result.returncode == 0 and out.exists(), 'returncode': result.returncode,
              'duration_s': time.perf_counter() - started, 'onnx_sha256': sha(model),
              'rknn_sha256': sha(out) if out.exists() else None,
              'log_path': str(HERE / 'reports/build.log'), 'untrained': True,
              'quantization': False, 'target': 'rk3588', 'command': command}
    (HERE / 'reports/build_result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
