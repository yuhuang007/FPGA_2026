from pathlib import Path
import re,collections,json,csv
out=Path('work/CAM_quality_3_6_0/reports/electrical_audit')
r=(out/'report_timing/fpga_gsv1_top.rtr').read_text()
paths=[]
for b in re.split(r'(?=Startpoint  :)',r)[1:]:
 s=re.match(r'Startpoint  : (.*?) \(port\)',b);e=re.search(r'Endpoint    : (.*)',b);k=re.search(r'Path Type   : (min|max) \((slow|fast) corner\)',b);a=re.search(r'Data arrival time\s+([\d.]+)',b)
 if s and e and k and a:
  pinline=next(l for l in b.splitlines() if l.strip().endswith(s[1]+' (port)') and not l.startswith('Startpoint'))
  transition=pinline.split(s[1])[0].split()[-1]
  assert transition in ['r','f']
  paths.append(dict(port=s[1],endpoint=e[1].strip(),kind=k[1],corner=k[2],input_transition=transition,capture_clock_edge='r',delay_ns=float(a[1])))
assert len(paths)==40,len(paths)
cl=(out/'clock_paths/report_timing/fpga_gsv1_top.rtr').read_text(); clocks=collections.defaultdict(set)
for b in re.split(r'(?=Startpoint  :)',cl)[1:]:
 s=re.match(r'Startpoint  : (.*?)/opit_0/CLK',b);k=re.search(r'Path Type   : (min|max) \((slow|fast) corner\)',b);a=re.search(r'Launch Clock Delay\s+:\s+([\d.]+)',b)
 if s and k and a:clocks[(s[1],k[1],k[2])].add(float(a[1]))
ds=[]
for l in r.splitlines():
 m=re.match(r' cmos2_pclk\s+(cmos2_\S+)\s+(-?[\d.]+) \(r\)\s+(SLOW|FAST)\s+(-?[\d.]+) \(r\)',l)
 if m:ds.append(dict(port=m[1],corner=m[3].lower(),setup_ns=float(m[2]),hold_ns=float(m[4])))
rows=[]
for port in sorted({p['port'] for p in paths}):
 for corner in ['slow','fast']:
  p=[a for a in paths if a['port']==port and a['corner']==corner]; reg=p[0]['endpoint'].split('/')[0]
  d={a['kind']:a['delay_ns'] for a in p}; c={k:sorted(clocks.get((reg,k,corner),[])) for k in ['min','max']}
  z=next(a for a in ds if a['port']==port and a['corner']==corner)
  row=dict(port=port,corner=corner,data_min_ns=d['min'],data_min_transition=next(a['input_transition'] for a in p if a['kind']=='min'),data_max_ns=d['max'],data_max_transition=next(a['input_transition'] for a in p if a['kind']=='max'),capture_clock_edge='r',clock_early_ns=c['min'],clock_late_ns=c['max'],pad_setup_ns=z['setup_ns'],pad_hold_ns=z['hold_ns'])
  rows.append(row); print(row)
(out/'input_path_audit.json').write_text(json.dumps(dict(paths=paths,clocks=[dict(register=k[0],kind=k[1],corner=k[2],values=sorted(v)) for k,v in clocks.items()],io_datasheet=ds,combined=rows),indent=2))
with (out/'input_path_audit.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
