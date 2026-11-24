"""Record actual GAIN8 feedback without promoting it to a quality repair."""
from datetime import datetime
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
reports = root / 'reports'
d = json.loads((reports / 'GAIN8_actual_decode.json').read_text(encoding='utf-8'))
s = d['snapshots']
r = {k: v for k, v in d['rear_rates'].items() if k != 'snapshots'}
assert d['completed'] and d['ceiling_applied_verified']
assert all(x['sensor_id'] == '3660' and x['phase'] == 2 and x['valid']
           and not x['failed'] and not x['read_errors'] and not x['nacks']
           and x['coherent'] and x['gain_ceiling_x'] == 8 for x in s)
assert max(x['gain_x'] for x in s) < 8

result = dict(
    timestamp=datetime.now().astimezone().isoformat(),
    current_board='User-confirmed GAIN8 E2; C1Q1 applied-phase readback verified',
    user_feedback='GAIN8已下载，后摄还是有绿线，并且显示画面的效果还不如前摄清晰',
    quality_accepted=False, green_line_fixed=False,
    current_exposure_ms_range=[min(x['exposure_ms'] for x in s), max(x['exposure_ms'] for x in s)],
    current_gain_x_range=[min(x['gain_x'] for x in s), max(x['gain_x'] for x in s)],
    saved_pre_apply_gain_x=s[0]['baseline_gain_x'],
    saved_pre_apply_ceiling_x=s[0]['baseline_gain_ceiling_x'],
    verified_ceiling_x=8, HTS=s[0]['HTS'], VTS=s[0]['VTS'],
    rear_rates=r, front_rates=d['front_rates'],
    source_uart='GAIN8_actual_uart.txt', decoded='GAIN8_actual_decode.json',
    uart_sha256=hashlib.sha256((reports/'GAIN8_actual_uart.txt').read_bytes()).hexdigest(),
    confirmed=[
        'Gain-ceiling write/readback succeeded; no SCCB errors in these records.',
        'Observed gain is below both the original15.5x and the new8x limits.',
        'The8x limit is not binding in this observed scene; reducing it did not demonstrate a green-line benefit.',
        'CAM1 retains25fps capture/publish/new-display and valid720x1280 geometry in this12s window.',
        'User reports rear clarity below front clarity; no controlled static-text or digital-pixel comparison yet.'
    ],
    not_confirmed=[
        'Low-light gain itself is not ruled out as a noise amplifier, but excessive gain ceiling is not a demonstrated cause.',
        'The2.5-2.75x versus saved3.25x difference is not attributed to a non-binding ceiling; scene/AE evolution is uncontrolled.',
        'Clean bars and valid geometry do not rule out data-dependent DVP errors.',
        'Lighting banding, sensor/ISP dark-row noise, optics/focus and data-dependent capture faults remain distinguishable hypotheses.',
        'A photographed screen is not a raw CAM1 frame. No CAM1 digital frame export exists in the current production protocol.',
        'Comparison with CAM0 is not proof that GAIN8 reduced rear clarity relative to its own prior baseline.'
    ],
    actions=dict(no_new_rear_register_change=True, no_new_build=True,
                 no_pi_live=True, no_auto_programming=True,
                 next_user_observation='One5s fully-covered rear-lens observation: dark-field line persistence versus lighting dependence.',
                 independent_front_check='Corrected full720 production-path fixture running; not yet PASS, not in GAIN8.'),
    rollback='release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK_HDMI_1080P60.sbit'
)
(reports/'GAIN8_findings.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state=json.loads((reports/'continuation_state.json').read_text(encoding='utf-8-sig'))
state.update(Timestamp=result['timestamp'], CurrentBoard=result['current_board'],
             Gain8Findings='reports/GAIN8_findings.json', RearGainQualityAccepted=False,
             FrontFullPixelTest='Corrected fixture running, session6863; do not call PASS until exit0 and final oracle totals checked.',
             Awaiting='Single covered-lens observation; no further rear gain/ISP/clock sweep. No Pi LIVE. Keep current board for comparison.')
(reports/'continuation_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ('quality_accepted','current_exposure_ms_range','current_gain_x_range','saved_pre_apply_gain_x','verified_ceiling_x')},ensure_ascii=False,indent=2))
