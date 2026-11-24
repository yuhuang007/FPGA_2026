from pathlib import Path
import json, re, hashlib

root = Path(__file__).resolve().parents[1]
build, = (root / 'build').glob('SOURCE_MAP_3_6_1_*')
report = build / 'report_timing/fpga_gsv1_top.rtr'
timing = report.read_text(errors='replace')
summary = {}
for corner in ('Slow', 'Fast'):
    for check in ('Setup', 'Hold'):
        block = timing.split(f'{check} Summary({corner} Corner):', 1)[1].split('====', 1)[0]
        values = {}
        for clock in ('ddrphy_clkin', 'pix_clk'):
            match = re.search(r'^\s*' + clock + r'\s+' + clock + r'\s+([\d.-]+)', block, re.M)
            assert match, (corner, check, clock)
            values[clock] = float(match.group(1))
        match = re.search(r'eth2_phy_tx_capture\s+([\d.-]+)', block)
        assert match
        values['net2_nominal_PHY_capture'] = float(match.group(1))
        summary[f'{corner.lower()}_{check.lower()}_slack_ns'] = values
resources = {}
map_log = (build / 'device_map/run.log').read_text(errors='replace')
for name in ('FF', 'LUT', 'DRM', 'PLL', 'IO'):
    match = re.search(r'^\| ' + name + r'\s+\|\s+([\d.]+)\s+\|\s+([\d.]+)', map_log, re.M)
    assert match, name
    resources[name] = {'used': float(match.group(1)), 'available': float(match.group(2))}
result = {
    'report': str(report),
    'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
    'declared_constraints_met': 'Design Summary : All Constraints Met.' in timing,
    'summary': summary,
    'resources': resources,
    'limits': [
        'Inherited constraints unchanged. Results cover declared internal and nominal external paths only.',
        'Net2 PHY internal delay PVT and PCB skew remain unqualified; nominal model is not full board signoff.',
        'DVP source timing and actual module DOVDD remain unknown; input timing coverage is inherited.',
        'No hardware programming or board verification performed.'
    ]
}
assert result['declared_constraints_met']
(root / 'reports/timing_resources.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
scope_file = root / 'reports/scope.json'
scope = json.loads(scope_file.read_text())
scope['new_rtl'] = [p for p in scope['new_rtl'] if p.startswith('rtl/')]
scope_file.write_text(json.dumps(scope, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
