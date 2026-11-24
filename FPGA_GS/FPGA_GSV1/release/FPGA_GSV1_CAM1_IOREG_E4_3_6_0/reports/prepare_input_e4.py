"""One CAM1-only IREGIS controlled experiment, derived from frozen RAW E3.

No change of sensor values, IO levels, PCLK edge/frequency or CAM0 ownership.
The old routed input window is not a proven failure; this is a physical
register-location comparison, with unknown source IO timing kept explicit.
"""
from pathlib import Path
import hashlib, json, shutil

r = Path(__file__).resolve().parent
root = r.parents[1]
base = root / 'release/FPGA_GSV1_CAM1_RAW_E3_3_6_0/source'
s = r / 'rear_input_source'
assert not s.exists(), 'Do not overwrite an existing experiment'
s.mkdir()
for name in ('rtl', 'vendor', 'constraints', 'config', 'scripts', 'sim'):
    shutil.copytree(base/name, s/name, ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy2(base/'flow.tcl', s/'flow.tcl')
ports = [f'cmos2_data[{i}]' for i in range(8)] + ['cmos2_href', 'cmos2_vsync']
fdc = s/'constraints/mes50hp.fdc'
fdc.write_bytes(fdc.read_bytes() + (
    '\n# CAM1 IREGIS E4: existing positive-edge first FFs only; no extra stage.\n'
    '# Preserve all IO standards, pad assignments, clocks and timing budgets.\n'
    + ''.join(f'define_attribute {{p:{p}}} {{PAP_IO_REGISTER}} {{TRUE}}\n' for p in ports)
).encode())
observer = s/'rtl/network/m365_tx_observer.v'
old = observer.read_bytes()
assert old.count(b'.REVISION_ASCII("P")') == 1
observer.write_bytes(old.replace(b'.REVISION_ASCII("P")', b'.REVISION_ASCII("I")'))
for file, before, after in (
    ('scripts/read_net2_diag.ps1', b'35[OP]', b'35[OPI]'),
    ('scripts/decode_cam1_patch.py', b'^N2 35P ', b'^N2 35[PI] '),
    ('scripts/decode_cam1_rate.py', b"'N2 35P '", b"'N2 35P ', 'N2 35I '"),
):
    p=s/file; b=p.read_bytes(); assert before in b; p.write_bytes(b.replace(before, after))
p=s/'scripts/read_net2_diag.ps1'
p.write_bytes(p.read_bytes().replace(b'No N2 35O/35P line.', b'No N2 35O/35P/35I line.'))

flow=(s/'flow.tcl').read_text()
# PDS parses ordinary Tcl before scheduling implementation tasks. A read of
# device_map/run.log here runs too early. Verify actual packing in the external
# post-implementation checker instead, never inside this deferred flow script.
flow=flow.replace('report_timing\ngen_bit_stream', 'report_timing -report_io_datasheet -input_pins TRUE\ngen_bit_stream')
(s/'flow.tcl').write_text(flow)
p=s/'scripts/build_cam0.ps1'
b=p.read_bytes().replace(b"CAM1_RAW_E3_3_6_0", b"CAM1_IOREG_E4_3_6_0")
b=b.replace(b'CAM1 pre-DDR native pixel patch E3; original sensor settings; no quality fix claimed',
            b'CAM1 IO input-register E4 controlled comparison; unknown external source timing; no quality fix claimed')
p.write_bytes(b)

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
changes=[]
for name in ('rtl','vendor','constraints','config'):
    for p in (s/name).rglob('*'):
        if p.is_file() and (not (base/p.relative_to(s)).exists() or sha(p)!=sha(base/p.relative_to(s))):
            changes.append(p.relative_to(s).as_posix())
assert set(changes)=={'constraints/mes50hp.fdc','rtl/network/m365_tx_observer.v'},changes
assert sha(s/'rtl/board/fpga_gsv1_top.v')==sha(base/'rtl/board/fpga_gsv1_top.v')
result=dict(baseline=str(base),candidate=str(s),hardware_changes=changes,
    input_ports=ports,uart_identity='N2 35I, C1R8 and C1PX layouts unchanged',
    no_rtl_video_datapath_change=True,no_cam0_fix_mixed=True,
    sensor_registers_unchanged=True,io_levels_unchanged=True,pclk_positive_edge_unchanged=True,
    dedicated_ioclk_rejected='Local Place-0089: these IO loaders cannot use one IOCLKBUF; no such route in candidate',
    local_global_clock_probe='All10 actual IREGIS; internal constraints met. This is not full-design placement or source timing signoff.',
    hypothesis='Registered IO reduces pad-to-first-FF routing dispersion; compare coloured dark lines without changing image processing.',
    limitations=['Global PCLK path retained; IREGIS shifts receiving aperture and may increase hold demand.',
                 'TY DOVDD, source tCO/edge, board/FFC skew remain unknown; no source IO slack is claimed.',
                 'A changed image supports sampling sensitivity, not a unique root cause; independent PNR can change unrelated physical routes.'])
(r/'reports/input_e4_changes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))

q=r/'reports/electrical_audit/electrical_findings.json'
j=json.loads(q.read_text())
j['cam0']['full_test']='PASS: reports/front_grs_regression/simulation.log; 5good/1bad,5 unique DDR frames; exact5529600 writes/4838400 reads; no read faults'
j['cam0']['board_30fps_verified']=False
j['sole_next_step']['action']='User has no measurement equipment and authorized a controlled implementation comparison. Build only CAM1 IREGIS E4 after local mapping/internal timing; retain all external electrical/timing unknowns.'
j['sole_next_step']['minimum_user_information']='No further equipment question. After a releasable controlled candidate exists: one manual download, rear original view, original lighting/dark cover comparison; no Pi changes.'
q.write_text(json.dumps(j,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
