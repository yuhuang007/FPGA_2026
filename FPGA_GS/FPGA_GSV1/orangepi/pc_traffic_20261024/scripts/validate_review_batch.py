"""Validate frozen review packet integrity, schema and optional genuine fillback."""
from pathlib import Path
import hashlib,json,sys
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    batch=(R/sys.argv[1]).resolve(); m=json.loads((batch/'manifest.json').read_text(encoding='utf-8'))
    errors=[]
    for name,want in json.loads((batch/'files_sha256.json').read_text(encoding='utf-8')).items():
        if not (batch/name).is_file():errors.append('file missing: '+name)
        elif sha(batch/name)!=want:errors.append('file changed: '+name)
    for e in m['entries']:
        for key in ['image','annotation','overlay']:
            if sha(batch/e[key])!=e[key+'_sha256']:errors.append(e['candidate_id']+': '+key+' hash')
        a=json.loads((batch/e['annotation']).read_text(encoding='utf-8')); ids={o['id'] for o in a['objects']}
        if len(ids)!=len(a['objects']):errors.append(e['candidate_id']+': duplicate object ids')
        for o in a['objects']:
            x1,y1,x2,y2=o['bbox_xyxy']
            if not(0<=x1<x2<=1920 and 0<=y1<y2<=1080):errors.append(e['candidate_id']+': invalid box')
            if o.get('parent_id') and o['parent_id'] not in ids:errors.append(e['candidate_id']+': missing parent')
            if o.get('control_relation','unknown')!='unknown':errors.append(e['candidate_id']+': control inference')
    r={'integrity_passed':not errors,'batch':m['batch_id'],'images':m['count'],
       'manifest_sha256':sha(batch/'manifest.json'),'errors':errors,
       'visual_review_passed':False,'human_signoff':False,'training_approval':False}
    if len(sys.argv)>2:
        fillback=Path(sys.argv[2]); es={e['candidate_id']:e for e in m['entries']}; done=[]
        for line in fillback.read_text(encoding='utf-8').splitlines():
            if not line.strip():continue
            a=json.loads(line); e=es[a['candidate_id']]
            if not a.get('decision'):continue
            assert a.get('reviewer_id') and a.get('reviewer_type') in ['AI','human']
            assert a.get('independent_from_first_pass') is True and a['reviewer_id']!=e['first_pass_reviewer']
            assert a.get('reviewed_at') and a.get('actual_method') and a.get('full_original_checked') is True
            assert a['image_sha256']==e['image_sha256'] and a['reviewed_annotation_sha256']==e['annotation_sha256']
            if a['reviewer_type']=='AI': assert not a.get('human_signoff')
            done.append(a['candidate_id'])
        assert len(done)==len(set(done))
        r['syntactically_complete_fillback_records']=len(done)
        r['note']='Identity/independence cannot be established by this schema validator; do not auto-approve.'
    print(json.dumps(r,ensure_ascii=False,indent=2)); return 0 if not errors else 1
if __name__=='__main__':raise SystemExit(main())
