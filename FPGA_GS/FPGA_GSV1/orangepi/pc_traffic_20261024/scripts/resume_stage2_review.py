"""Small-image review tooling. Coordinates/decisions are entered after actual viewing.

No inference, independent signature, or training approval is generated here.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv, hashlib, json, sys
from PIL import Image, ImageDraw

R = Path(__file__).resolve().parents[1]
O = R / 'review_stage2'

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def save(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()

def prepare(indices):
    out = O / 'resume_evidence'
    out.mkdir(exist_ok=True)
    for i in indices:
        im = Image.open(R / f'data/candidate_images/s2tld1080_{i:04d}.jpg').convert('RGB')
        im.resize((1152, 648), Image.Resampling.LANCZOS).save(out / f'{i:04d}_full.jpg', quality=94)
        # These contexts are valid for the currently reviewed stationary tree/bus scene.
        # Later scenes must use explicitly chosen contexts instead.
        if 8 <= i <= 11:
            boxes = [(580,450,670,550),(905,440,995,540),(1520,495,1610,595)]
            c = Image.new('RGB',(900,328),'white'); d = ImageDraw.Draw(c)
            for j,box in enumerate(boxes):
                c.paste(im.crop(box).resize((270,300),Image.Resampling.NEAREST),(j*300,28))
                d.text((j*300,4),f'{i:04d} {box}',fill='black')
            c.save(out/f'{i:04d}_detail.png')
    print(json.dumps({'prepared_only_not_reviewed':indices}))

def contexts(indices, extras):
    source=read(O/'source_reference.json')
    for i in indices:
        im=Image.open(R/f'data/candidate_images/s2tld1080_{i:04d}.jpg').convert('RGB')
        boxes=[]
        for k,obj in enumerate(source[i]):
            x1,y1,x2,y2=obj['bbox_xyxy']
            if x1>=x2 or y1>=y2: continue
            boxes.append((f'source context {k}',[max(0,x1-15),max(0,y1-15),min(1920,x2+15),min(1080,y2+15)]))
        boxes += [(f'whole-frame search {k}',b) for k,b in enumerate(extras.get(str(i),[]))]
        assert boxes
        canvas=Image.new('RGB',(900,350*((len(boxes)+2)//3)),'white');draw=ImageDraw.Draw(canvas)
        for n,(name,box) in enumerate(boxes):
            crop=im.crop(box);scale=min(3,280/crop.width,305/crop.height)
            patch=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.NEAREST)
            x=(n%3)*300;y=(n//3)*350
            draw.text((x+2,y+3),f'{i:04d} {name}',fill='black')
            draw.text((x+2,y+17),str(tuple(box)),fill='black');canvas.paste(patch,(x,y+40))
        canvas.save(O/'resume_evidence'/f'{i:04d}_contexts.png')
    print(json.dumps({'context_images_prepared_not_reviewed':indices}))

def record(path):
    packet = read(path)
    rows = list(csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig')))
    source = read(O/'source_reference.json')
    for entry in packet['images']:
        i = entry['index']; row = rows[i]; sid = row['sample_id']
        p = O/'first_pass'/f'{sid}.json'
        if p.exists():
            raise RuntimeError(f'Refusing to overwrite existing label: {p}')
        assert entry['full_image_checked'] is True and entry['detail_checked'] is True
        assert entry['objects'] and entry['note'] and entry['arbitration']
        objects = entry['objects']
        ids = {x['id'] for x in objects}
        assert len(ids) == len(objects)
        im_path = R/row['image_path']; assert sha(im_path) == row['sha256']
        for obj in objects:
            x1,y1,x2,y2 = obj['bbox_xyxy']
            assert 0 <= x1 < x2 <= 1920 and 0 <= y1 < y2 <= 1080
            assert obj.get('control_relation','unknown') == 'unknown'
            assert not obj.get('parent_id') or obj['parent_id'] in ids
            if obj['type'] == 'emitter' and obj.get('parent_id'):
                parent = next(x for x in objects if x['id'] == obj['parent_id'])
                if parent['type'] == 'body':
                    px1,py1,px2,py2 = parent['bbox_xyxy']
                    assert px1 <= x1 < x2 <= px2 and py1 <= y1 < y2 <= py2, (i, obj['id'], 'emitter outside body; inspect geometry before publication')
        evidence = entry['evidence']
        for name in evidence:
            assert (R/name).is_file()
        label = {'schema_version':'0.1','label_version':'pc-ai-r1.1-resume-20261024',
            'candidate_id':sid,'image_path':row['image_path'].replace('\\','/'),
            'image_sha256':row['sha256'],'image_size':[1920,1080],
            'reviewer':'Codex_PC_AI_stage2','reviewer_type':'AI','human_signoff':False,
            'recorded_at':now(),'review_status':'AI_first_pass_detailed_pending_independent',
            'actual_method':entry.get('actual_method',['unmarked full image resized to 1152x648, whole-frame omission search',
                             'selected original-pixel contexts enlarged with nearest-neighbor; uncertain regions stay ignore']),
            'evidence_files':evidence,'evidence_sha256':{n:sha(R/n) for n in evidence},
            'complete_image_annotation':entry.get('complete_image_annotation',False),'eligible_for_yolo_export':False,
            'blocked_reason':'Unresolved regions and independent review/arbitration pending; no standard YOLO full-image export.',
            'objects':objects,'source_reference_only':source[i],'changes':[entry['note']],
            'arbitration':entry['arbitration'],'group_observation':entry['group_observation'],
            'unreadable_attributes_policy':'No inferred off, symbol, color, kind or control relation.'}
        save(p,label)
        im = Image.open(im_path).convert('RGB'); d=ImageDraw.Draw(im)
        for obj in objects:
            color={'body':'#00ff70','emitter':'#ffff00','ignore':'#ff40ff','hard_negative':'#ff9800'}[obj['type']]
            d.rectangle(obj['bbox_xyxy'],outline=color,width=2)
            d.text((obj['bbox_xyxy'][0],max(0,obj['bbox_xyxy'][1]-13)),obj['id'],fill=color)
        im.save(O/'overlays'/f'{sid}.jpg',quality=96)
    print(json.dumps({'recorded_actual_first_pass':[e['index'] for e in packet['images']],
                      'independent_reviews_created':0,'training_approvals_created':0}))

if __name__ == '__main__':
    if sys.argv[1] == 'prepare': prepare([int(x) for x in sys.argv[2:]])
    elif sys.argv[1] == 'record': record(R/sys.argv[2])
    elif sys.argv[1] == 'contexts': contexts([int(x) for x in sys.argv[3:]],read(R/sys.argv[2]))
    else: raise SystemExit('prepare indices... | record explicit_decisions.json')
