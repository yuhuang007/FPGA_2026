"""Read-only packet audit and small independent review views; no verdict generation."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review_stage2/independent_codex_board_r2'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--audit',action='store_true');parser.add_argument('--batch');parser.add_argument('--start',type=int,default=0);args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.audit:
        cp=read(ROOT/'reports/continuation_checkpoint.json');expected={b['batch_id']:b['manifest_sha256'] for b in cp['frozen_batches']};reports=[];protected={}
        for name in ('batch_001','batch_002','batch_003'):
            directory=ROOT/'review_stage2/frozen'/name;m=read(directory/'manifest.json');assert sha(directory/'manifest.json')==expected[name]
            errors=[]
            for filename,want in read(directory/'files_sha256.json').items():
                p=directory/filename
                if not p.is_file() or sha(p)!=want:errors.append(filename)
            for entry in m['entries']:
                for key in ('image','annotation','overlay'):assert sha(directory/entry[key])==entry[key+'_sha256']
                a=read(directory/entry['annotation']);assert a['label_version']==entry['label_version'];assert a['image_sha256']==entry['image_sha256']
            protected.update({str(p):sha(p) for p in directory.rglob('*') if p.is_file()})
            reports.append({'batch':name,'count':m['count'],'manifest_sha256':sha(directory/'manifest.json'),'label_versions':sorted(set(e['label_version'] for e in m['entries'])),'errors':errors,'passed':not errors,'ordered_candidates':[e['candidate_id'] for e in m['entries']]})
        (OUT/'integrity_before.json').write_text(json.dumps({'time':datetime.datetime.now().astimezone().isoformat(),'batches':reports,'protected_files':protected},indent=2),encoding='utf-8')
        print(json.dumps(reports,indent=2));return
    batch=ROOT/'review_stage2/frozen'/args.batch;m=read(batch/'manifest.json');views=OUT/'views'/args.batch;views.mkdir(parents=True,exist_ok=True)
    for entry in m['entries'][args.start:args.start+8]:
        ann=read(batch/entry['annotation']);im=Image.open(batch/entry['image']).convert('RGB')
        # Original and bounding regions are separate. Unmarked original first, then marked original-pixel crops.
        full=im.resize((960,540),Image.Resampling.LANCZOS);full.save(views/(entry['candidate_id']+'_full.jpg'),quality=90)
        objects=ann['objects'];rows=(len(objects)+3)//4;canvas=Image.new('RGB',(960,max(1,rows)*220),'#eeeeee');d=ImageDraw.Draw(canvas)
        for i,o in enumerate(objects):
            b=o['bbox_xyxy'];pad=12;rect=(max(0,b[0]-pad),max(0,b[1]-pad),min(im.width,b[2]+pad),min(im.height,b[3]+pad))
            crop=im.crop(rect);scale=min(4,230/crop.width,180/crop.height);crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.NEAREST)
            x=(i%4)*240;y=(i//4)*220;canvas.paste(crop,(x,y+35))
            d.text((x+2,y+2),o['id']+' '+o['type'],fill='black');d.text((x+2,y+17),str(b),fill='black')
            box=[x+(b[0]-rect[0])*scale,y+35+(b[1]-rect[1])*scale,x+(b[2]-rect[0])*scale,y+35+(b[3]-rect[1])*scale]
            d.rectangle(box,outline={'body':'green','emitter':'orange','ignore':'magenta','hard_negative':'red'}.get(o['type'],'blue'),width=1)
        canvas.save(views/(entry['candidate_id']+'_detail.jpg'),quality=94)
        combined=Image.new('RGB',(960,540+canvas.height),'white');combined.paste(full,(0,0));combined.paste(canvas,(0,540));combined.save(views/(entry['candidate_id']+'_review.jpg'),quality=91)
        compact={'id':entry['candidate_id'],'version':ann['label_version'],'objects':objects,'arbitration':ann.get('arbitration'),'complete':ann['complete_image_annotation']}
        print(json.dumps(compact,ensure_ascii=False))

if __name__=='__main__':main()
