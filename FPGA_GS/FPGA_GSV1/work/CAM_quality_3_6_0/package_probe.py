"""Freeze a passing, matched-input CAM1 controlled experiment. Never program."""
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

r = Path(__file__).resolve().parent
root = r.parents[1]
source = r/'rear_probe_source'
run = source/'build/CAM1_GREEN_CHAIN_E1_3_6_0_20261024_192436_439'
result = json.loads((run/'result.json').read_text(encoding='utf-8-sig'))
assert all(result[k] for k in ('BuildPass', 'ExistingConstraintsMet', 'InputsUnchanged'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
bit = Path(result['Release'])
assert sha(bit) == result['SHA256'].lower()
timing = (run/'report_timing/fpga_gsv1_top.rtr').read_text()
summaries = []
for name, body in re.findall(r'((?:Setup|Hold|Recovery|Removal|Pulse Width) Summary\([^\n]+\):)\s*\n(.*?)(?=\n={8,})', timing, re.S):
    rows = []
    for line in body.splitlines():
        m = re.search(r'(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$', line)
        if m:
            rows.append((float(m[1]), int(m[3])))
    assert rows and all(n == 0 for _, n in rows), name
    summaries.append(dict(summary=name, rows=len(rows), worst_slack_ns=min(x[0] for x in rows), failing_endpoints=0))
assert len(summaries) == 10, summaries
prr = (run/'place_route/fpga_gsv1_top.prr').read_text()
util = prr.split('Device Utilization Summary :')[1].split('Clock Resource')[0]
value = lambda key: float(re.search(r'\|\s*'+re.escape(key)+r'\s*\|\s*(\d+(?:\.\d+)?)', util)[1])
resources = {k:value('Use of '+k) for k in ('CLMA','CLMS','DRM','PLL')}
resources['LUT'] = sum(float(n) for n in re.findall(r'\|\s+LUT\s+\|\s*(\d+)', util)[:2])
resources['FF'] = sum(float(n) for n in re.findall(r'\|\s+FF\s+\|\s*(\d+)', util)[:2])
evidence = dict(existing_constraints_met=True, summaries=summaries, resources=resources,
                constraints_changed=False,
                limits=['Inherited external PHY PVT/PCB and camera pad electrical-model limits remain.',
                        'Test-pattern hardware result required; this is not a green-line repair.'])
(r/'reports/probe_timing_resources.json').write_text(json.dumps(evidence, indent=2)+'\n')
dest = root/'release/FPGA_GSV1_CAM1_GREEN_CHAIN_E1_3_6_0'
assert not dest.exists(), f'Refuse overwrite: {dest}'
dest.mkdir()
for name in ('rtl','vendor','constraints','config'):
    shutil.copytree(run/name, dest/'source'/name)
shutil.copy2(run/'flow.tcl', dest/'source/flow.tcl')
for name in ('scripts','sim'):
    shutil.copytree(source/name, dest/'source'/name, ignore=shutil.ignore_patterns('__pycache__'))
out = dest/'reports'
out.mkdir()
for name in ('baseline_uart.txt','rear_visible_uart.txt','cam0_baseline.json','cam1_visible.json',
             'assessment.json','scope.json','photos.json','probe_audit.json','probe_timing_resources.json',
             'cam1_probe.log','cam1_bars.log'):
    shutil.copy2(r/'reports'/name, out/name)
for name in ('result.json','inputs.json','pds_console.log'):
    shutil.copy2(run/name, out/name)
for name in ('report_timing','place_route'):
    (out/name).mkdir()
    for p in (run/name).iterdir():
        if p.is_file() and p.suffix in ('.rtr','.prr','.prt','.txt','.log'):
            shutil.copy2(p, out/name/p.name)
shutil.copy2(root/'release/FPGA_GSV1_CAM1_OV3660_3_5_8_ROTATE25_CANDIDATE/reports/sources/OV3660_datasheet.txt',out/'OV3660_datasheet.txt')
tools = dest/'tools/cam1'
tools.mkdir(parents=True)
shutil.copy2(root/'release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/tools/cam0/read_net2_diag.ps1',tools/'read_net2_diag.ps1')
for name in ('decode_cam1_green_probe.py','decode_cam1_rate.py'):
    shutil.copy2(source/'scripts'/name, tools/name)
shutil.copy2(bit, dest/bit.name)
artifact = dict(version='3.6.0 CAM1 GREEN CHAIN E1 controlled experiment',
    bitstream=str(dest/bit.name), sha256=sha(bit), generated_time_utc=result['GeneratedTime'],
    generated_time_local=datetime.fromtimestamp(bit.stat().st_mtime).astimezone().isoformat(),
    programmed=False, board_verified=False, green_line_fixed=False,
    cam0_exposure_changed=False, cam0_ownership_fix_included=False,
    sequence_seconds_after_CAM1_config=[dict(mode='live',seconds=30),dict(mode='sensor_bars',seconds=12),
        dict(mode='live_gap',seconds=8),dict(mode='FPGA_bars',seconds=12),dict(mode='live',seconds=None)],
    purpose='Separate sensor/PRE_ISP/DVP from downstream DDR/display; patterns cannot alone rule out data-dependent DVP faults.',
    uart='N2 35O W12 D6/phase3/failed1/error4/original503D8/readback503D8; W13..39 unchanged',
    rollback=str(root/'release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK_HDMI_1080P60.sbit'),
    rollback_sha256='f760692d6a1e7695d4005945d0ba977468d8857c4b36c45dc57bd98e7283acb1',
    build=str(run), timing=evidence)
(dest/'artifact.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
sums = [sha(p)+'  '+p.relative_to(dest).as_posix() for p in sorted(dest.rglob('*')) if p.is_file()]
(dest/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
print(json.dumps(artifact, ensure_ascii=False, indent=2))
