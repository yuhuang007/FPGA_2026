from datetime import datetime
from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parent
p=r/'reports'
d=json.loads((p/'GAIN8_after_cover_decode.json').read_text(encoding='utf-8'))
s=d['snapshots']
videos=[Path('E:/系统软件/下载/c82896c619f04fc09964f9799b989464.mp4'),
        Path('E:/系统软件/下载/452f27d2d5a62ecdcc1fa2f7f8520b5d.mp4')]
result=dict(timestamp=datetime.now().astimezone().isoformat(),
 user_confirmed='黑底仍有成排绿线',
 videos=[dict(path=str(v),sha256=hashlib.sha256(v.read_bytes()).hexdigest()) for v in videos],
 extracted_frames=['covered_video/contact.png','covered_video2/contact.png'],
 visible_observations=['Thin red/purple and green horizontal streaks change across recorded frames.',
                       'Yellow OSD remains legible/stable in these filmed views.',
                       'No claim of full-frame block/address corruption is made from these filmed views.'],
 serial_after_cover_report=dict(file='GAIN8_after_cover_uart.txt',decode='GAIN8_after_cover_decode.json',
   window_seconds=8,capture_fps=d['rear_rates']['capture_fps'],
   ddr_publish_fps=d['rear_rates']['ddr_publish_fps'],display_new_fps=d['rear_rates']['display_new_fps'],
   bad_delta=d['rear_rates']['capture_bad_delta'],
   exposure_ms=[min(a['exposure_ms'] for a in s),max(a['exposure_ms'] for a in s)],
   gain_x=[min(a['gain_x'] for a in s),max(a['gain_x'] for a in s)],
   simultaneous_with_video=False,physical_cover_during_uart_read='Not independently confirmed'),
 conclusions=['Environment light bands alone do not explain the user-confirmed persistence with the lens fully covered.',
              'Gain8 was not binding in the earlier live scene; it is binding in this later8s readback. Do not conflate these scenes.',
              'Valid geometry/rates do not establish pixel-content correctness.',
              'Reference OV3660 BLC auto+continuous-update and rotation compensation match the archived driver; no erroneous BLC register established.',
              'Need lossless pre-DDR source pixels to separate an upstream defect from DDR/display/filming effects.'],
 sensor_isp_vs_dvp_sampling_root_confirmed=False,
 next_candidate='CAM1_RAW_E3_3_6_0: one accepted native16x720 strip x1120; same full720 video remains live; whole-strip CRC and repeated UART pages.',
 next_candidate_sensor_settings='R0 original OV3660 table/gain ceiling15.5x; no new sensor writes; GAIN8 experiment not promoted.',
 camera_front_full_path_check=dict(log='cam0_front30_corrected.log',pass_=False,
   result='4 DDR publications with consecutive30fps before deliberate bad-frame drop; final geometry totals4good/2bad disagree with fixture expectation5good/1bad.',
   next='Instrument individual frame verdicts and resolve startup/monitor counting before front candidate. No full front build launched.'),
 pi_live_started=False,auto_programmed=False)
(p/'dark_video_findings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state=json.loads((p/'continuation_state.json').read_text(encoding='utf-8'))
state.update(Timestamp=result['timestamp'],User='Covered lens retains coloured horizontal streaks; two videos reviewed',
 FrontFullPixelTest=result['camera_front_full_path_check'],
 RearRawBuildSession=57625,RearRawBranch='rear_pixels_source',
 Awaiting='One RAW E3 build after actual-DRM/native720/CRC/production UART checks; no blind sensor changes. Not yet a delivered bitstream.',
 LatestEvidence='reports/dark_video_findings.json')
(p/'continuation_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Saved dark-video evidence and actual8s readback; no quality repair claimed.')
