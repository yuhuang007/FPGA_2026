"""One diagnostic image; no programming, no replacement of any release."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,re,shutil
r=Path(__file__).resolve().parent;root=r.parents[1];s=r/'rear_blc_source'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
runs=list((s/'build').glob('CAM1_BLC_E5_3_6_0_*'));assert len(runs)==2
results={run:json.loads((run/'result.json').read_text(encoding='utf-8-sig')) for run in runs}
passed=[run for run,res in results.items() if res['BuildPass']];assert len(passed)==1
run=passed[0];res=results[run]
checks=json.loads((r/'reports/blc_e5_checks.json').read_text(encoding='utf-8-sig'))
assert res['BuildPass'] and res['ExistingConstraintsMet'] and res['InputsUnchanged'] and checks['pass_']
manifest=json.loads((run/'inputs.json').read_text(encoding='utf-8-sig'))
for item in manifest:
 assert sha(run/item['RelativePath'])==item['SnapshotSHA256'].lower(),item['RelativePath']
 assert sha(Path(item['Source']))==item['SHA256'].lower(),item['Source']
bit=Path(res['Release']);assert sha(bit)==res['SHA256'].lower()
prr=(run/'place_route/fpga_gsv1_top.prr').read_text(errors='replace')
t=(run/'report_timing/fpga_gsv1_top.rtr').read_text(errors='replace')
summaries=[]
for name,body in re.findall(r'((?:Setup|Hold|Recovery|Removal|Pulse Width) Summary\([^\n]+\):)\s*\n(.*?)(?=\n={8,})',t,re.S):
 rows=[]
 for line in body.splitlines():
  m=re.search(r'(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$',line)
  if m:rows.append((float(m[1]),int(m[3])))
 assert rows and all(v>=0 and n==0 for v,n in rows),name
 summaries.append(dict(summary=name,worst_slack_ns=min(v for v,_ in rows),failing_endpoints=0))
assert len(summaries)==10
body=prr.split('Device Utilization Summary :')[-1]
value=lambda k:float(re.search(r'\|\s*'+re.escape(k)+r'\s*\|\s*(\d+(?:\.\d+)?)',body)[1])
resources={k:value('Use of '+k) for k in ('CLMA','CLMS','DRM','PLL')}
for k in ('LUT','FF'):resources[k]=sum(float(n) for n in re.findall(r'\|\s+'+k+r'\s+\|\s*(\d+)',body)[:2])
pins={}
for line in prr.splitlines():
 if line.startswith('| cmos2_'):
  q=[v.strip() for v in line.strip('| ').split('|')]
  if q[0].startswith('cmos2_data[') or q[0] in ('cmos2_href','cmos2_vsync'):pins[q[0]]=q
assert len(pins)==10 and all(q[-1]=='IREGIS' for q in pins.values())
assert all(q[5]==('LVCMOS12' if q[0].startswith('cmos2_data') else 'LVCMOS33') for q in pins.values())
io=[]
for l in t.splitlines():
 m=re.match(r' cmos2_pclk\s+(cmos2_\S+)\s+(-?[\d.]+) \(r\)\s+(SLOW|FAST)\s+(-?[\d.]+) \(r\)',l)
 if m:io.append(dict(port=m[1],corner=m[3],setup_requirement_ns=float(m[2]),hold_requirement_ns=float(m[4])))
assert len(io)==20
timing=dict(internal_constraints_met=True,summaries=summaries,resources=resources,
 implemented_input_registers={p:q[-1] for p,q in pins.items()},IO_receiver_requirements=io,
 external_DVP_input_timing_signed_off=False,
 limits=['TY module DOVDD, source output tCO min/max/guaranteed launch edge and actual FFC/PCB skew remain unknown.',
         'Receiver IO datasheet numbers are requirements, not source margin or physical measurements.',
         'E4 constraints preserved byte-for-byte. No period relaxation or new false path.',
         'Inherited network/other external model limitations remain; internal STA is not full board signoff.'])
(r/'reports/blc_e5_timing_resources.json').write_text(json.dumps(timing,indent=2))
dest=root/'release/FPGA_GSV1_CAM1_BLC_E5_3_6_0';assert not dest.exists();dest.mkdir()
for folder in ('rtl','vendor','constraints','config'):shutil.copytree(run/folder,dest/'source'/folder)
shutil.copy2(run/'flow.tcl',dest/'source/flow.tcl')
for folder in ('scripts','sim'):shutil.copytree(s/folder,dest/'source'/folder,ignore=shutil.ignore_patterns('__pycache__'))
reports=dest/'reports';reports.mkdir()
for name in ('result.json','inputs.json','pds_console.log'):shutil.copy2(run/name,reports/name)
for name in ('blc_e5_checks.json','blc_e5_timing_resources.json','blc_control.log','blc_strip.log','blc_uart.log','blc_label.log','blc_overlay.log',
             'blc_strip_fixture_transition_failure.log','blc_strip_fixture_id_failure.log'):
 shutil.copy2(r/'reports'/name,reports/name)
for folder in ('report_timing','place_route','device_map','constraint_check'):
 (reports/folder).mkdir()
 for f in (run/folder).iterdir():
  if f.is_file() and f.suffix in ('.rtr','.prr','.prt','.dmr','.pcf','.ccr','.log'):shutil.copy2(f,reports/folder/f.name)
shutil.copytree(r/'reports/blc_e5_basis',reports/'sources')
evidence=json.loads((r/'reports/blc_e5_basis/evidence.json').read_text())
pdf=Path(evidence['source_pdf']);assert sha(pdf)==evidence['sha256'];shutil.copy2(pdf,reports/'sources'/pdf.name)
for name in ('prepare_blc_e5.py','integrate_blc_e5.py','prepare_blc_checks.py','check_blc_e5.py','check_blc_overlay.py','package_blc_e5.py'):
 shutil.copy2(r/name,reports/name)
for name in ('blc_meta_pages.txt','blc_strip_pages.txt','blc_uart_lines.txt'):shutil.copy2(s/name,reports/name)
tools=dest/'tools/cam1';tools.mkdir(parents=True)
for name in ('read_net2_diag.ps1','decode_cam1_patch.py','decode_cam1_blc.py','decode_cam1_rate.py'):shutil.copy2(s/'scripts'/name,tools/name)
shutil.copy2(bit,dest/bit.name)
rollback=root/'release/FPGA_GSV1_CAM1_IOREG_E4_3_6_0/FPGA_GSV1_CAM1_IOREG_E4_3_6_0_HDMI_1080P60.sbit'
assert sha(rollback)=='ff11e6121a4adf898f6d74115883a9d7bc2a20d4f38508a40fee56b94692e896'
failed_evidence=[]
for failed,rr in results.items():
 if rr['BuildPass']:continue
 fdir=reports/'failed_internal_STA'/failed.name;fdir.mkdir(parents=True)
 for name in ('result.json','inputs.json','pds_console.log'):shutil.copy2(failed/name,fdir/name)
 shutil.copy2(failed/'report_timing/fpga_gsv1_top.rtr',fdir/'fpga_gsv1_top.rtr')
 failed_evidence.append(dict(build=str(failed),setup_WNS_ns=-.607,
  path='OSD Chinese font DRM -> added diagnostic select -> high-fanout HDMI RGB IOL register',
  repair='Register composed OSD area/pixel; add exactly one cycle to matching pixel/HS/VS/DE/alarm pipeline. Period/IO/clock constraints unchanged.',
  check='12000cycle exact one-cycle retiming equivalence with actual font, labels and raster output slice.',
  unqualified_bitstream_not_packaged=True))
artifact=dict(version='3.6.0 CAM1 BLC E5 A-B-Aprime controlled diagnostic',
 bitstream=str(dest/bit.name),sha256=sha(bit),generated_utc=res['GeneratedTime'],
 generated_china_time=datetime.fromtimestamp(bit.stat().st_mtime,timezone(timedelta(hours=8))).isoformat(),
 programmed=False,board_verified=False,stripes_fixed=False,qualified_functional_release=False,
 build_input_snapshot_hashes_verified=True,
 failed_build_evidence=failed_evidence,
 E4_board_result='User confirms changing purple/red dark-field lines persist; E4 did not resolve stripes.',
 build=str(run),uart_identity='N2 35B, C1BR PRE/POST, C1BT phase/status, C1PX strip, inherited C1R8 rates',
 changes=checks['changes'],timing=timing,
 experiment=dict(prepare_seconds=60,each_export_seconds=45,overall_approx_seconds=200,
   common_preparation='Pin manual AEC/AGC with3503[1:0] and AWB with3406[0], read current held values, rewrite those same exposure/gain/WB values and verify each byte; A must still reproduce stripes.',
   A='Original BLC updating state, all shared parameters fixed.',
   B='4005 RMW clear bit1, then4003 RMW set bit6; never replay4003[7] REDO.',
   Aprime='4003 original operating bits[6:0], then original4005, verify each; do not replay REDO.',
   final='Readback-verified restoration of4003 working bits,4005,3503,3406; only then DONE. Failures INVALID with best effort restore.',
   never_written='4002, BLC windows/targets,402C..4033 coefficients, sampling edge/PLL/IO settings.',
   evidence='One unenhanced16x720 RGB565 strip at source x1120 before DDR per stage. PRE/POST56-register scans with CRC/time/source frame tags; coefficient reads not atomic.',
   validity='A reproduces, lens stays covered, shared parameters stable, full three CRC-valid strips, B coefficient PRE/POST stable, and final restore verified. Black/dark/desaturated output is not improvement.',
   interpretation='B attenuates and Aprime returns supports dynamic BLC involvement only. B unchanged lowers priority. Invalid conditions prohibit conclusions.'),
 protected='CAM0 ownership/exposure, CAM1 sensor init/sync/rotation/720p25, DDR, HDMI raster format/PLL/filter algorithms, MAC/protocol/PHY/PLL/RGMII unchanged. Network module edits only expose UART snapshot pulse.',
 output_pipeline_change='Diagnostic OSD composition registered; RGB/raster/OSD/alarm all delayed one extra pixel clock together, verified exact retiming. 1080p60 format remains unchanged.',
 physical_limit='All three phases run in one physical implementation. Comparison against E4 also changes PNR placement/routing, so is not a one-physical-variable comparison.',
 source_basis=evidence,
 minimum_user_action='Cover CAM1 before manual SRAM download; select rear single/original; keep COM23 free and immediately confirm download. Keep covered through A/B/Aprime until DONE, about3min20s. No reset or Pi service changes.',
 rollback=str(rollback),rollback_sha256=sha(rollback),rollback_note='E4 is the controlled recovery baseline, not a stripe fix. Never use an unverified board reset key.',
 next_step_after_board='Apply fixed validity and decision rules; no further register tuning before results.')
(dest/'artifact.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
entries=[sha(f)+'  '+f.relative_to(dest).as_posix() for f in sorted(dest.rglob('*')) if f.is_file()]
(dest/'SHA256SUMS').write_text('\n'.join(entries)+'\n')
print(json.dumps(dict(bitstream=artifact['bitstream'],sha256=artifact['sha256'],generated_china_time=artifact['generated_china_time'],
 timing=timing,rollback=str(rollback)),ensure_ascii=False,indent=2))

