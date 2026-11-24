"""Source/device-reference audit. No build, hardware IO, register writes or source edits."""
from pathlib import Path
import hashlib,json,re,importlib.util,statistics
r=Path(__file__).resolve().parent;root=r.parents[1]
src=root/'release/FPGA_GSV1_CAM1_RAW_E3_3_6_0/source'
ref=root/'release/FPGA_GSV1_CAM1_OV3660_3_5_8_ROTATE25_CANDIDATE/reports/sources'
old=root/'release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/source'
build=r/'rear_pixels_source/build/CAM1_RAW_E3_3_6_0_20261024_203852_117'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
txt=lambda p:p.read_text(encoding='utf-8-sig',errors='replace')
table=txt(src/'rtl/capture/cam_ov3660_table.v')
entries=[]
for line in table.splitlines():
 m=re.search(r"9'd(\d+):entry=(.*?);",line)
 if m:
  choices=re.findall(r"24'h([0-9a-fA-F]{6})",m[2]);v=int(choices[0],16)
  entries.append((int(m[1]),v>>8,v&255,line))
assert [x[0] for x in entries]==list(range(248))
regs=txt(ref/'sensors_private_include_ov3660_regs.h')
names={k:int(v,16) for k,v in re.findall(r'#define\s+(\w+)\s+(0x[0-9a-fA-F]+)',regs)};names['REG_DLY']=65535
settings=txt(ref/'sensors_private_include_ov3660_settings.h')
block=re.sub(r'//[^\n]*','',settings.split('sensor_default_regs[][2] = {')[1].split('};')[0])
reference=[]
for a,v in re.findall(r'\{\s*(\w+)\s*,\s*(0x[0-9a-fA-F]+|\d+)\s*\}',block):
 if a=='REGLIST_TAIL':break
 address=int(a,16) if a.startswith('0x') else names[a];value=int(v,0)
 if (address,value)==(0x3008,2):continue
 if address==65535:value=100
 reference.append((address,value))
assert [(a,v) for _,a,v,_ in entries[:len(reference)]]==reference
history={}
for i,a,v,_ in entries:history.setdefault(a,[]).append(dict(index=i,value=f'{v:02x}'))
final={a:int(h[-1]['value'],16) for a,h in history.items()}
word=lambda a:final[a]*256+final[a+1]
expected={0x3820:0x46,0x3821:6,0x4514:0xbb,0x4520:0xb0,0x3814:0x11,0x3815:0x11,
 0x5001:0x83,0x501f:1,0x4300:0x61,0x4002:0xc5,0x4003:0x81,0x4005:0x12,
 0x3503:0,0x3a00:0x3a,0x3a05:0x30,0x3a18:0,0x3a19:0xf8,0x4740:0x20}
assert all(final[a]==v for a,v in expected.items())
config=txt(src/'rtl/capture/cam_ov3660_config.v')
verify_block=config.split('function [23:0] expected;')[1].split('endfunction')[0]
verified={int(v,16)>>8 for v in re.findall(r"24'h([0-9a-fA-F]{6})",verify_block)}
fdc=txt(src/'constraints/mes50hp.fdc')
assert not re.search(r'^\s*set_input_delay',fdc,re.M)
protected=['rtl/capture/cam_ov3660_table.v','rtl/capture/cam_ov3660_config.v',
 'rtl/capture/cam3660_dvp.v','rtl/capture/capture_pipe.v','rtl/reuse/video_capture_status.v',
 'constraints/mes50hp.fdc','rtl/reuse/fram_buf.v','rtl/frame/m3_front_owner.v']
for rel in protected:assert sha(src/rel)==sha(old/rel)==sha(build/rel),rel
reference_hashes=[]
for m in json.loads(txt(ref/'manifest.json')):
 p=ref/Path(m['file']).name
 assert sha(p)==m['sha256'],p
 reference_hashes.append(dict(file=str(p),sha256=sha(p),url=m['url']))
# Independently decode and compare the new stable-digital, full-production path fixture.
sp=importlib.util.spec_from_file_location('decoder',src/'scripts/decode_cam1_patch.py')
decoder=importlib.util.module_from_spec(sp);sp.loader.exec_module(decoder)
key,g,raw=decoder.decode(txt(r/'reports/audit_cam1_preddr_pages.txt'))
def oracle(y,x):
 if y%4==0:return ((((y*7)^(x*3))&7)<<11)|((((y*11)^x)&15)<<5)|(((y*13)^(x*5))&7)
 if y%4==1:return 1<<(x%16)
 if y%4==2:return 0x55aa if x%2 else 0xaa55
 return ((y*0x3517)^(x*0x1739))&65535
want=b''.join(oracle(y,x).to_bytes(2,'big') for y in range(720) for x in range(1120,1136))
assert raw==want
blc_current=txt(r/'reports/GAIN8_actual_decode.json')
oldread=json.loads(blc_current)['snapshots'][0]
result=dict(audited_production_source=str(src),routed_build=str(build),
 production_files_identical_to_R0_and_routed_build={rel:sha(src/rel) for rel in protected},
 reference_sources=reference_hashes,
 datasheet=dict(file=str(ref/'OV3660_datasheet.txt'),sha256=sha(ref/'OV3660_datasheet.txt'),
 url='https://media.ic-find.com/datasheets/4666f79f51fd79b7cecae867005c0723.pdf',version='PRELIMINARY1.3 2011-05-13',
 relevant_sections=['2.7/table2-4 RGB565','figure2-7/tables2-8/2-9 PLL','3.1/table3-1 rotation',
 '3.2/figure3-3 window','3.5/table3-7 and7.13/table7-13 BLC','5.2/table5-3 DVP frame timing','8.3/table8-3 voltage','8.4/table8-4 clocks']),
 table_entry_count=len(entries),reference_prefix_entries=len(reference),reference_prefix_exact=True,
 sequence=dict(reset_and_enable_wait_ms=[100,100],critical_readback_register_count=45,
 all_writes_check_ack=True,stops_on_verify_failure=True,no_runtime_camera_writer_in_E3=True,
 writes_to_overridden_registers={f'{a:04x}':h for a,h in history.items() if len(h)>1}),
 geometry=dict(start=[word(0x3800),word(0x3802)],end_inclusive=[word(0x3804),word(0x3806)],
 sensor_window=[word(0x3804)-word(0x3800)+1,word(0x3806)-word(0x3802)+1],
 offset=[word(0x3810),word(0x3812)],output=[word(0x3808),word(0x380a)],
 scale=False,binning=False,HTS=word(0x380c),VTS=word(0x380e),
 crop_formula_verified=(word(0x3804)-word(0x3800)+1-2*word(0x3810)==1280 and word(0x3806)-word(0x3802)+1-2*word(0x3812)==720)),
 final_registers={f'{a:04x}':f'{v:02x}' for a,v in expected.items()},
 black_level=dict(explicit_writes={'4002':'C5','4003':'81','4005':'12'},
 reset_defaults_not_written={'4000':'0D','4001':'04','4004':'08','4006':'08','4007':'00','4009':'10'},
 historical_GAIN8_readback=oldread['BLC'],
 historical_readback_not_simultaneous_E3=True,
 unverified_current=['4000','4001','4002','4003','4004','4005','4006','4007','4009','402c..4033'],
 interpretation=['4000 bit0 enabled;0D BGR compensation and apply selection preserved',
 '4002=C5: format-change update enabled,auto enabled,5 reset frames',
 '4003=81: redo requested,freeze bit6 clear,manual frame count1',
 '4005=12: always-update bit1 set; reserved bits preserved from reference',
 '4001 reset4 and4004 reset8: start line and processed count; relation to cropped physical start408 not specified in available documentation',
 '4007 window selection exists but was not included in historical readback; no evidence it differs from reset00'],
 confirmed_mismatch=False),
 clock=dict(xclk_nominal_hz=24000000,xclk_directly_measured=False,sysclk_calculated_hz=36000000,
 byte_pclk_calculated_hz=72000000,pixel_clock_hz=36000000,row_us=50.0,frame_ms=40.0,fps=25,
 active_bytes=2560,available_byte_cycles_per_row=3600,ae_max_lines=796,ae_max_ms=39.8,
 band50_lines=200,band60_lines=166,ae_gain_ceiling_x=15.5),
 ISP=dict(reference_defaults_retained=True,values={'5000':'A7','5001':'83','501f':'01','4300':'61'},
 note='No documented enabled temporal filter/frame memory found; this is not proof that undocumented sensor internals cannot contribute.'),
 input_path=dict(edge='posedge cmos2_pclk for data/HREF/VS; matching one-byte top staging',
 first_register_type='gopQ in CLB; cmos2_d_d0[0] is CLMA_154_77',
 camera_input_register_constraint=False,non_dedicated_clock_route_allowed=True,
 data_pad_standard='LVCMOS12',sync_clock_pad_standard='LVCMOS33',bank_VCCIO=3.3,
 adapter_DOVDD_schematic_nominal=2.8,actual_module_and_waveform_unknown=True,
 cmos2_period_constraint_ns=11.9,observed_nominal_period_ns=1000/72,
 set_input_delay_present=False,
 sample_clock_arrival_ns_from_existing_min_paths={'fast':3.514,'slow':5.553},
 note='These are modeled clock insertion values on an internal FF->FF path, not input-data slack or a full min/max external eye.',
 source_clock_false_group='byte and /2 domains separately asynchronous; tuple RAM pointer CDC intended; bundled descriptor/data held after freeze',
 unavailable_to_signoff=['sensor PCLK-to-data min/max and relation at FPGA pads','actual PCB/FFC data vs clock skew','first-FF data arrival and threshold effects']),
 digital_path=dict(full_dimensions=[1280,720],source_frames_checked=2,production_pixels_checked=1843200,
 exported_pixels_checked=11520,unique_pages=480,whole_crc=f'{key[5]:08x}',
 exact_independent_oracle=True,tested_patterns=['dark row chroma','walking16bits','55aa-aa55','row/column mixed words'],
 analog_pad_timing_covered=False,existing_reject_recovery_checks_reused=True,
 code_findings=['high byte first; pair state reset during VS or outside HREF; odd byte and overflow reject closing frame',
 'VS/DE/RGB moved in one19-bit FIFO tuple; no independent synchronization of RGB bits',
 'capture_pipe delays RGB/DE/VS and opening ID together by2 cycles',
 'strip writes same cap_rgb1/cap_de1/cap_vs1 tuple as production DDR writer',
 'same-domain strip write and address count; no new video-domain sampling clock',
 '8banks of2048 words,11520 words used; last bank5/address1279; no wrap-overflow',
 'descriptor and RAM held frozen before sysclk reads; actual synchronous DRM read latency accounted'],
 limits=['Stable digital stimulus cannot establish analogue setup/hold or eliminate silicon CDC metastability.',
 'Existing internal STA excludes unconstrained pad->firstFF external requirements.']),
 recommendation='No justified sensor-register repair found. One passive receive-end CAM1 DVP timing/level measurement before any further bitstream.',
 no_production_source_changed=True,no_build=True,no_serial_read=True,no_programming=True,no_pi_activity=True)
(r/'reports/CAM1_source_device_audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(dict(reference_prefix_entries=len(reference),protected_source_hashes_match=True,
 config_entries=len(entries),critical_readback_registers=len(verified),geometry=result['geometry'],
 new_production_path_oracle_pass=True,export_crc=f'{key[5]:08x}',confirmed_register_mismatch=False),indent=2))
