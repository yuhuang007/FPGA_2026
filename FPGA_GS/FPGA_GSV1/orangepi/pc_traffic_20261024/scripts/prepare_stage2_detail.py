from pathlib import Path
import json
from PIL import Image, ImageDraw
R=Path(__file__).resolve().parents[1]; O=R/'review_stage2'
(O/'duplicate_pairs').mkdir(exist_ok=True); (O/'raw_detail').mkdir(exist_ok=True)
pairs=json.loads((R/'reports/near_duplicate_candidates.json').read_text())['pairs']
for k in range(0,len(pairs),4):
    canvas=Image.new('RGB',(1600,1920),'white'); d=ImageDraw.Draw(canvas)
    for q,p in enumerate(pairs[k:k+4]):
        y=q*480
        d.text((5,y+3),f"Pair {k+q:02d}: {p['a']} | {p['b']} dHash={p['dhash128_distance']}",fill='black')
        for j,key in enumerate(['a','b']):
            im=Image.open(R/'data/candidate_images'/f"{p[key]}.jpg").resize((800,450))
            canvas.paste(im,(j*800,y+25))
    canvas.save(O/'duplicate_pairs'/f'{k//4:02d}.jpg',quality=94)
# Full native-pixel upper road and all source-object context; no labels drawn.
for i in range(400):
    im=Image.open(R/'data/candidate_images'/f's2tld1080_{i:04d}.jpg')
    im.crop((0,80,1920,720)).save(O/'raw_detail'/f'{i:04d}.jpg',quality=96)
print('87 pair comparisons; 400 native-pixel upper-road crops generated (not reviewed by script)')
