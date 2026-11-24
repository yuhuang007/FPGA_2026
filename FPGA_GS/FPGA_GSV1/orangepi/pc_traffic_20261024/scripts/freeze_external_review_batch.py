"""Freeze explicitly recorded visual judgments, never generate labels from source boxes."""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, shutil, sys
from PIL import Image, ImageDraw

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    request=read(R/sys.argv[1]);source=R/request['acquisition_manifest'];acq=read(source)
    out=R/request['output'];assert not out.exists(),'Never overwrite a published batch'
    for sub in ('images','labels','views','evidence'):(out/sub).mkdir(parents=True,exist_ok=True)
    acquired={e['candidate_id']:e for e in acq['entries'] if e.get('image')};entries=[];licenses=[];tasks=[]
    for d in request['judgments']:
        assert d['actual_full_image_viewed'] and d['actual_detail_viewed']
        e=acquired[d['candidate_id']];assert e['license_status'] in ('verified_current_oembed_CC_BY','verified_current_Wikimedia_CC0_or_CC_BY','verified_current_Wikimedia_explicit_CC_license')
        if e['license_status']=='verified_current_Wikimedia_explicit_CC_license':
            assert e['current_license'] in ('CC0','CC BY 2.0','CC BY 3.0','CC BY 4.0','CC BY-SA 3.0','CC BY-SA 4.0')
        src=R/e['image'];assert sha(src)==e['image_sha256'];im=Image.open(src).convert('RGB');w,h=im.size
        assert [w,h]==e['image_size'];assert len({o['id'] for o in d['objects']})==len(d['objects'])
        for o in d['objects']:
            x,y,u,v=o['bbox_xyxy'];assert 0<=x<u<=w and 0<=y<v<=h
            if o['type']=='body':assert o['kind'] in ('motor_vehicle','pedestrian')
        dst=out/'images'/src.name;shutil.copy2(src,dst);evidence=[]
        provenance=e.get('source_oembed',e.get('source_metadata'));assert provenance
        assert sha(R/provenance)==e.get('source_oembed_sha256',e.get('source_metadata_sha256'))
        for p in [R/f for f in d['evidence']]+[R/provenance]+([R/e['photo_page_evidence']] if e.get('photo_page_evidence') else []):
            target=out/'evidence'/p.name;shutil.copy2(p,target);evidence.append({'path':target.relative_to(R).as_posix(),'sha256':sha(target)})
        a={'schema_version':'0.1','candidate_id':e['candidate_id'],'label_version':request['label_version'],
            'image_path':dst.relative_to(R).as_posix(),'image_sha256':sha(dst),'image_size':[w,h],
            'reviewer':request['reviewer'],'reviewer_type':'AI','human_signoff':False,
            'recorded_at':datetime.now(timezone.utc).isoformat(),'review_status':'initial_AI_review_pending_genuine_independent',
            'actual_method':request['actual_method'],'objects':d['objects'],'source_reference_only':e['source_annotations_reference_only'],
            'source_reference_size':e['source_reference_size'],'source_boxes_copied_as_project_truth':False,
            'scene_id':d['scene_id'],'location_basis':d['location_basis'],'evidence_sha256':evidence,'notes':d['notes'],
            'license_status':e['license_status'],'planned_split':d['planned_split'],'official_split':'unassigned',
            'eligible_for_yolo_export':False,'training_release':False}
        lp=out/'labels'/(e['candidate_id']+'.json');save(lp,a);draw=ImageDraw.Draw(im)
        for o in d['objects']:
            color={'body':'lime','ignore':'magenta','hard_negative':'orange'}[o['type']];draw.rectangle(o['bbox_xyxy'],outline=color,width=2)
        im.thumbnail((900,650));im.save(out/'views'/src.name,quality=92)
        entries.append({'candidate_id':e['candidate_id'],'image':'images/'+src.name,'image_sha256':sha(dst),
            'annotation':'labels/'+lp.name,'annotation_sha256':sha(lp),'label_version':a['label_version'],
            'first_pass_reviewer':a['reviewer'],'original_photo_id':e['photo_id'],'source_coco_id':e.get('coco_id'),
            'source_dataset':e.get('source_dataset','COCO'),'source_dataset_image_id':e.get('source_dataset_image_id',e.get('coco_id')),
            'source_variants_must_link':[e['image'],dst.relative_to(R).as_posix()],
            'scene_id':d['scene_id'],'planned_split':a['planned_split'],'official_split':'unassigned'})
        license={'candidate_id':e['candidate_id'],'author':e['author'],'photo_page':e['photo_page'],'title':e['title'],
            'current_flickr_license':e['current_license'],'current_flickr_license_url':e['current_license_url'],
            'eligible_license':True,'conflict_quarantined':False}
        if e.get('source_oembed'):
            license.update(oEmbed_evidence_file=provenance,oEmbed_evidence_sha256=sha(R/provenance))
        else:
            license.pop('current_flickr_license');license.pop('current_flickr_license_url')
            license.update(current_license=e['current_license'],current_license_url=e['current_license_url'],
                share_alike_required_for_shared_photo_derivatives='BY-SA' in e['current_license'],
                metadata_evidence_file=provenance,metadata_evidence_sha256=sha(R/provenance),source='Wikimedia_Commons')
        licenses.append(license)
    mp=out/'manifest.json';save(mp,{'schema_version':'0.1','batch_id':out.name,'immutable':True,
        'recorded_at':datetime.now(timezone.utc).isoformat(),'images':len(entries),'entries':entries,
        'review_round':'initial_only_not_independent','reviewer_type':'AI','human_signoff':False,'training_release':False,
        'source_licenses_file':request['license_audit_output'],'pc_judgment_request':sys.argv[1],'pc_judgment_request_sha256':sha(R/sys.argv[1])})
    for e in entries:tasks.append({'candidate_id':e['candidate_id'],'manifest':mp.relative_to(R).as_posix(),'manifest_sha256':sha(mp),
        'image_sha256':e['image_sha256'],'annotation_sha256':e['annotation_sha256'],'label_version':e['label_version'],
        'scope':request['independent_scope'],'status':'pending_genuine_independent_review'})
    save(out/'independent_tasks.json',{'tasks':tasks,'training_release':False})
    save(R/request['license_audit_output'],{'recorded_at':datetime.now(timezone.utc).isoformat(),'entries':licenses,
        'verified_current_CC_BY':sum(str(e.get('current_flickr_license_url',e.get('current_license_url',''))).startswith('https://creativecommons.org/licenses/by/') for e in licenses),
        'verified_current_CC0':sum(e.get('current_license')=='CC0' for e in licenses),
        'quarantined_license_conflict':0,'training_release':False})
    print(json.dumps({'initial_originals':len(entries),'manifest':mp.relative_to(R).as_posix(),'manifest_sha256':sha(mp)}))

if __name__=='__main__':main()
