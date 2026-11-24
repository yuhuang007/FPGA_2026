"""Package explicit PC amendments; never overwrite frozen labels or reuse signatures."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,shutil,sys
from PIL import Image,ImageDraw

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    request=read(R/sys.argv[1]);name=sys.argv[2];out=R/'review_stage2/revisions'/name
    assert not out.exists(),f'Refusing to overwrite revision package {out}'
    out.mkdir(parents=True)
    for sub in ['images','labels','overlays','evidence']:(out/sub).mkdir()
    now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();entries=[];tasks=[];requests=[]
    for item in request['revisions']:
        base_manifest=R/item['base_manifest'];base=base_manifest.parent;m=read(base_manifest)
        old=next(e for e in m['entries'] if e['candidate_id']==item['candidate_id']);a=read(base/old['annotation'])
        assert sha(base/old['annotation'])==old['annotation_sha256']
        affected=[]
        for change in item['changes']:
            obj=next(o for o in a['objects'] if o['id']==change['object_id'])
            obj[change['field']]=change['value'];affected.append(change['object_id']+'.'+change['field'])
        for removal in item.get('remove_fields',[]):
            obj=next(o for o in a['objects'] if o['id']==removal['object_id'])
            assert removal['field'] not in ('id','type','bbox_xyxy'), 'Core object fields must be revised, not deleted'
            assert removal['field'] in obj, 'Cannot remove a missing field'
            del obj[removal['field']];affected.append(removal['object_id']+'.'+removal['field'])
        for obj in item.get('append_objects',[]):
            assert obj['id'] not in {o['id'] for o in a['objects']};a['objects'].append(obj);affected.append(obj['id'])
        a.update({'supersedes_annotation_sha256':old['annotation_sha256'],
            'supersedes_manifest_sha256':sha(base_manifest),'label_version':name+'-pc-amendment-20261024',
            'recorded_at':now,'review_status':'PC_revised_pending_version_bound_reconfirmation',
            'affected_fields':affected,'old_review_acceptance_inherited':False,
            'eligible_for_yolo_export':False,'human_signoff':False})
        a['changes'].append(item['note']);a['arbitration'].append('Fresh independent confirmation required for '+', '.join(affected)+' at this new annotation SHA.')
        a['actual_method'].append('PC targeted original-pixel review for amendment; evidence: '+', '.join(item['evidence']))
        evidence=[]
        for relative in item['evidence']:
            p=R/relative;target=out/'evidence'/p.name
            if target.exists():assert sha(target)==sha(p)
            else:shutil.copy2(p,target)
            evidence.append({'file':'evidence/'+p.name,'sha256':sha(p),'original_path':relative})
        label=out/old['annotation'];save(label,a);shutil.copy2(base/old['image'],out/old['image'])
        im=Image.open(out/old['image']).convert('RGB');d=ImageDraw.Draw(im)
        for obj in a['objects']:
            c={'body':'#00ff70','emitter':'#ffff00','ignore':'#ff40ff','hard_negative':'#ff9800'}[obj['type']]
            d.rectangle(obj['bbox_xyxy'],outline=c,width=2);d.text((obj['bbox_xyxy'][0],max(0,obj['bbox_xyxy'][1]-13)),obj['id'],fill=c)
        im.save(out/old['overlay'],quality=96)
        en=dict(old);en.update({'annotation_sha256':sha(label),'overlay_sha256':sha(out/old['overlay']),
                               'label_version':a['label_version'],'evidence':evidence});entries.append(en)
        template=next(json.loads(line) for line in (base/'review_fillback.jsonl').read_text(encoding='utf-8').splitlines() if json.loads(line)['candidate_id']==a['candidate_id'])
        template.update({'reviewed_annotation_sha256':sha(label),'label_version':a['label_version']});tasks.append(template)
        requests.append({'candidate_id':a['candidate_id'],'revision_manifest':str((out/'manifest.json').relative_to(R)).replace('\\','/'),
                         'annotation_sha256':sha(label),'affected_fields':affected,'status':'pending_independent_reconfirmation','training_approval':False})
    manifest={'batch_id':name,'created_at':now,'purpose':'PC amendments for version-bound reconfirmation; no old acceptance inherited',
        'count':len(entries),'class_order':['motor_vehicle_body','pedestrian_body'],'independent_review_completed':False,
        'human_confirmations_completed':0,'entries':entries,'arbitration_required':['Reconfirm all changed fields against new label SHA; unresolved ignore and training release remain separate.']}
    save(out/'manifest.json',manifest)
    mh=sha(out/'manifest.json')
    for t in tasks:t['manifest_sha256']=mh
    (out/'review_fillback.jsonl').write_text(''.join(json.dumps(t,ensure_ascii=False)+'\n' for t in tasks),encoding='utf-8')
    save(out/'files_sha256.json',{str(p.relative_to(out)).replace('\\','/'):sha(p) for p in out.rglob('*') if p.is_file()})
    queue_path=R/'review_stage2/reconfirmation_queue.json';queue=read(queue_path) if queue_path.exists() else {'requests':[]}
    for q in requests:q['revision_manifest_sha256']=mh
    queue['recorded_at']=now;queue['requests'].extend(requests);save(queue_path,queue)
    print(json.dumps({'revision_package':name,'images':len(entries),'new_manifest_sha256':mh,'old_acceptance_inherited':False}))

if __name__=='__main__':main()
