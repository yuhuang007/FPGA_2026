"""Check current-version label structure and provenance; no visual approval."""
import csv, json, hashlib
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    rows=list(csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig')))
    errors=[];counts=Counter();evidence=0;active={}
    for row in rows:
        p=R/row['annotation_file'];a=read(p);sid=row['sample_id']
        active[sid]={'file':p.relative_to(R).as_posix(),'sha256':sha(p)}
        if sha(R/a['image_path'])!=a['image_sha256']:errors.append([sid,'image hash'])
        for name,want in a.get('evidence_sha256',{}).items():
            evidence+=1
            if sha(R/name)!=want:errors.append([sid,'evidence hash',name])
        objects={o['id']:o for o in a['objects']}
        if len(objects)!=len(a['objects']):errors.append([sid,'duplicate object IDs'])
        for o in objects.values():
            counts[o['type']]+=1;x,y,u,v=o['bbox_xyxy']
            if not 0<=x<u<=1920 or not 0<=y<v<=1080:errors.append([sid,o['id'],'bounds'])
            if o.get('parent_id'):
                parent=objects.get(o['parent_id'])
                if not parent:errors.append([sid,o['id'],'missing parent'])
                elif parent['type']=='body':
                    x1,y1,x2,y2=parent['bbox_xyxy']
                    if not x1<=x<u<=x2 or not y1<=y<v<=y2:errors.append([sid,o['id'],'emitter outside body'])
            if o['type']=='emitter':
                if o['color_readable']!=(o['state']!='unknown'):errors.append([sid,o['id'],'state/readability'])
                if o.get('arrow_direction','unknown')!='unknown' and o['symbol']!='arrow':errors.append([sid,o['id'],'arrow morphology'])
    result={'recorded_at':datetime.now(timezone.utc).isoformat(),'active_labels':len(rows),
        'checked_evidence_hashes':evidence,'object_counts':dict(counts),'structural_errors':errors,
        'integrity_passed':not errors,'visual_approval':False,'training_approval':False,'active_label_sha256':active}
    (R/'reports/active_label_structure_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='active_label_sha256'}))
    assert not errors


if __name__=='__main__':main()
