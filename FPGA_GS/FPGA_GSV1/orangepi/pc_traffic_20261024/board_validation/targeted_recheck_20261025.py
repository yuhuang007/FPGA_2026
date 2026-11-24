"""Independent review evidence preparation and binding, no generated verdicts."""
import datetime,hashlib,json,sys
from pathlib import Path
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1]
O=R/'review_stage2/independent_codex_board_r2'
I=R/'review_stage2/targeted_recheck_20261025'
V=O/'recheck_20261025_views'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verified():
    tasks=read(I/'task_index.json')['tasks'];templates={a['candidate_id']:a for a in map(json.loads,(I/'review_fillback.jsonl').read_text(encoding='utf-8').splitlines())}
    out=[]
    for t in tasks:
        mp=R/t['revision_manifest'];assert sha(mp)==t['manifest_sha256']
        e=next(e for e in read(mp)['entries'] if e['candidate_id']==t['candidate_id']);ap=R/t['annotation_file'];ip=mp.parent/e['image'];a=read(ap);template=templates[t['candidate_id']]
        assert sha(ap)==e['annotation_sha256']==t['annotation_sha256']==template['reviewed_annotation_sha256']
        assert sha(ip)==e['image_sha256']==a['image_sha256']==template['image_sha256']
        assert a['label_version']==e['label_version']==t['label_version']==template['label_version']
        assert template['manifest_sha256']==t['manifest_sha256']
        out.append((t,e,a,ip,template))
    assert len(out)==14
    return out
def main():
    entries=verified()
    if sys.argv[1]=='prepare':
        assert not (O/'recheck_20261025_integrity.json').exists()
        protected={}
        for d in [I,R/'review_stage2/revisions',R/'review_stage2/frozen']:
            protected.update({str(p.relative_to(R)):sha(p) for p in d.rglob('*') if p.is_file()})
        V.mkdir(exist_ok=True)
        for t,e,a,ip,template in entries:
            im=Image.open(ip).convert('RGB');full=im.resize((960,540),Image.Resampling.LANCZOS)
            full.save(V/(t['candidate_id']+'_full.png'))
            rows=(len(a['objects'])+3)//4;detail=Image.new('RGB',(960,220*rows),'#eeeeee');d=ImageDraw.Draw(detail)
            for i,o in enumerate(a['objects']):
                b=o['bbox_xyxy'];rect=(max(0,b[0]-12),max(0,b[1]-12),min(im.width,b[2]+12),min(im.height,b[3]+12));crop=im.crop(rect);s=min(4,230/crop.width,180/crop.height);crop=crop.resize((round(crop.width*s),round(crop.height*s)),Image.Resampling.NEAREST)
                x=i%4*240;y=i//4*220;detail.paste(crop,(x,y+35));d.text((x+2,y+2),o['id']+' '+o['type'],fill='black');d.text((x+2,y+17),str(b),fill='black');d.rectangle((x+(b[0]-rect[0])*s,y+35+(b[1]-rect[1])*s,x+(b[2]-rect[0])*s,y+35+(b[3]-rect[1])*s),outline='magenta',width=1)
            detail.save(V/(t['candidate_id']+'_detail.png'))
            panel=Image.new('RGB',(960,540+detail.height));panel.paste(full,(0,0));panel.paste(detail,(0,540));panel.save(V/(t['candidate_id']+'_panel.jpg'),quality=94)
        (O/'recheck_20261025_integrity.json').write_text(json.dumps({'protected':protected,'task_index_sha256':sha(I/'task_index.json')},indent=2),encoding='utf-8')
        print('Verified 14 task identities; independent views prepared. No verdicts generated.')
    elif sys.argv[1]=='labels':
        wanted=set(sys.argv[2:])
        for t,e,a,ip,template in entries:
            if t['candidate_id'][-4:] in wanted:print(json.dumps({'id':t['candidate_id'],'version':a['label_version'],'objects':a['objects'],'affected_fields':t['affected_fields']},ensure_ascii=False))
    elif sys.argv[1]=='save':
        data=read(Path(sys.argv[2]));target=O/f"recheck_20261025_part_{data['part']:02d}.jsonl";assert not target.exists()
        by_id={t['candidate_id']:(t,e,a,ip,template) for t,e,a,ip,template in entries};records=[]
        for obs in data['reviews']:
            t,e,a,ip,template=by_id[obs['candidate_id']];r=dict(template)
            r.update({'revision_manifest':t['revision_manifest'],'reviewer_id':'Codex_board_independent_AI_20261025_targeted','reviewer_type':'AI','independent_from_first_pass':True,'reviewed_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
                'actual_method':['Fresh visual inspection of full image extent at 960x540, then contextual original-pixel crops enlarged with nearest-neighbor up to 4x; no generative enhancement.','Read current version-bound object labels and inspect affected geometry, kind and attributes. Targeted change review, not a new exhaustive whole-image omission or grouping audit.'],
                'full_original_checked':True,'omission_search_completed':False,'bounds_checked':True,'kind_checked':True,'attributes_checked':True,'checks_scope':'Affected objects and surrounding context; broad omissions/grouping not re-certified.',
                'decision':obs['decision'],'findings':obs['findings'],'corrected_annotation_file':None,'human_signoff':False,'training_approval':False,
                'decision_scope':'Accept/revise/uncertain current draft changes only; no whole-image YOLO export or human/training authorization.',
                'original_image_evidence':{'path':str(ip.relative_to(R)),'sha256':sha(ip)},
                'viewed_evidence':[{'path':str(p.relative_to(R)),'sha256':sha(p)} for p in [V/(t['candidate_id']+'_full.png'),V/(t['candidate_id']+'_detail.png')]],
                'body_detection_assessment':obs['body_detection_assessment'],'PC_arbitration_required':obs.get('PC_arbitration_required',[]),'old_review_acceptance_inherited':False})
            for extra in obs.get('extra_evidence',[]):
                ep=R/extra;r['viewed_evidence'].append({'path':extra,'sha256':sha(ep)})
            if obs.get('extra_evidence'):r['actual_method'].append('Additionally inspected independent 4x nearest-neighbor unmarked and coordinate-grid crop, recorded in viewed_evidence.')
            records.append(r)
        changed=[p for p,h in read(O/'recheck_20261025_integrity.json')['protected'].items() if not (R/p).exists() or sha(R/p)!=h];assert not changed,changed
        target.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8');print(str(target))
if __name__=='__main__':main()
