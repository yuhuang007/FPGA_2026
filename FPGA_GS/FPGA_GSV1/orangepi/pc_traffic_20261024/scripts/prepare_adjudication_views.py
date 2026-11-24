"""Prepare a few original-image locating views; no decisions are generated."""
import csv, json, sys
from pathlib import Path
from PIL import Image, ImageDraw

R = Path(__file__).resolve().parents[1]
out = R/'review_stage2/adjudication_20261025'
out.mkdir(exist_ok=True)
rows = {r['sample_id']: r for r in csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig'))}
for i in map(int, sys.argv[1:]):
    row = rows[f's2tld1080_{i:04d}']
    a = json.loads((R/row['annotation_file']).read_text(encoding='utf-8'))
    im = Image.open(R/row['image_path']).convert('RGB')
    full = out/f'{i:04d}_full.jpg'
    detail = out/f'{i:04d}_detail.png'
    assert not full.exists() and not detail.exists(), 'Reuse existing evidence; do not overwrite'
    im.resize((1152,648),Image.Resampling.LANCZOS).save(full,quality=94)
    boxes = [(o['id'], [max(0,o['bbox_xyxy'][0]-15), max(0,o['bbox_xyxy'][1]-15),
        min(1920,o['bbox_xyxy'][2]+15), min(1080,o['bbox_xyxy'][3]+15)])
        for o in a['objects'] if o['type'] in ('body','ignore')]
    can = Image.new('RGB',(900,350*((len(boxes)+2)//3)),'white')
    draw = ImageDraw.Draw(can)
    for j,(name,box) in enumerate(boxes):
        crop=im.crop(box);scale=min(4,280/crop.width,300/crop.height)
        patch=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.NEAREST)
        x=j%3*300;y=j//3*350
        draw.text((x,y),f'{i:04d} {name} {box}',fill='black');can.paste(patch,(x,y+40))
    can.save(detail)
print('Prepared locating views only:',sys.argv[1:])
