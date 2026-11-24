"""Freeze three actually viewed source photos and PC body-only drafts, not truth."""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, shutil
from PIL import Image, ImageDraw

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
def body(oid,b,kind,basis,layout='vertical'):
    return {'id':oid,'type':'body','bbox_xyxy':b,'kind':kind,'layout':layout,'kind_basis':basis,
        'occlusion':'none','truncated':False,'control_relation':'unknown',
        'color_status':'unknown_or_not_assessed_for_body_only','arrow_status':'unknown_or_not_assessed_for_body_only'}
def ignore(oid,b,why):return {'id':oid,'type':'ignore','bbox_xyxy':b,'kind':'unknown','unknown_reason':'other','reason':why}

def main():
    source=R/'data/external_scene_candidates_r2';acquisition=read(source/'acquisition_manifest.json')
    out=R/'review_stage2/external_scene_pilot_r2';assert not out.exists(),'Preserve published batch'
    for sub in ('images','labels','views','evidence'):(out/sub).mkdir(parents=True,exist_ok=True)
    definitions={
        15272:{'objects':[body('body_1',[66,62,440,219],'motor_vehicle',
            'One aligned horizontal signal-head assembly of three circular-aspect modules on a continuous mount. Draft instance granularity requires independent confirmation against project body definition; not copied from the generic COCO class.', 'horizontal')],
            'scene':'JP_Tokyo_Tateishi_Sakura_Street_photo_8584364941',
            'location':'Photographer public description: at Tateishi Sakura Street, Katsushika, Tokyo; tags Japan/Tokyo/Tateishi. Actual cherry-lined street and horizontal three-round head are consistent; no exact GPS inferred.',
            'notes':['Whole unmarked image and native2x head enlargement actually viewed. Three lens modules are treated as one draft assembly; independent reviewer must explicitly verify instance granularity.',
                'No additional definite signal body or uncertain signal region seen in whole image. No off/color ground truth is created.']},
        183246:{'objects':[body('body_1',[661,108,687,214],'motor_vehicle',
            'Separate frontal narrow housing with one red luminous circular aspect and multiple lower circular chambers; no fixed three-lens assumption or off labels.'),
            ignore('ignore_adjacent_side_heads',[698,157,770,241],'Side/back signal assemblies; exact individual front extent/kind unresolved.'),
            ignore('ignore_construction_heads',[340,240,595,450],'Many side/back signal-like assemblies under installation; unresolved complete-body count and kind, not ordinary background.'),
            ignore('ignore_lower_context',[0,450,1024,819],'Distant road signals and reflective vehicle/window/mirror context cannot be individually resolved confidently.'),
            ignore('ignore_window_reflections',[760,0,1024,450],'Oblique window and reflected signal-like shapes; source/reflection identity and complete body geometry unresolved.')],
            'scene':'US_Flint_Miller_Ballenger_photo_2469205788',
            'location':'Photographer description explicitly names intersection of Miller and Ballenger Road in Flint, Michigan; construction scene matches. Precise GPS unverified.',
            'notes':['Whole unmarked image and native3x foreground head enlargement actually viewed.',
                'Likely difficult to retain sufficient clean context around the one reliable frontal body; do not force safe-crop approval. Installation/reflection coverage differs from routine roads.']},
        301376:{'objects':[body('body_1',[539,434,578,533],'motor_vehicle','Three separate circular-aspect hoods in one complete vertical head; exclude shared pole and the separate hand-signal unit below.'),
            body('body_ped',[538,543,571,613],'pedestrian','Upright illuminated hand establishes pedestrian signal. Native5x view shows a lower dark chamber in the same pedestrian housing, which is included; no off state inferred.'),
            ignore('ignore_left_rear_heads',[79,0,232,300],'Large side/rear assemblies near original upper boundary; front kind and complete instance granularity not certified.'),
            ignore('ignore_far_street',[570,615,682,865],'Far signal-like points and dense road objects cannot support individual reliable existence/kind/bounds labels at this source resolution.')],
            'scene':'US_Chicago_North_Avenue_photo_2718408461',
            'location':'Photographer title North Avenue and public tags Chicago/Illinois/Old Town; English streetscape, restaurant, Latin School sign and US hand signal support distinct US setting. Exact junction unverified.',
            'notes':['Whole unmarked source, native3x head grid and native5x hand housing viewed. Both pedestrian chambers included.',
                'Rear/side and far unresolved regions stay ignore. Proximity may prevent a context-preserving crop of both confirmed bodies; geometry must decide before export.']}}
    entries=[];licenses=[];tasks=[]
    for e in acquisition['entries']:
        assert e['license_status']=='verified_current_oembed_CC_BY'
        sid=e['candidate_id'];d=definitions[e['coco_id']];impath=R/e['image'];assert sha(impath)==e['image_sha256']
        image=out/'images'/impath.name;shutil.copy2(impath,image);w,h=e['image_size']
        evidence=[R/e['unmarked_view'],source/'views'/f'{e["coco_id"]}_context_grid.png']
        if e['coco_id']==301376:evidence.append(source/'views/301376_ped_native5x.png')
        evidence+=[R/e['source_oembed'],source/'provenance'/f'{e["coco_id"]}_page.html']
        bindings=[]
        for p in evidence:
            dst=out/'evidence'/p.name;shutil.copy2(p,dst);bindings.append({'path':dst.relative_to(R).as_posix(),'sha256':sha(dst)})
        for o in d['objects']:
            x,y,u,v=o['bbox_xyxy'];assert 0<=x<u<=w and 0<=y<v<=h
        a={'schema_version':'0.1','candidate_id':sid,'label_version':'external-PC-AI-r2-20261025',
            'image_path':image.relative_to(R).as_posix(),'image_sha256':sha(image),'image_size':[w,h],
            'reviewer':'Codex_PC_AI_external_scene_r2','reviewer_type':'AI','human_signoff':False,
            'recorded_at':datetime.now(timezone.utc).isoformat(),'review_status':'initial_AI_review_pending_genuine_independent',
            'actual_method':'Actual unmarked whole source and saved native-pixel enlargements; source/photo metadata read separately. Source boxes not copied.',
            'objects':d['objects'],'source_reference_only':e['source_annotations_reference_only'],
            'source_reference_size':[e['coco_metadata']['width'],e['coco_metadata']['height']],
            'source_boxes_copied_as_project_truth':False,'scene_id':d['scene'],'location_basis':d['location'],
            'evidence_sha256':bindings,'notes':d['notes'],'license_status':'verified_current_oembed_CC_BY',
            'planned_split':'val_candidate_pending_audit','official_split':'unassigned','eligible_for_yolo_export':False,'training_release':False}
        lp=out/'labels'/f'{sid}.json';save(lp,a)
        im=Image.open(image).convert('RGB');draw=ImageDraw.Draw(im)
        for o in a['objects']:draw.rectangle(o['bbox_xyxy'],outline='lime' if o['type']=='body' else 'magenta',width=2)
        im.thumbnail((900,650));vp=out/'views'/image.name;im.save(vp,quality=92)
        entries.append({'candidate_id':sid,'image':'images/'+image.name,'image_sha256':sha(image),
            'annotation':'labels/'+lp.name,'annotation_sha256':sha(lp),'label_version':a['label_version'],
            'first_pass_reviewer':a['reviewer'],'original_photo_id':e['photo_id'],'source_coco_id':e['coco_id'],
            'source_variants_must_link':[e['image'],image.relative_to(R).as_posix()],
            'scene_id':d['scene'],'planned_split':a['planned_split'],'official_split':'unassigned'})
        licenses.append({'candidate_id':sid,'author':e['author'],'photo_page':e['photo_page'],'title':e['title'],
            'current_flickr_license':e['current_license'],'current_flickr_license_url':e['current_license_url'],
            'oEmbed_evidence_file':e['source_oembed'],'oEmbed_evidence_sha256':e['source_oembed_sha256'],
            'eligible_license':True,'conflict_quarantined':False})
    mp=out/'manifest.json';save(mp,{'schema_version':'0.1','batch_id':'external_scene_pilot_r2','immutable':True,
        'recorded_at':datetime.now(timezone.utc).isoformat(),'images':len(entries),'entries':entries,
        'review_round':'initial_only_not_independent','reviewer_type':'AI','human_signoff':False,'training_release':False,
        'source_licenses_file':'reports/external_scene_license_audit_r2.json'})
    for e in entries:tasks.append({'candidate_id':e['candidate_id'],'manifest':mp.relative_to(R).as_posix(),'manifest_sha256':sha(mp),
        'image_sha256':e['image_sha256'],'annotation_sha256':e['annotation_sha256'],'label_version':e['label_version'],
        'scope':'Actual independent whole-image body/omissions/geometry review; attributes deliberately unassessed. Check Japanese head instance definition, Chicago full two-chamber pedestrian housing and Flint unresolved assemblies/reflections. Source observations are not split release.',
        'status':'pending_genuine_independent_review'})
    save(out/'independent_tasks.json',{'tasks':tasks,'training_release':False})
    save(R/'reports/external_scene_license_audit_r2.json',{'recorded_at':datetime.now(timezone.utc).isoformat(),
        'entries':licenses,'verified_current_CC_BY_2_0':3,'quarantined_license_conflict':0,'training_release':False})
    print(json.dumps({'frozen_initial_external_originals':3,'draft_bodies':4,'independent_reviews_created':0,'manifest_sha256':sha(mp)}))

if __name__=='__main__':main()
