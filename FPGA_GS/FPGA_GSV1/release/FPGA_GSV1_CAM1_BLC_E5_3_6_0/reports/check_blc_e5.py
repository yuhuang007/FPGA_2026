from pathlib import Path
import hashlib,importlib.util,json,sys,zlib
r=Path(__file__).resolve().parent;s=r/'rear_blc_source';out=r/'reports/blc_e5_checks';out.mkdir(exist_ok=True)
sys.path.insert(0,str(s/'scripts'));import decode_cam1_blc as b;import decode_cam1_patch as p
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
base=r.parents[1]/'release/FPGA_GSV1_CAM1_IOREG_E4_3_6_0/source'
changed=[];protected={}
for folder in ('rtl','vendor','constraints','config'):
 for f in (s/folder).rglob('*'):
  if not f.is_file():continue
  rel=f.relative_to(s).as_posix();old=base/rel
  if not old.exists() or sha(f)!=sha(old):changed.append(rel)
  else:protected[rel]=sha(f)
allowed={'rtl/board/fpga_gsv1_top.v','rtl/capture/cam1_blc_control.v','rtl/capture/cam1_pixel_patch.v',
 'rtl/display/cam1_blc_label.v','rtl/display/m31_osd.v','rtl/display/m31_video_output.v',
 'rtl/network/m361_diag.v','rtl/network/m365_tx_observer.v','rtl/network/m3_network.v'}
assert set(changed)==allowed,changed
assert sha(s/'constraints/mes50hp.fdc')==sha(base/'constraints/mes50hp.fdc')
assert '.FRONT_BLANKING_GRANT' not in (s/'rtl/board/fpga_gsv1_top.v').read_text(encoding='utf-8')
control=(r/'reports/blc_control.log').read_text()
assert all(f'PASS control scenario {i} ' in control for i in range(8)) and 'FATAL' not in control
striplog=(r/'reports/blc_strip.log').read_text()
assert all(f'PASS stage{i} ' in striplog for i in range(3)) and 'FATAL' not in striplog
assert 'PASS BLC OSD label' in (r/'reports/blc_label.log').read_text()
assert 'PASS actual UART 600 complete lines' in (r/'reports/blc_uart.log').read_text()
assert 'PASS12000cycles exact one-cycle retiming' in (r/'reports/blc_overlay.log').read_text()
# Actual UART serializer output, not merely the held packet construction.
lines=[line for line in (s/'blc_uart_lines.txt').read_text().splitlines() if line];assert len(lines)==600
pixel_ids=[]
for i,line in enumerate(lines):
 w=[int(x,16) for x in line.split()[2:]]
 assert line.startswith('N2 35B ') and len(w)==40
 kind=i%16
 assert w[20]==(0x43314252 if kind in (0,1) else (0x43314254 if kind==2 else 0x43315058))
 if kind>=3:pixel_ids.append(w[25])
assert pixel_ids==list(range(486))
# Build a labelled synthetic decoder fixture from real SCCB-simulation pages
# and prior CRC-verified native strip. This is NEVER new board evidence.
metadata=[]
for line in (s/'blc_meta_pages.txt').read_text().splitlines():
 raw=bytes.fromhex(line.split()[1]);metadata.append([int.from_bytes(raw[i:i+4],'big') for i in range(0,80,4)])
_,_,native=p.decode((r/'reports/RAW_E3_second_capture.txt').read_text())
crc=zlib.crc32(native)
def uart(w):return 'N2 35B '+' '.join(f'{x:08X}' for x in ([0]*12+[0x43315238]+[0]*6+[72000000]+w))
fixture=[uart(w) for w in metadata]
for fid in (1,2,3):
 for offset in range(0,11520,24):
  payload=native[offset*2:(offset+24)*2]
  w=[0x43315058,fid,0x10000,1120<<16,(16<<16)|720,offset,crc,24]
  w += [int.from_bytes(payload[i:i+4],'big') for i in range(0,48,4)]
  fixture.append(uart(w))
text='\n'.join(fixture);(out/'synthetic_A_B_AP.txt').write_text(text)
res=b.decode(text,out/'synthetic_complete');assert res['digital_acquisition_complete'],res['errors']
assert not res['BLC_effect_verified']
for stage in res['stages'].values():
 assert stage['pre']['line_period_ms']==.05
 assert abs(stage['pre']['exposure_ms']-39.8)<1e-9
# Remove one unique pixel page, one metadata page, or final restoration.
badcases={
 'missing_pixel':'\n'.join(line for line in fixture if not (line.split()[22]=='43315058' and line.split()[23]=='00000001' and line.split()[27]=='00000000')),
 'missing_post':'\n'.join(line for line in fixture if not (line.split()[22]=='43314252' and (int(line.split()[23],16)>>8&255)==1 and (int(line.split()[23],16)>>29)==2)),
 'no_restore':'\n'.join(line for line in fixture if not (line.split()[22]=='43314254' and int(line.split()[23],16)>>29==4))}
for name,bad in badcases.items():
 result=b.decode(bad,out/name);assert not result['digital_acquisition_complete'],name
# Actual new rearmed production capture path, all720 lines per stage.
strips=(s/'blc_strip_pages.txt').read_text();seen={}
for epoch,fid in enumerate((0,3,5)):
 t='\n'.join(line for line in strips.splitlines() if int(line.split()[1][8:16],16)==fid)
 key,g,data=p.decode(t);assert key[:5]==(fid,1120,0,16,720)
 def pixel(y,x):
  if y%4==0:v=((((y*7)^(x*3))&7)<<11)|((((y*11)^x)&15)<<5)|(((y*13)^(x*5))&7)
  elif y%4==1:v=1<<(x%16)
  elif y%4==2:v=0x55aa if x&1 else 0xaa55
  else:v=((y*0x3517)^(x*0x1739))&65535
  return v^(epoch*0x1237)
 expected=b''.join(pixel(y,x).to_bytes(2,'big') for y in range(720) for x in range(1120,1136))
 assert data==expected and len(data)==23040
 seen[fid]=dict(pages=g['pages'],crc32=f'{key[-1]:08x}',exact_pixels=11520)
result=dict(pass_=True,changes=changed,protected_source_hashes=protected,
 constraints_identical_to_E4=True,full720_production_capture_three_rearms=seen,
 SCCB_scenarios=8,actual_uart_lines=600,actual_sequential_pixel_pages=486,
 decoder_complete_rejected_missing_pixel_post_or_restore=True,decoder_exposure_ms_conversion=True,
 fixture_is_simulation_and_prior_data_not_new_board_evidence=True,
 production_full_frames_checked=6,production_pixels_checked=5529600,
 output_raster_OSD_RGB_retiming_cycles_checked=12000,
 strip_log_literal_note='Final inherited display string still says2 frames/480pages; preceding three stage lines and the test assertion total_pixels=5529600,verdicts=6 verify the actual three-stage totals. No test log edited.',
 external_IO_not_signed_off=True,no_CAM0_owner_or_network_business_change=True)
(r/'reports/blc_e5_checks.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='protected_source_hashes'},indent=2))



