from pathlib import Path
from PIL import Image, ImageDraw
import json,sys
R=Path(__file__).resolve().parents[1]; O=R/'review_stage2/zooms'; O.mkdir(exist_ok=True)
source=json.loads((R/'review_stage2/source_reference.json').read_text())
for arg in sys.argv[1:]:
    i=int(arg); im=Image.open(R/'data/candidate_images'/f's2tld1080_{i:04d}.jpg')
    # Include native unmarked full upper half, INCLUDING y=0. Plus each source in 4x context.
    c=Image.new('RGB',(1920,1040),'white');d=ImageDraw.Draw(c)
    c.paste(im.crop((0,0,1920,600)),(0,0))
    for j,obj in enumerate(source[i][:5]):
        a,b,x,y=obj['bbox_xyxy']; cx=(a+x)//2;cy=(b+y)//2
        box=(max(0,cx-45),max(0,cy-45),min(1920,cx+45),min(1080,cy+45))
        crop=im.crop(box).resize(((box[2]-box[0])*4,(box[3]-box[1])*4),Image.Resampling.NEAREST)
        c.paste(crop,(j*380,635));d.text((j*380,608),f'{i:04d} source#{j} crop={box}',fill='black')
    c.save(O/f'{i:04d}.png')
