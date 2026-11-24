"""Decode the controlled CAM1 experiment using the existing C1R8 rate decoder.

Raw captures remain unchanged; normalized temporary records only adapt W12.
No phase result is treated as proof of image quality.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PHASES = {0: 'before_init', 1: 'initial_live', 2: 'sensor_bars',
          3: 'restored_live_gap', 4: 'FPGA_bars', 5: 'final_live', 7: 'failed'}
p = argparse.ArgumentParser()
p.add_argument('capture', type=Path)
p.add_argument('--output', type=Path)
a = p.parse_args()
groups = []
for line in a.capture.read_text(encoding='utf-8-sig').splitlines():
    if not line.startswith('N2 35O '):
        continue
    try:
        w = [int(v, 16) for v in line.split()[2:]]
    except ValueError:
        continue
    if len(w) != 40 or w[12] >> 24 != 0xd6:
        continue
    tag = w[12]
    phase = (tag >> 21) & 7
    status = dict(phase=phase, name=PHASES.get(phase, 'unknown'),
                  failed=bool(tag & (1 << 20)), error_code=(tag >> 16) & 15,
                  original_503d=tag >> 8 & 255, readback_503d=tag & 255)
    if not groups or groups[-1]['status'] != status:
        groups.append(dict(status=status, lines=[]))
    w[12] = 0x43315238
    groups[-1]['lines'].append('N2 35O ' + ' '.join(f'{v:08X}' for v in w))
result = dict(experiment='CAM1_GREEN_CHAIN_E1_3_6_0', records=0, stages=[],
              image_quality_verified=False)
with tempfile.TemporaryDirectory(prefix='cam1_green_decode_') as tmp:
    for i, group in enumerate(groups):
        path = Path(tmp) / f'{i}.txt'
        path.write_text('\n'.join(group['lines']) + '\n', encoding='utf-8')
        run = subprocess.run([sys.executable, str(Path(__file__).with_name('decode_cam1_rate.py')),
                              str(path)], capture_output=True, text=True, encoding='utf-8')
        if run.returncode not in (0, 2):
            raise RuntimeError(run.stderr)
        decoded = json.loads(run.stdout)
        result['records'] += decoded['records']
        result['stages'].append(dict(**group['status'], rate=decoded))
result['complete_sequence_seen'] = all(any(s['phase'] == phase and not s['failed']
    and s['rate']['records'] >= 2 for s in result['stages']) for phase in (1, 2, 3, 4, 5))
out = json.dumps(result, ensure_ascii=False, indent=2)
if a.output:
    a.output.write_text(out + '\n', encoding='utf-8')
print(out)
raise SystemExit(0 if result['complete_sequence_seen'] else 2)
