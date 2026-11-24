import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

r = Path(__file__).resolve().parent
base = r.parents[1] / 'release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/source'
probe = r / 'rear_probe_source'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
changes = []
unchanged = 0
for root in ('rtl', 'vendor', 'constraints'):
    for path in sorted((probe/root).rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(probe)
        original = base / rel
        if original.exists() and sha(original) == sha(path):
            unchanged += 1
        else:
            changes.append(dict(path=rel.as_posix(), added=not original.exists(), sha256=sha(path)))
assert {c['path'] for c in changes} == {'rtl/board/fpga_gsv1_top.v', 'rtl/capture/cam1_green_probe.v'}
result = dict(unchanged_protected_files=unchanged, changes=changes,
              constraints_unchanged=sha(base/'constraints/mes50hp.fdc') == sha(probe/'constraints/mes50hp.fdc'))
# Decoder regression uses synthetic W12 experiment phases and the existing rate
# decoder. These are test records, never reported as hardware observations.
rows = []
for phase in (1, 2, 3, 4, 5):
    for i in range(2):
        w = [0]*40
        w[12] = (0xd6 << 24) | (phase << 21) | (0x3c << 8) | (0xb0 if phase == 2 else 0x3c)
        w[13] = 921600
        w[14] = (1 << 26) | 720
        w[15] = phase*100+i*25
        w[16] = (phase*2+i)*1000
        w[17] = ((phase*100+i*25) << 16) | (phase*100+i*25)
        w[18] = w[16]
        w[19] = 72000000
        rows.append('N2 35O ' + ' '.join(f'{v:08x}' for v in w))
with tempfile.TemporaryDirectory(prefix='cam1_decoder_check_') as tmp:
    path = Path(tmp)/'synthetic.txt'
    path.write_text('\n'.join(rows)+'\n')
    def run():
        return subprocess.run([sys.executable, str(probe/'scripts/decode_cam1_green_probe.py'), str(path)],
                              capture_output=True, text=True, encoding='utf-8')
    check = run()
    assert check.returncode == 0, check.stderr or check.stdout
    decoded = json.loads(check.stdout)
    assert len(decoded['stages']) == 5 and decoded['records'] == 10
    assert all(s['rate']['capture_fps'] == 25 and s['rate']['geometry_ok'] for s in decoded['stages'])
    path.write_text('N2 35O 00000000\n')
    assert run().returncode == 2
result['decoder_checks'] = 'PASS synthetic phase separation, rates, geometry, truncated-result rejection'
(r/'reports/probe_audit.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
