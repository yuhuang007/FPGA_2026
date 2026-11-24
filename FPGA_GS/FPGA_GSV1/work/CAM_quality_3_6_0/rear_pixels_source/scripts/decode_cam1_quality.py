"""C1Q1 gain contrast page; use measured row period, not assumed exposure ms."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ADDRESSES = [0x300a,0x300b,0x303a,0x303b,0x303c,0x303d,
 0x3500,0x3501,0x3502,0x3500,0x3501,0x3503,
 0x350a,0x350b,0x350a,0x350b,0x380c,0x380d,0x380e,0x380f,
 0x3a00,0x3a05,0x3a02,0x3a03,0x3a14,0x3a15,0x3a18,0x3a19,
 0x3a08,0x3a09,0x3a0a,0x3a0b,0x3c00,0x3c01,0x3c0c,
 0x4000,0x4001,0x4002,0x4003,0x4004,0x4005,0x4009,0x503d,0x5308]
p = argparse.ArgumentParser()
p.add_argument('capture', type=Path)
p.add_argument('--output', type=Path)
a = p.parse_args()
snapshots=[]
for line in a.capture.read_text(encoding='utf-8-sig').splitlines():
    if not line.startswith('N2 35O '):
        continue
    try:
        w=[int(v,16) for v in line.split()[2:]]
    except ValueError:
        continue
    if len(w)!=40 or w[12]!=0x43315238 or w[20]!=0x43315131:
        continue
    flags=w[21]
    b=b''.join(v.to_bytes(4,'big') for v in w[29:40])
    word=lambda i: int.from_bytes(b[i:i+2],'big')
    exp=lambda v: (v&0xfffff)/16
    row_ms=(w[25]>>16)*0.00002  # direct physical row spacing,50MHz reference
    coherent=b[6:8]==b[9:11] and b[12:14]==b[14:16]
    snapshots.append(dict(phase=flags>>28, failed=bool(flags&(1<<27)),
        valid=bool(flags&(1<<26)),timeout=bool(flags&(1<<25)),
        error_code=(flags>>20)&15,nacks=(flags>>16)&15,
        sequence=(flags>>8)&255,read_errors=flags&255,
        front_capture_good=w[25]&65535,front_published=w[28]>>16,
        front_displayed=w[28]&65535,
        row_ms=row_ms,baseline_ms=w[26],sweep_ms=w[27],reference_ms=w[18],
        baseline_exposure_ms=exp(w[22]>>8)*row_ms if w[26] else None,
        baseline_gain_x=((w[23]>>16)&1023)/16 if w[26] else None,
        baseline_gain_ceiling_x=(w[23]&1023)/16 if w[26] else None,
        target_ceiling_x=(w[24]>>16)/16,coherent=coherent,
        sensor_id=f'{word(0):04X}',
        exposure_ms=exp(int.from_bytes(b[6:9],'big'))*row_ms,
        gain_x=(word(12)&1023)/16,manual=b[11],
        HTS=word(16),VTS=word(18),gain_ceiling_x=(word(26)&1023)/16,
        exposure_ceiling_50_ms=word(22)*row_ms,exposure_ceiling_60_ms=word(24)*row_ms,
        inferred_SYSCLK_Hz=word(16)/(row_ms/1000) if row_ms else None,
        night_mode=bool(b[20]&4),frame_insertion=bool(b[21]&64),
        BLC={f'{ADDRESSES[i]:04X}':f'{b[i]:02X}' for i in range(35,42)},
        registers=[dict(address=f'{addr:04X}',value=f'{v:02X}') for addr,v in zip(ADDRESSES,b)]))
rate=subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).with_name('decode_cam1_rate.py')),
                     str(a.capture)],capture_output=True,text=True,encoding='utf-8')
if rate.returncode not in (0,2):
    raise RuntimeError(rate.stderr)
result=dict(tag='C1Q1',records=len(snapshots),snapshots=snapshots,
            rear_rates=json.loads(rate.stdout),image_quality_verified=False,
            notes=['This CAM1 candidate exports one C1Q1 page; CAM0 register polling is omitted to reduce passive logic. CAM0 frame counts and C1R8 rates remain.',
                   'Baseline and current exposure use the same measured row period; this profile never changes timing.',
                   'Readback is a short SCCB sweep with repeated exposure/gain checks, not a frame-synchronous AE latch.',
                   'Phase2 means ceiling registers verified; green-line benefit/brightness tradeoff require human comparison.'])
good=[s for s in snapshots if s['valid'] and s['coherent'] and s['row_ms']>0 and s['sensor_id']=='3660']
result['completed']=len(good)>=2 and result['rear_rates']['completed']
result['ceiling_applied_verified']=any(s['phase']==2 and not s['failed'] and
    s['gain_ceiling_x']==s['target_ceiling_x'] and s['manual']&3==0 for s in good)
if len(snapshots)>=2:
    first,last=snapshots[0],snapshots[-1]
    dt=((last['reference_ms']-first['reference_ms'])&0xffffffff)/1000
    if dt>0:
        result['front_rates']=dict(reference_seconds=dt,capture_bad_delta=None,
            note='CAM0 register readback/bad count unavailable in this CAM1-only diagnostic page; do not infer zero.',
            **{key+'_fps':((last[key]-first[key])&65535)/dt for key in
               ('front_capture_good','front_published','front_displayed')})
out=json.dumps(result,ensure_ascii=False,indent=2)
if a.output:
    a.output.write_text(out+'\n',encoding='utf-8')
print(out)
raise SystemExit(0 if result['completed'] else 2)
