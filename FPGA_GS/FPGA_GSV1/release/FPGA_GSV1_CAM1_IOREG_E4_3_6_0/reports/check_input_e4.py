"""Narrow E4 checks: source isolation, exact FDC append and existing UART data.
No hardware IO, new video/algorithm test, or network activity.
"""
from pathlib import Path
import hashlib, importlib.util, json, subprocess, sys
r=Path(__file__).resolve().parent
s=r/'rear_input_source'
base=r.parents[1]/'release/FPGA_GSV1_CAM1_RAW_E3_3_6_0/source'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ports=[f'cmos2_data[{i}]' for i in range(8)]+['cmos2_href','cmos2_vsync']
old=(base/'constraints/mes50hp.fdc').read_bytes()
new=(s/'constraints/mes50hp.fdc').read_bytes()
assert new.startswith(old)
added=new[len(old):].decode()
assert [l for l in added.splitlines() if l.startswith('define_attribute')]==[
    f'define_attribute {{p:{p}}} {{PAP_IO_REGISTER}} {{TRUE}}' for p in ports]
assert not any(w in added for w in ['set_input_delay','false_path','LVCMOS','PAP_IO_DRIVE','create_clock'])
changed=[];protected={}
for name in ('rtl','vendor','config'):
    for p in (s/name).rglob('*'):
        if p.is_file():
            rel=p.relative_to(s).as_posix()
            if sha(p)!=sha(base/rel):changed.append(rel)
            else:protected[rel]=sha(p)
assert changed==['rtl/network/m365_tx_observer.v'],changed
o=(base/changed[0]).read_bytes()
assert (s/changed[0]).read_bytes()==o.replace(b'.REVISION_ASCII("P")',b'.REVISION_ASCII("I")')
assert '.FRONT_BLANKING_GRANT' not in (s/'rtl/board/fpga_gsv1_top.v').read_text(encoding='utf-8')
spec=importlib.util.spec_from_file_location('e4decode',s/'scripts/decode_cam1_patch.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
oldlog=(r/'reports/RAW_E3_second_capture.txt').read_text(encoding='utf-8-sig')
newlog=oldlog.replace('N2 35P ','N2 35I ')
a=m.decode(oldlog);b=m.decode(newlog)
assert a==b and len(b[2])==23040 and b[0][0]==490
out=r/'reports/input_e4_checker';out.mkdir(exist_ok=True)
(out/'synthetic_I_from_existing_P.txt').write_text(newlog)
cmd=[sys.executable,str(s/'scripts/decode_cam1_rate.py'),str(out/'synthetic_I_from_existing_P.txt'),'--output',str(out/'synthetic_I_rates.json')]
z=subprocess.run(cmd,capture_output=True,text=True);assert z.returncode==0,z.stderr
rates=json.loads((out/'synthetic_I_rates.json').read_text());assert rates['completed'] and rates['records']>2
result=dict(pass_=True,constraints_only_ten_input_register_attributes=True,
    physical_clock_io_standard_edge_and_sensor_unchanged=True,
    protected_source_hashes=protected,
    e4_parser_lossless_against_existing_e3_capture=True,
    parser_test_is_synthetic_not_new_board_evidence=True,
    roi_crc32=f'{b[0][-1]:08x}',frame_id=b[0][0],
    reused_production_pixel_oracle='reports/audit_cam1_preddr.log: no production RTL datapath changed',
    no_new_fpga_download_uart_or_pi_activity=True)
(r/'reports/input_e4_checks.json').write_text(json.dumps(result,indent=2))
print('PASS exact ten IREGIS attributes; protected RTL/vendor/config unchanged; I UART parser lossless, existing complete E3 source data (not new board capture)')
