"""Package only one internally timed CAM1 IREGIS comparison; never overwrite."""
from pathlib import Path
from datetime import datetime
import hashlib,json,re,shutil
r=Path(__file__).resolve().parent;root=r.parents[1];s=r/'rear_input_source'
runs=list((s/'build').glob('CAM1_IOREG_E4_3_6_0_*'))
assert len(runs)==1,'Exactly one full controlled build is expected'
run=runs[0];original=json.loads((run/'result.json').read_text(encoding='utf-8-sig'))
res=json.loads((run/'postbuild_audit.json').read_text())
assert res['ImplementationValidated'] and original['ExistingConstraintsMet'] and original['InputsUnchanged']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bit=Path(res['Release']);assert sha(bit)==res['SHA256'].lower()
prr=(run/'place_route/fpga_gsv1_top.prr').read_text(encoding='utf-8',errors='replace')
pins={}
for line in prr.splitlines():
    if line.startswith('| cmos2_'):
        q=[x.strip() for x in line.strip('| ').split('|')]
        if q[0].startswith('cmos2_data[') or q[0] in ('cmos2_href','cmos2_vsync'):
            pins[q[0]]=q
assert len(pins)==10 and all(q[-1]=='IREGIS' for q in pins.values()),pins
assert all(q[5]==('LVCMOS12' if q[0].startswith('cmos2_data') else 'LVCMOS33') for q in pins.values())
t=(run/'report_timing/fpga_gsv1_top.rtr').read_text()
summaries=[]
for name,body in re.findall(r'((?:Setup|Hold|Recovery|Removal|Pulse Width) Summary\([^\n]+\):)\s*\n(.*?)(?=\n={8,})',t,re.S):
    rows=[]
    for line in body.splitlines():
        m=re.search(r'(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$',line)
        if m:rows.append((float(m[1]),int(m[3])))
    assert rows and all(n==0 for _,n in rows),name
    summaries.append(dict(summary=name,worst_slack_ns=min(x[0] for x in rows),failing_endpoints=0))
assert len(summaries)==10
body=prr.split('Device Utilization Summary :')[-1]
value=lambda key:float(re.search(r'\|\s*'+re.escape(key)+r'\s*\|\s*(\d+(?:\.\d+)?)',body)[1])
resources={k:value('Use of '+k) for k in ('CLMA','CLMS','DRM','PLL')}
for key in ('LUT','FF'):
    resources[key]=sum(float(n) for n in re.findall(r'\|\s+'+key+r'\s+\|\s*(\d+)',body)[:2])
io=[]
for l in t.splitlines():
    m=re.match(r' cmos2_pclk\s+(cmos2_\S+)\s+(-?[\d.]+) \(r\)\s+(SLOW|FAST)\s+(-?[\d.]+) \(r\)',l)
    if m:io.append(dict(port=m[1],corner=m[3],setup_ns=float(m[2]),hold_ns=float(m[4])))
assert len(io)==20,len(io)
timing=dict(internal_constraints_met=True,summaries=summaries,resources=resources,
    implemented_input_registers={p:q[-1] for p,q in pins.items()},io_receiver_requirements=io,
    worst_pad_setup_ns=max(x['setup_ns'] for x in io),worst_pad_hold_ns=max(x['hold_ns'] for x in io),
    source_io_slack_unknown=True,external_input_timing_signed_off=False,
    limits=['No source tCO min/max/launch-edge guarantee, TY DOVDD or actual board/FFC skew available.',
            'IO datasheet is receiver requirement only, not measured margin. Unknown input delay has not been replaced with zero.',
            'All inherited clocks/IO standards/uncertainties preserved; no false path or relaxed period added.',
            'Existing network/other external timing limits remain. No board quality claim from internal STA.',
            'PAP_IO_REGISTER changes physical sampling aperture; hold demand may grow. No source margin improvement claimed.'])
(r/'reports/input_e4_timing_resources.json').write_text(json.dumps(timing,indent=2))
dest=root/'release/FPGA_GSV1_CAM1_IOREG_E4_3_6_0';assert not dest.exists()
dest.mkdir()
for folder in ('rtl','vendor','constraints','config'):
    shutil.copytree(run/folder,dest/'source'/folder)
# Corrected entry removes the premature guard read only. Preserve original
# submitted flow next to the original failed-wrapper result for traceability.
shutil.copy2(s/'flow.tcl',dest/'source/flow.tcl')
for folder in ('scripts','sim'):
    shutil.copytree(s/folder,dest/'source'/folder,ignore=shutil.ignore_patterns('__pycache__'))
out=dest/'reports';out.mkdir()
for name in ('input_e4_changes.json','input_e4_checks.json','input_e4_timing_resources.json'):
    shutil.copy2(r/'reports'/name,out/name)
for name in ('result.json','inputs.json','pds_console.log','postbuild_audit.json'):
    shutil.copy2(run/name,out/name)
shutil.copy2(run/'flow.tcl',out/'original_submitted_flow.tcl')
for name in ('audit_input_e4_build.py','analyze_input_e4.py','check_input_e4.py','prepare_input_e4.py'):
    shutil.copy2(r/name,out/name)
for folder in ('report_timing','place_route','device_map'):
    (out/folder).mkdir()
    for p in (run/folder).iterdir():
        if p.is_file() and p.suffix in ('.rtr','.prr','.prt','.dmr','.pcf','.log'):
            shutil.copy2(p,out/folder/p.name)
shutil.copytree(r/'reports/electrical_audit',out/'prior_electrical_audit',
    ignore=shutil.ignore_patterns('*.adf','*.db','*.pds','*.png','*.pdf'))
for name in ('input_path_audit.json','input_path_audit.csv'):
    p=r/'reports/input_e4_paths'/name
    if p.exists():shutil.copy2(p,out/name)
tools=dest/'tools/cam1';tools.mkdir(parents=True)
for name in ('read_net2_diag.ps1','decode_cam1_patch.py','decode_cam1_rate.py'):
    shutil.copy2(s/'scripts'/name,tools/name)
shutil.copy2(bit,dest/bit.name)
rollback=root/'release/FPGA_GSV1_CAM1_RAW_E3_3_6_0/FPGA_GSV1_CAM1_RAW_E3_3_6_0_HDMI_1080P60.sbit'
assert sha(rollback)=='8e7addbe24c20757de9f2286b57fd83ef0539319b5dd83869b961c23d8286756'
a=dict(version='3.6.0 CAM1 IOREG E4 controlled board experiment',bitstream=str(dest/bit.name),
    sha256=sha(bit),generated_utc=res['GeneratedTime'],
    generated_local=datetime.fromtimestamp(bit.stat().st_mtime).astimezone().isoformat(),
    programmed=False,board_verified=False,green_lines_fixed=False,qualified_functional_release=False,
    build_wrapper_original_pass=original['BuildPass'],independent_implementation_validation_pass=True,
    build_wrapper_issue='Premature Tcl guard read failed before deferred implementation started. Original BuildPass:false retained. All actual design actions succeeded; independent exact-error classification + snapshot hashes +10 IREGIS + fresh final-DB STA query validated. Future flow guard removed; no RTL/FDC repair or rebuild.',
    build=str(run),uart_identity='N2 35I; original C1R8 and C1PX payload unchanged',
    actual_changes='CAM1 data8/HREF/VS existing first positive-edge FFs packed into IOL. UART revision only other RTL edit.',
    unchanged='Sensor config/exposure/gain/BLC, IO standard/drive/PCLK/PLL, camera byte assembly, CAM0 owner, HDMI/DDR/filter/network logic.',
    physical_pnr_caveat='Placement/routing rerun can alter paths beyond the logical change. No claim that only one physical quantity changed.',
    rollback=str(rollback),rollback_sha256=sha(rollback),timing=timing,
    minimal_board_action='One manual SRAM download; KEY6 original, KEY5 rear single; compare same light/position then cover lens once5s. Keep COM23 free; no reset/cabling/Pi/LIVE.',
    interpretation='Improvement supports DVP input implementation sensitivity; persistent lines leave source/ISP or other electrical faults unresolved. No unique root cause from one comparison.',
    front30_fix_included=False)
(dest/'artifact.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
entries=[sha(p)+'  '+p.relative_to(dest).as_posix() for p in sorted(dest.rglob('*')) if p.is_file()]
(dest/'SHA256SUMS').write_text('\n'.join(entries)+'\n')
print(json.dumps(a,ensure_ascii=False,indent=2))
