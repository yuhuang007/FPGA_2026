"""Version explicit external-photo amendments without changing frozen sources."""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, shutil, sys
from PIL import Image,ImageDraw

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    request=read(R/sys.argv[1]);out=R/'review_stage2/external_scene_revisions'/sys.argv[2];assert not out.exists()
    for sub in ('images','labels','views','evidence'):(out/sub).mkdir(parents=True,exist_ok=True)
    entries=[];tasks=[]
    for q in request['revisions']:
        mp=R/q['base_manifest'];m=read(mp);e=next(e for e in m['entries'] if e['candidate_id']==q['candidate_id'])
        old=mp.parent/e['annotation'];assert sha(old)==e['annotation_sha256'];a=read(old);affected=[]
        for change in q['changes']:
            o=next(o for o in a['objects'] if o['id']==change['object_id']);o[change['field']]=change['value'];affected.append(o['id']+'.'+change['field'])
        for o in q.get('append_objects',[]):
            assert o['id'] not in {v['id'] for v in a['objects']};a['objects'].append(o);affected.append(o['id'])
        w,h=a['image_size']
        for o in a['objects']:
            x,y,u,v=o['bbox_xyxy'];assert 0<=x<u<=w and 0<=y<v<=h
        evidence=[]
        for relative in q['evidence']:
            p=R/relative;target=out/'evidence'/p.name;shutil.copy2(p,target);evidence.append({'path':target.relative_to(R).as_posix(),'sha256':sha(target)})
        image=out/e['image'];shutil.copy2(mp.parent/e['image'],image);assert sha(image)==e['image_sha256']
        a.update(label_version=out.name+'-PC-20261025',recorded_at=datetime.now(timezone.utc).isoformat(),
            supersedes_annotation_sha256=e['annotation_sha256'],supersedes_manifest_sha256=sha(mp),affected_fields=affected,
            old_review_acceptance_inherited=False,review_status='PC_revised_pending_genuine_targeted_reconfirmation',
            image_path=image.relative_to(R).as_posix(),human_signoff=False,eligible_for_yolo_export=False,training_release=False)
        a['notes']+=q['notes'];a['evidence_sha256']+=evidence
        a['actual_method']=str(a['actual_method'])+'; actual targeted PC amendments from '+sys.argv[1]
        label=out/e['annotation'];save(label,a);im=Image.open(image).convert('RGB');d=ImageDraw.Draw(im)
        for o in a['objects']:d.rectangle(o['bbox_xyxy'],outline='lime' if o['type']=='body' else 'magenta',width=2)
        im.thumbnail((900,650));im.save(out/'views'/image.name,quality=92)
        new=dict(e);new.update(annotation_sha256=sha(label),label_version=a['label_version']);entries.append(new)
        tasks.append({'candidate_id':e['candidate_id'],'image_sha256':e['image_sha256'],'annotation_sha256':sha(label),
            'label_version':a['label_version'],'affected_fields':affected,'status':'pending_genuine_targeted_check'})
    mp=out/'manifest.json';save(mp,{'schema_version':'0.1','batch_id':out.name,'immutable':True,
        'recorded_at':datetime.now(timezone.utc).isoformat(),'images':len(entries),'entries':entries,
        'purpose':'New version of actual PC adjudications; only changed fields require fresh independent confirmation.',
        'reviewer_type':'AI','human_signoff':False,'training_release':False,
        'PC_judgment_file':sys.argv[1],'PC_judgment_sha256':sha(R/sys.argv[1])})
    for t in tasks:t.update(manifest=mp.relative_to(R).as_posix(),manifest_sha256=sha(mp))
    save(out/'independent_tasks.json',{'tasks':tasks,'old_acceptance_inherited':False})
    print(json.dumps({'revision':out.name,'images':len(entries),'manifest_sha256':sha(mp)}))
if __name__=='__main__':main()
