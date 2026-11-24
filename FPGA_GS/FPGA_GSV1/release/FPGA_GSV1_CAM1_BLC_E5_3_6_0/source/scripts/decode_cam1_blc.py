"""E5 A/B/A-prime evidence, not an automatic camera-quality verdict.
Native data are one 16x720 RGB565 strip before DDR, not sensor Bayer RAW.
"""
import argparse,csv,json,re,zlib
from pathlib import Path
import decode_cam1_patch as patch

ADDR=[0x300a,0x300b,0x3503,0x3500,0x3501,0x3502,0x350a,0x350b,0x3406,
      *range(0x3400,0x3406),*range(0x380c,0x3810),*range(0x303a,0x303e),
      0x4000,0x4001,0x4002,0x4003,0x4004,0x4005,0x4006,0x4007,0x4009,
      *range(0x402c,0x4034),0x4740,0x4300,0x5000,0x5001,0x3a00,0x503d,
      0x3820,0x3821,0x3509,0x3504,0x3505,0x3512,0x3513,0x350c,0x350d,0x3008]
NAMES={1:'A_update',2:'B_frozen',3:'Aprime_restored'}
def records(text):
    for line in text.splitlines():
        if not re.match(r'^N2 35B ',line):continue
        x=line.split()[2:]
        if len(x)!=40 or any(not re.fullmatch('[0-9a-fA-F]{8}',v) for v in x):continue
        yield line,[int(v,16) for v in x]

def parameters(raw,pclk_hz):
    d=dict(zip(ADDR,raw));hts=d[0x380c]*256+d[0x380d];vts=d[0x380e]*256+d[0x380f]
    exposure=((d[0x3500]&15)<<16)|(d[0x3501]<<8)|d[0x3502]
    gain=((d[0x350a]&3)<<8)|d[0x350b]
    # In the inherited 720p25 configuration, one timing count consumes TWO
    # DVP byte cycles. Do not apply this conversion to a different PLL mode.
    mode_ok=bytes(d[a] for a in range(0x303a,0x303e))==bytes([0,0x18,0x12,0x20])
    # Preserve raw values even if this optional conversion is unavailable.
    line_ms=2000*hts/pclk_hz if pclk_hz and mode_ok else None
    return dict(registers={f'{a:04X}':f'{d[a]:02X}' for a in ADDR},
        exposure_raw_1_16_line=exposure,exposure_lines=exposure/16,
        exposure_ms=exposure/16*line_ms if line_ms else None,
        pclk_hz=pclk_hz,timing_conversion_verified_for_this_pll=mode_ok,
        line_period_ms=line_ms,HTS=hts,VTS=vts,gain_raw=gain,gain_x=gain/16,
        BLC_coeff_raw_hex=[f'{d[a]*256+d[a+1]:04X}' for a in range(0x402c,0x4034,2)],
        BLC_coeff_note='RW; datasheet: with 3 decimal. Numeric scale/sign not used for judgement; multi-byte reads not atomic during update.')

def decode(text,dest):
    dest.mkdir(parents=True,exist_ok=True)
    regs={};statuses=[];pixels=[];rate_pclks=[];errors=[]
    for line,w in records(text):
        if w[12]==0x43315238 and w[19]>0:rate_pclks.append(w[19])
        p=w[20:];tag=p[0];phase=p[1]>>29;flags=p[1]>>16&255
        if tag==0x43314252:
            kind=p[1]>>8&255
            raw=b''.join(v.to_bytes(4,'big') for v in p[6:])
            if len(raw)!=56 or zlib.crc32(raw)!=p[5]:raise ValueError('Register page CRC failure')
            key=(phase,kind,p[2]);value=dict(start_ms=p[3],end_ms=p[4],crc=f'{p[5]:08x}',raw=raw)
            if key in regs and regs[key]!=value:raise ValueError('Conflicting same-stage register page')
            regs[key]=value
        elif tag==0x43314254:
            statuses.append(dict(phase=phase,flags=flags,error=p[1]>>8&255,sample_id=p[2],
                ms=p[3],bracket_source_frame_tags=p[4:8],pre_crc=f'{p[8]:08x}',post_crc=f'{p[9]:08x}',
                original_operating_controls=p[10],restored_readback_controls=p[11],completed_mask=p[12]&7))
        elif tag==0x43315058:pixels.append((p[1],line))
    pclk=sorted(rate_pclks)[len(rate_pclks)//2] if rate_pclks else None
    stages={};raw_by_phase={}
    for phase,name in NAMES.items():
        matches=[k for k in regs if k[0]==phase and k[1]==0]
        if len(matches)!=1:errors.append(f'{name}: missing or ambiguous PRE');continue
        _,_,fid=matches[0];a=regs[(phase,0,fid)];b=regs.get((phase,1,fid))
        if b is None:errors.append(f'{name}: missing POST');continue
        raw_by_phase[phase]=(a['raw'],b['raw'])
        bracket=[s for s in statuses if s['phase']==phase and s['sample_id']==fid
                 and s['pre_crc']==a['crc'] and s['post_crc']==b['crc']
                 and s['completed_mask']&(1<<(phase-1)) and s['flags']&2]
        if not bracket:errors.append(f'{name}: missing matching sample/CRC/frame-bracket status')
        group='\n'.join(line for f,line in pixels if f==fid)
        try:key,g,data=patch.decode(group)
        except ValueError as e:errors.append(f'{name}: {e}');continue
        image=patch.write_result(key,g,data,dest/name)
        image['no_sensor_register_writes']=False
        image['experiment']='One bitwise-preserving controlled BLC freeze/restore; fixed exposure/gain/WB shared by A/B/Aprime.'
        (dest/name/'result.json').write_text(json.dumps(image,indent=2))
        rows=json.loads((dest/name/'row_rgb.json').read_text())
        decoded=[int.from_bytes(data[i:i+2],'big') for i in range(0,len(data),2)]
        for y,row in enumerate(rows):
            v=decoded[y*16:(y+1)*16]
            channels=[[((p>>11)&31)*255/31 for p in v],
                      [((p>>5)&63)*255/63 for p in v],[(p&31)*255/31 for p in v]]
            for c,vals in zip('RGB',channels):
                m=sum(vals)/len(vals);row[c+'_within_row_stddev']=(sum((n-m)**2 for n in vals)/len(vals))**.5
            for bit in range(16):row[f'bit{bit}_ones']=sum((n>>bit)&1 for n in v)
        mean={c:sum(v[c] for v in rows)/len(rows) for c in 'RGB'}
        sd={c:(sum((v[c]-mean[c])**2 for v in rows)/len(rows))**.5 for c in 'RGB'}
        with (dest/name/'rows.csv').open('w',newline='') as f:
            wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
        stages[name]=dict(frame_id=fid,strip=image,row_mean=mean,row_mean_stddev=sd,
            frame_bracketing_status=bracket[-1] if bracket else None,
            pre=dict(**{k:v for k,v in a.items() if k!='raw'},**parameters(a['raw'],pclk)),
            post=dict(**{k:v for k,v in b.items() if k!='raw'},**parameters(b['raw'],pclk)))
    protected=[i for i,a in enumerate(ADDR) if a not in (0x4003,0x4005) and not 0x402c<=a<=0x4033]
    if len(raw_by_phase)==3:
        baseline=raw_by_phase[1][0]
        for phase,pair in raw_by_phase.items():
            for raw in pair:
                if any(raw[i]!=baseline[i] for i in protected):errors.append(f'phase{phase}: shared parameter drift')
                if raw[2]&3!=3 or raw[8]&1!=1:errors.append(f'phase{phase}: exposure/gain/WB not fixed')
                if raw[26]&0x7f!=(baseline[26]&0x3f)|(0x40 if phase==2 else 0):errors.append(f'phase{phase}: freeze control wrong')
                if raw[28]!=(baseline[28]&0xfd if phase==2 else baseline[28]):errors.append(f'phase{phase}: always-update control wrong')
        if raw_by_phase[2][0][32:40]!=raw_by_phase[2][1][32:40]:errors.append('B frozen coefficients changed between PRE/POST')
        if not baseline[23]&1 or not baseline[28]&2 or baseline[26]&0x40:errors.append('A is not original enabled update state')
    done=[s for s in statuses if s['phase']==4 and s['completed_mask']==7 and s['flags']&8 and not s['flags']&16 and s['error']==0]
    if not done:errors.append('Missing verified DONE/restore readback')
    else:
        d=done[-1];mask=0x7fffffff
        if d['original_operating_controls']&mask!=d['restored_readback_controls']&mask:errors.append('Final control restoration mismatch')
    if any(s['flags']&16 or s['phase']==5 for s in statuses):errors.append('Board reported INVALID')
    result=dict(digital_acquisition_complete=not errors and len(stages)==3,errors=errors,stages=stages,
        final_status=statuses[-1] if statuses else None,verified_done=done[-1] if done else None,
        visual_validity='Pending user confirmation: covered lens throughout; fixed-parameter A reproduces stripes; B not merely dark/black or desaturated.',
        decision_rules=['B attenuates stripes and Aprime returns: supports BLC update involvement, not a repair or unique cause.',
                        'B unchanged: lower BLC hypothesis priority; investigate sensor supply/readout and DVP.',
                        'Parameter drift, restore failure, A not reproducing, incomplete data: experiment invalid.'],
        limits=['Each image is one 16x720 pre-DDR RGB565 spatial strip, not a full image, Bayer RAW or continuous capture.',
                'Coefficient scans are time intervals bracketing capture; not atomic frame-associated values.',
                'Strip CRC proves exported integrity only. Pixel correctness and external DVP timing remain unverified.',
                'Native.png is unenhanced; horizontal_x16_preview.png repeats columns only.'],
        BLC_effect_verified=False)
    (dest/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',required=True,type=Path);args=p.parse_args()
    try:
        r=decode(args.input.read_text(encoding='utf-8-sig',errors='replace'),args.output)
        print(json.dumps({k:v for k,v in r.items() if k!='stages'},ensure_ascii=False,indent=2))
        raise SystemExit(0 if r['digital_acquisition_complete'] else 1)
    except ValueError as e:print('采样未完成:',e);raise SystemExit(1)


