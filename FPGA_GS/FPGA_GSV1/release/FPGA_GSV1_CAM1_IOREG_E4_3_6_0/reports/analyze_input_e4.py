"""Query final E4 PNR only; compare receiver windows, never invent source slack."""
from pathlib import Path
import csv,json,re,subprocess
r=Path(__file__).resolve().parent
run=next((r/'rear_input_source/build').glob('CAM1_IOREG_E4_3_6_0_*'))
res=json.loads((run/'postbuild_audit.json').read_text());assert res['ImplementationValidated']
out=r/'reports/input_e4_paths';out.mkdir(exist_ok=True)
clock=out/'clock_paths';clock.mkdir(exist_ok=True)
pds='E:/XUEXI/FPGA_PDS/PDS_2022.2-SP6.4/bin/pds_shell.exe'
# Build a report-only project with explicit architecture/source declarations.
# open_project is scheduled by PDS but rejected by its initial -file parser;
# do not suppress that error or reopen/mutate the original build project.
setup=(run/'flow.tcl').read_text().split('compile -top_module')[0]
setup=re.sub(r'(add_design|add_constraint) "([^"]+)"',lambda m:f'{m[1]} "{(run/m[2]).as_posix()}"',setup)
for name,dest,froms,npaths,nworst in (
    ('inputs',out,'cmos2_data* cmos2_href cmos2_vsync',200,16),
    ('clocks',clock,'cmos2_d_d0* cmos2_href_d0* cmos2_vsync_d0*',160,4)):
    tcl=out/f'query_{name}.tcl'
    tcl.write_text(setup+f'''
set_dir -impl_directory {dest.as_posix()}
report_timing -force_to_run -input_db_file {run.as_posix()}/place_route/fpga_gsv1_top_pnr.adf -from {{{froms}}} -max_path {npaths} -nworst {nworst} -input_pins TRUE -report_io_datasheet -report_exception TRUE
exit
''')
    qlog=out/f'query_{name}.log'
    if qlog.exists() and re.search(r'^E:',qlog.read_text(errors='replace'),re.M):
        import shutil
        shutil.copy2(qlog,out/f'query_{name}_earlier_parse_error.log')
    with qlog.open('w') as f:
        a=subprocess.run([pds,'-file',str(tcl)],cwd=out,stdout=f,stderr=subprocess.STDOUT)
    text=(out/f'query_{name}.log').read_text(errors='replace')
    assert a.returncode==0 and not re.search(r'^E:',text,re.M),name
report=(out/'report_timing/fpga_gsv1_top.rtr').read_text()
paths=[]
for b in re.split(r'(?=Startpoint  :)',report)[1:]:
    s=re.match(r'Startpoint  : (.*?) \(port\)',b)
    e=re.search(r'Endpoint    : (.*)',b)
    k=re.search(r'Path Type   : (min|max) \((slow|fast) corner\)',b)
    a=re.search(r'Data arrival time\s+([\d.]+)',b)
    if not (s and e and k and a):continue
    line=next(l for l in b.splitlines() if l.strip().endswith(s[1]+' (port)') and not l.startswith('Startpoint'))
    transition=line.split(s[1])[0].split()[-1];assert transition in ('r','f')
    paths.append(dict(port=s[1],endpoint=e[1].strip(),kind=k[1],corner=k[2],input_transition=transition,capture_clock_edge='r',delay_ns=float(a[1])))
assert len(paths)==40,len(paths)
clocks=[]
for b in re.split(r'(?=Startpoint  :)',(clock/'report_timing/fpga_gsv1_top.rtr').read_text())[1:]:
    s=re.match(r'Startpoint  : ((?:cmos2_d_d0\[\d+\]|cmos2_href_d0|cmos2_vsync_d0))/([^\n]+)',b)
    k=re.search(r'Path Type   : (min|max) \((slow|fast) corner\)',b)
    a=re.search(r'Launch Clock Delay\s+:\s+([\d.]+)',b)
    if s and k and a:
        v=dict(register=s[1],mapped_clock_pin=s[2].strip(),kind=k[1],corner=k[2],delay_ns=float(a[1]))
        if v not in clocks:clocks.append(v)
ds=[]
for l in report.splitlines():
    m=re.match(r' cmos2_pclk\s+(cmos2_\S+)\s+(-?[\d.]+) \(r\)\s+(SLOW|FAST)\s+(-?[\d.]+) \(r\)',l)
    if m:ds.append(dict(port=m[1],corner=m[3].lower(),setup_ns=float(m[2]),hold_ns=float(m[4])))
assert len(ds)==20 and len(clocks)>=40,(len(ds),len(clocks))
old=json.loads((r/'reports/electrical_audit/input_path_audit.json').read_text())
rows=[]
for port in sorted({p['port'] for p in paths}):
    for corner in ('slow','fast'):
        pp=[p for p in paths if p['port']==port and p['corner']==corner]
        reg={'cmos2_href':'cmos2_href_d0','cmos2_vsync':'cmos2_vsync_d0'}.get(port,port.replace('data','d_d0'))
        cs=[c for c in clocks if c['register']==reg and c['corner']==corner]
        assert len(cs)==2,(reg,corner,cs)
        d={p['kind']:p['delay_ns'] for p in pp};c={a['kind']:a['delay_ns'] for a in cs}
        z=next(a for a in ds if a['port']==port and a['corner']==corner)
        rows.append(dict(port=port,corner=corner,data_min_ns=d['min'],data_max_ns=d['max'],clock_early_ns=c['min'],clock_late_ns=c['max'],pad_setup_ns=z['setup_ns'],pad_hold_ns=z['hold_ns']))
def span(ps,corner):
    a=[p for p in ps if p['corner']==corner and p['port'].startswith('cmos2_data')]
    return dict(min_ns=min(x['delay_ns'] for x in a),max_ns=max(x['delay_ns'] for x in a),span_ns=max(x['delay_ns'] for x in a)-min(x['delay_ns'] for x in a))
comparison=dict(baseline={c:span(old['paths'],c) for c in ('slow','fast')},candidate={c:span(paths,c) for c in ('slow','fast')},
    baseline_pad_stable_ns=[-max(x['setup_ns'] for x in old['io_datasheet']),max(x['hold_ns'] for x in old['io_datasheet'])],
    candidate_pad_stable_ns=[-max(x['setup_ns'] for x in ds),max(x['hold_ns'] for x in ds)],
    source_slack_unknown=True,clock_and_data_delays_changed_by_pnr=True,
    caveat='Spans include corners/transitions; neither span reduction nor receiver aperture proves sensor pixel correctness or positive source margin.')
(out/'input_path_audit.json').write_text(json.dumps(dict(paths=paths,clocks=clocks,io_datasheet=ds,combined=rows,comparison=comparison),indent=2))
with (out/'input_path_audit.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(comparison,indent=2))
