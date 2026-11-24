from pathlib import Path
import json,hashlib,datetime,shutil
r=Path(__file__).resolve().parent
project=r.parents[1]
base=project/'release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/source'
motion=project/'release/FPGA_GSV1_CAM0_OV5640_3_5_9_MOTION_CANDIDATE/source'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected=['rtl/reuse/reg_config.v','rtl/reuse/i2c_com.v',
 'rtl/capture/cam_ov3660_table.v','rtl/capture/cam_ov3660_config.v',
 'rtl/capture/cam3660_dvp.v','rtl/frame/m3_front_owner.v',
 'rtl/network/m36_phy2.v','rtl/network/m364_e1_rgmii.v','constraints/mes50hp.fdc']
checks={p:sha(base/p)==sha(motion/p) for p in protected}
f=json.loads((r/'reports/cam0_baseline.json').read_text())
rear=json.loads((r/'reports/cam1_visible.json').read_text())
z=f['snapshots'][-1]
result=dict(
 timestamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
 user_confirmed_loaded='3.5.9-R0 READBACK; user path confirmation, not device SHA readback',
 user_confirmed_port='COM23',no_live_service_started=True,
 current_cam0=dict(reference_seconds=f['reference_window_seconds'],capture_fps=f['capture_fps'],
 publish_fps=f['ddr_publish_fps'],display_new_fps=f['display_new_fps'],bad_delta=f['capture_bad_delta'],
 read_errors_delta=f['read_errors_delta'],exposure_ms=z['exposure_ms'],gain_x=z['gain_x'],
 row_ms=z['row_period_ms'],hts=z['hts'],vts=z['vts'],night=z['night_mode'],extra_vts=z['extra_vts']),
 current_cam1=dict(reference_seconds=rear['reference_window_seconds'],capture_fps=rear['capture_fps'],
 publish_fps=rear['ddr_publish_fps'],display_new_fps=rear['display_new_fps'],
 bad_delta=rear['capture_bad_delta'],geometry_ok=rear['geometry_ok'],
 exposure_gain='UNKNOWN: R0 UART exports CAM0 registers only; CAM1 has startup verification, no periodic AE/AGC register sweep'),
 confirmed_front_bottleneck=dict(mechanism='verdict closes at next VS; DDR drain/reset/regrant misses SOF-only acceptance',
 proof='reports/cam0_turnover.log: same 6 complete720 frames, old3/new6; owner pin invariants checked',
 changed_branch='source/ only FRONT_BLANKING_GRANT wrapper and CAM0 instance',
 build_or_hardware_verified=False,network_slow_reader_may_still_cause_protected_frame_drops=True),
 archive_motion=dict(sha256='6fe75558add3378754c8113960f59051ebe401ed8d292723b7dde0b9b4eefe0f',
 reusable_sccb_and_profile=True,protected_source_comparison=checks,
 old_checks_reused='work/CAM0_motion/reports/ae_profile_tests.json and final_timing_resources.json',
 hardware_verified=False,selected_for_download=False,
 signal_budget_ratio=(9.99888*8)/(z['exposure_ms']*z['gain_x']),
 note='linear exposure*gain estimate only, not measured image brightness/noise. Do not apply10ms/8x as a guaranteed noise fix.'),
 rear_green_line=dict(user_reports_naked_eye=True,source_digital_frame_captured=False,
 capture_outlet_gap='existing production upload is CAM0 only; no CAM1 raw-frame output',
 next_candidate='rear_probe_source: OV3660 503D RMW+verify/exact restore, then known FPGA bars after DVP before DDR; no protocol changes',
 not_a_fix=True,limits='pattern outcome narrows stages; data-dependent DVP errors still possible when sensor bars appear clean'),
 unrelated_tests_not_rerun=True,auto_programmed=False)
(r/'reports/assessment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
photo_rows=[]
for name in ['微信图片_20261024185617_517_3.jpg','微信图片_20261024191554_518_3.jpg']:
 p=Path('E:/系统软件/下载')/name
 photo_rows.append(dict(original=str(p),bytes=p.stat().st_size,sha256=sha(p)))
(r/'reports/photos.json').write_text(json.dumps(photo_rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result['current_cam0'],ensure_ascii=False))
print(json.dumps(result['current_cam1'],ensure_ascii=False))
print('Archived profile protected sources identical:',all(checks.values()))
