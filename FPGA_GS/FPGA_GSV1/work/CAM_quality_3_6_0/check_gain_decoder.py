import json
import subprocess
import sys
import tempfile
from pathlib import Path
r=Path(__file__).resolve().parent
rows=[]
for i in range(3):
    w=[0]*40
    w[12]=0x43315238;w[13]=921600;w[14]=(1<<26)|720
    w[15]=100+i*50;w[16]=10000+i*2000
    w[17]=((100+i*50)<<16)|(100+i*50);w[18]=10000+i*2000;w[19]=72000000
    w[20]=0x43315131;w[21]=0x24000000|((10+i)<<8)
    w[22]=(0x31c0<<8);w[23]=(248<<16)|248;w[24]=128<<16
    w[25]=2500<<16;w[26]=20000;w[27]=20000+i*2000
    b=bytearray(44);b[0:2]=bytes.fromhex('3660');b[6:11]=bytes.fromhex('0031c00031')
    b[12:16]=bytes.fromhex('00800080');b[16:20]=bytes.fromhex('07080320')
    b[22:28]=bytes.fromhex('031c031c0080')
    for n in range(11):w[29+n]=int.from_bytes(b[n*4:n*4+4],'big')
    rows.append('N2 35O '+' '.join(f'{v:08x}' for v in w))
with tempfile.TemporaryDirectory() as temp:
    p=Path(temp)/'synthetic.txt';p.write_text('\n'.join(rows)+'\n')
    command=[sys.executable,'-X','utf8',str(r/'rear_gain_source/scripts/decode_cam1_quality.py'),str(p)]
    check=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
    assert check.returncode==0,check.stderr or check.stdout
    result=json.loads(check.stdout)
    assert result['completed'] and result['ceiling_applied_verified']
    assert result['rear_rates']['capture_fps']==25
    for s in result['snapshots']:
        assert abs(s['exposure_ms']-39.8)<1e-9 and s['gain_x']==8
        assert s['baseline_gain_x']==15.5 and abs(s['baseline_exposure_ms']-39.8)<1e-9
        assert s['inferred_SYSCLK_Hz']==36000000
    p.write_text(rows[0]+'\n')
    assert subprocess.run(command,capture_output=True).returncode==2
out=dict(pass_status=True,source='synthetic test only; not hardware',
         checks=['C1Q1 header/byte order','measured50us rows ->39.8ms','15.5x baseline/8x applied',
                 'SYSCLK36MHz','25fps with2s page gaps','single-record rejection'])
(r/'reports/gain_decoder_checks.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
