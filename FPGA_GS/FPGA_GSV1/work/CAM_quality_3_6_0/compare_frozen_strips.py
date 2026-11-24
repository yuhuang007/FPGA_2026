"""Compare two independent E3 exports without altering native evidence."""
import csv,json,math,statistics
from pathlib import Path
from PIL import Image,ImageDraw
base=Path(__file__).parent/'reports'
dirs=[base/'RAW_E3_actual_decoded',base/'RAW_E3_second_decoded']
data=[json.loads((p/'analysis.json').read_text()) for p in dirs]
rows=[]
for p in dirs:
    rr=list(csv.DictReader((p/'rows_detailed.csv').open()))
    rows.append([{k:float(v) if k!='dominant_channel' else v for k,v in r.items()} for r in rr])
def corr(a,b):
    ma,mb=statistics.mean(a),statistics.mean(b)
    aa=sum((x-ma)**2 for x in a);bb=sum((x-mb)**2 for x in b)
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(aa*bb) if aa*bb else None
out=dict(source_rectangle=data[0]['source_rect'],capture1=dict(frame_id=data[0]['frame_id'],crc=data[0]['crc32_actual']),
         capture2=dict(frame_id=data[1]['frame_id'],crc=data[1]['crc32_actual']),
         note='Separate programming epochs; equal frame IDs are not equal physical frames. First cover state unknown; second user reports lens covered throughout freeze.',
         channel_comparison={})
for c in 'RGB':
    a,b=[[r[c+'_mean'] for r in rr] for rr in rows]
    out['channel_comparison'][c]=dict(row_mean_correlation=corr(a,b),
        mean_absolute_row_mean_change=statistics.mean(abs(x-y) for x,y in zip(a,b)),
        row_mean_std_frame1=statistics.pstdev(a),row_mean_std_frame2=statistics.pstdev(b),
        top_row_frame1=max(range(720),key=a.__getitem__),top_row_frame2=max(range(720),key=b.__getitem__))
out['channel_one_fraction_comparison']={str(i):[x['global_bit_one_fractions'][str(i)] for x in data] for i in range(16)}
raw=[(p/'native_rgb565_be.bin').read_bytes() for p in dirs]
out['changed_pixel_count']=sum(raw[0][i:i+2]!=raw[1][i:i+2] for i in range(0,len(raw[0]),2))
out['total_pixels']=len(raw[0])//2
out['strongest_colored_rows_frame2']=[{k:r[k] for k in ('source_y','R_mean','G_mean','B_mean','R_std','G_std','B_std')} for r in sorted(rows[1],key=lambda r:r['color_span'],reverse=True)[:8]]
out['most_green_row_frame2']=max(rows[1],key=lambda r:r['G_mean']-(r['R_mean']+r['B_mean'])/2)
out['limits']=['Only two16-pixel-wide strips, separated by reprogramming; not continuous temporal capture.',
    'Different exposure/gain or AE startup may contribute; frame-specific register values are not exported.',
    'Low correlation does not rule out a smaller fixed-pattern component.',
    'Colored rows beforeDDR cannot distinguish sensor/ISP from pattern-dependent DVP sampling or packing defects.']
(dirs[1]/'comparison_to_first.json').write_text(json.dumps(out,indent=2)+'\n')
canvas=Image.new('RGB',(1090,780),'white');d=ImageDraw.Draw(canvas)
for i,p in enumerate(dirs):
    im=Image.open(p/'native.png').convert('RGB')
    x=i*545
    d.text((x+5,5),'Capture '+str(i+1)+': '+('cover UNKNOWN' if i==0 else 'cover USER CONFIRMED'),fill='black')
    d.text((x+5,22),'x16 width; ORIGINAL levels',fill='black')
    d.text((x+275,22),'x16 width; display gain x8',fill='black')
    canvas.paste(im.resize((256,720),Image.Resampling.NEAREST),(x+5,50))
    canvas.paste(im.point(lambda v:min(255,v*8)).resize((256,720),Image.Resampling.NEAREST),(x+275,50))
canvas.save(dirs[1]/'two_strips_labelled.png')
print(json.dumps(out,indent=2))
