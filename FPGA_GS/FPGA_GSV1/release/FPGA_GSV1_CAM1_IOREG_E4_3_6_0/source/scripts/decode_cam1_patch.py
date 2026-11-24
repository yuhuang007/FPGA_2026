"""Lossless native CAM1 pre-DDR strip. No network/Pi dependencies."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import zlib
from PIL import Image

def decode(text):
    groups={}
    for line in text.splitlines():
        if line.startswith('C1PX '):
            data=bytes.fromhex(line.split()[1])
            if len(data)!=80: raise ValueError('C1PX test page length')
            w=[int.from_bytes(data[i:i+4],'big') for i in range(0,80,4)]
        elif re.match(r'^N2 35[PI] ',line):
            words=line.split()[2:]
            if len(words)!=40 or any(not re.fullmatch('[0-9A-Fa-f]{8}',s) for s in words):
                continue # incomplete UART line is never accepted as pixel data
            w=[int(s,16) for s in words[20:]]
        else: continue
        if w[0]!=0x43315058: continue
        fid,flags=w[1:3];x,y=w[3]>>16,w[3]&65535
        width,height=w[4]>>16,w[4]&65535
        offset,crc,count=w[5:8]
        if flags>>16!=1 or not 0<count<=24 or offset%24 or offset+count>width*height:
            raise ValueError('Invalid/failing patch descriptor')
        key=(fid,x,y,width,height,crc)
        g=groups.setdefault(key,dict(pixels={},pages=0,rejected=flags>>8&255))
        payload=b''.join(n.to_bytes(4,'big') for n in w[8:])[:count*2]
        for i in range(count):
            n=offset+i;v=payload[i*2:i*2+2]
            if n in g['pixels'] and g['pixels'][n]!=v:
                raise ValueError('Conflicting same-frame pixel pages')
            g['pixels'][n]=v
        g['pages']+=1
    complete=[]
    for key,g in groups.items():
        fid,x,y,width,height,crc=key
        if len(g['pixels'])!=width*height: continue
        data=b''.join(g['pixels'][i] for i in range(width*height))
        actual=zlib.crc32(data)
        if actual!=crc: raise ValueError(f'Whole native strip CRC mismatch {actual:08x}!={crc:08x}')
        complete.append((key,g,data))
    if not complete:
        raise ValueError('采样未完成：没有同一完整帧、全部像素及CRC通过的C1PX结果；不得用缺页图判断绿线。'
                         f' received={[len(g["pixels"]) for g in groups.values()]}')
    return complete[-1]

def write_result(key,g,data,dest):
    fid,x,y,width,height,crc=key
    dest.mkdir(parents=True,exist_ok=True)
    (dest/'native_rgb565_be.bin').write_bytes(data)
    pixels=[]
    for i in range(0,len(data),2):
        n=int.from_bytes(data[i:i+2],'big');r=n>>11;gr=n>>5&63;b=n&31
        pixels.append(((r<<3)|(r>>2),(gr<<2)|(gr>>4),(b<<3)|(b>>2)))
    image=Image.new('RGB',(width,height));image.putdata(pixels)
    image.save(dest/'native.png')
    image.resize((width*16,height),Image.Resampling.NEAREST).save(dest/'horizontal_x16_preview.png')
    rows=[]
    for i in range(height):
        a=pixels[i*width:(i+1)*width]
        avg=[sum(p[j] for p in a)/width for j in range(3)]
        rows.append(dict(source_y=y+i,R=avg[0],G=avg[1],B=avg[2],green_excess=avg[1]-(avg[0]+avg[2])/2))
    (dest/'row_rgb.json').write_text(json.dumps(rows,indent=2)+'\n')
    result=dict(completed=True,frame_id=fid,source_x=x,source_y=y,width=width,height=height,
                pixels=len(pixels),crc32=f'{crc:08x}',pages_received=g['pages'],
                preceding_rejected_candidates=g['rejected'],
                stage='CAM1 capture_pipe output BEFORE DDR/scaling/filter/OSD',
                no_sensor_register_writes=True,
                limits=['One frozen spatial strip is not full-frame or continuous-video pixel signoff.',
                        'Native pixels may include sensor/ISP or DVP sampling faults; this does not separate them.',
                        'The horizontal x16 preview repeats each column for visibility; native.png and raw file retain original pixels.',
                        'Do not use the narrow strip to judge optical focus or whole-image sharpness.'])
    (dest/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    try:
        print(json.dumps(write_result(*decode(args.input.read_text(encoding='utf-8-sig',errors='replace')),args.output),indent=2))
    except ValueError as e:
        print(json.dumps(dict(completed=False,error=str(e)),ensure_ascii=False));raise SystemExit(1)
