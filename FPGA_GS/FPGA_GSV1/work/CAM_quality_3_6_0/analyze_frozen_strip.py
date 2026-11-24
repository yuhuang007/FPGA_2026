"""Read-only analysis of an already CRC-validated RGB565 strip; no smoothing."""
import argparse, csv, hashlib, json, math, statistics, zlib
from pathlib import Path
from PIL import Image, ImageDraw

p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('uart',type=Path)
p.add_argument('--cover-state',default='Not independently confirmed at reset+20s freeze time.')
a=p.parse_args();d=a.folder
meta=json.loads((d/'result.json').read_text());raw=(d/'native_rgb565_be.bin').read_bytes()
w,h=meta['width'],meta['height']
words=[int.from_bytes(raw[i:i+2],'big') for i in range(0,len(raw),2)]
im=Image.open(d/'native.png').convert('RGB');rgb=list(im.getdata());rows=[]
for y in range(h):
    r=dict(source_y=y+meta['source_y'])
    pix=rgb[y*w:(y+1)*w];ww=words[y*w:(y+1)*w]
    for c,name in enumerate('RGB'):
        v=[v[c] for v in pix]
        r.update({name+'_mean':statistics.mean(v),name+'_std':statistics.pstdev(v),
                  name+'_min':min(v),name+'_max':max(v)})
    r['color_span']=max(r[c+'_mean'] for c in 'RGB')-min(r[c+'_mean'] for c in 'RGB')
    r['dominant_channel']=max('RGB',key=lambda c:r[c+'_mean'])
    for bit in range(16):r['bit'+str(bit)+'_one_fraction']=sum((n>>bit)&1 for n in ww)/w
    rows.append(r)
with (d/'rows_detailed.csv').open('w',newline='') as f:
    out=csv.DictWriter(f,fieldnames=list(rows[0]));out.writeheader();out.writerows(rows)
groups={};malformed=0
for line in a.uart.read_text(encoding='utf-8-sig').splitlines():
    if not line.startswith('N2 35P '):continue
    try:v=[int(x,16) for x in line.split()[2:]]
    except ValueError:malformed+=1;continue
    if len(v)!=40 or v[20]!=0x43315058:malformed+=1;continue
    key=tuple(v[i] for i in (21,22,23,24,26))
    groups.setdefault(key,{}).setdefault(v[25],[]).append(v[27:])
expected=set(range(0,w*h,24));checks=[]
for key,pages in groups.items():
    checks.append(dict(frame_id=key[0],flags=hex(key[1]),xy=hex(key[2]),size=hex(key[3]),
        crc=f'{key[4]:08x}',unique_pages=len(pages),missing_offsets=sorted(expected-set(pages)),
        unexpected_offsets=sorted(set(pages)-expected),
        conflicting_offsets=[o for o,v in pages.items() if any(x!=v[0] for x in v)],
        repetitions_min=min(map(len,pages.values())),repetitions_max=max(map(len,pages.values()))))
quant=lambda x:dict(min=min(x),median=statistics.median(x),max=max(x))
summary=dict(frame_id=meta['frame_id'],source_rect=[meta['source_x'],meta['source_y'],w,h],
    bytes=len(raw),crc32_actual=f'{zlib.crc32(raw):08x}',crc32_descriptor=meta['crc32'],
    sha256_raw=hashlib.sha256(raw).hexdigest(),page_checks=checks,malformed_lines=malformed,
    global_rgb_means=[statistics.mean(v[c] for v in rgb) for c in range(3)],
    global_rgb_range=[[min(v[c] for v in rgb),max(v[c] for v in rgb)] for c in range(3)],
    row_mean_summary={c:quant([r[c+'_mean'] for r in rows]) for c in 'RGB'},
    within_row_std_summary={c:quant([r[c+'_std'] for r in rows]) for c in 'RGB'},
    row_color_span_summary=quant([r['color_span'] for r in rows]),
    strongest_colored_rows=sorted(rows,key=lambda r:r['color_span'],reverse=True)[:16],
    global_bit_one_fractions={str(bit):sum((n>>bit)&1 for n in words)/len(words) for bit in range(16)},
    frozen_cover_state=a.cover_state,
    frozen_exposure_gain='Not exported or latched in E3; unavailable for this frozen frame.',
    caution='CRC verifies export integrity only. One narrow frozen strip does not characterize all columns/frames.')
(d/'analysis.json').write_text(json.dumps(summary,indent=2)+'\n')
# Same code values, horizontally repeated, then a separately labelled display-only gain.
native=im.resize((256,h),Image.Resampling.NEAREST)
enhanced=im.point(lambda x:min(255,x*8)).resize((256,h),Image.Resampling.NEAREST)
canvas=Image.new('RGB',(1060,h+65),'white');draw=ImageDraw.Draw(canvas)
draw.text((10,8),'FROZEN RGB565 x1120..1135: '+a.cover_state,fill='black')
draw.text((10,28),'x16 width only; original values',fill='black');canvas.paste(native,(10,55))
draw.text((280,28),'x16 width + display gain x8',fill='black');canvas.paste(enhanced,(280,55))
draw.text((550,28),'Row means, original RGB888 scale 0..255',fill='black')
for tick in (0,64,128,192,255):
    xx=550+tick*1.9;draw.line((xx,55,xx,h+54),fill='#dddddd');draw.text((xx,42),str(tick),fill='black')
for c,color in zip('RGB',('red','green','blue')):
    points=[(550+r[c+'_mean']*1.9,55+i) for i,r in enumerate(rows)]
    draw.line(points,fill=color,width=1)
canvas.save(d/'comparison_labelled.png')
print(json.dumps({k:v for k,v in summary.items() if k!='strongest_colored_rows'},indent=2))
