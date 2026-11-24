"""Record the completed independent regression; no rerun or hardware access."""
from pathlib import Path
import hashlib,json,re
r=Path(__file__).resolve().parent;o=r/'reports/front_grs_regression'
log=(o/'simulation.log').read_text()
assert 'PASS CAM0 production' in log and 'FATAL:' not in log
v=[(int(i),e) for i,e in re.findall(r'CAM0_VERDICT id=(\d+) errors=(\w+)',log)]
assert v==[(0,'00'),(1,'00'),(2,'00'),(3,'00'),(4,'01'),(5,'00')]
pub=[(int(c),int(i),int(t)) for c,i,t in re.findall(r'CAM0_PUBLICATION count=(\d+) id=(\d+) ns=(\d+)',log)]
assert [(c,i) for c,i,t in pub]==[(1,0),(2,1),(3,2),(4,3),(5,5)]
totals=dict((k,int(n)) for k,n in re.findall(r'(\w+)=(\d+)',log.split('CAM0_FINAL ')[1].splitlines()[0]))
assert totals==dict(good=5,bad=1,pubs=5,writes=5529600,reads=4838400,displays=3,independent=3,third_writes=3600,read_faults=0)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources=[r/'prepare_cam0_grs_fixture.py',r/'check_cam0_grs_regression.py',o/'cam0_front30_grs_tb.sv',o/'cmos_8_16bit_grs_fixture.v',o/'simulation.log']
sources+=list((r/'source/rtl').rglob('*.v'))
result=dict(passed=True,board_verified=False,full_build_done=False,
    verdicts=v,publication_ids=[i for _,i,_ in pub],totals=totals,
    publication_period_ms=[(pub[i][2]-pub[i-1][2])/1e9 for i in range(1,len(pub))],
    last_interval_contains_deliberate_rejected_frame=True,
    simulation_time_units='publication log ns field contains realtime rounded in1ps units; divide1e9 for milliseconds',
    startup_cause='RTL fixture omitted actual PGL50H GRS INIT0 for stopped-clock legacy gearbox and permit pipeline; production startup RTL unchanged',
    production_changes=['rtl/reuse/fram_buf.v FRONT_BLANKING_GRANT','rtl/board/fpga_gsv1_top.v CAM0 opt-in'],
    original_failure_preserved=str(r/'reports/cam0_front30_corrected.log'),
    reproduction=['python -X utf8 work/CAM_quality_3_6_0/prepare_cam0_grs_fixture.py','python -X utf8 work/CAM_quality_3_6_0/check_cam0_grs_regression.py'],
    hashes={str(p.relative_to(r)):sha(p) for p in sources},
    excluded_from_cam1_candidate=True)
(o/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='hashes'},indent=2))
