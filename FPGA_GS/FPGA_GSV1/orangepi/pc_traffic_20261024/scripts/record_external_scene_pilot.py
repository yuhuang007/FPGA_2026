"""Persist this turn's actual full-image/zoom review; source labels are references.

This is one AI's initial review, never the independent second review.  Outputs
are immutable once frozen.  Larger Flickr variants remain bound to the same
photo identity as their COCO derivatives; neither variant may cross splits.
"""
from pathlib import Path
import json, shutil, hashlib, re
from datetime import datetime, timezone
from PIL import Image

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
def body(id,b,kind,basis):return {'id':id,'type':'body','bbox_xyxy':b,'kind':kind,'layout':'vertical',
    'kind_basis':basis,'occlusion':'none','truncated':False,'control_relation':'unknown','group_id':None,
    'color_status':'unknown_or_not_assessed_for_body_only','arrow_status':'unknown_or_not_assessed_for_body_only'}
def ignore(id,b,why):return {'id':id,'type':'ignore','bbox_xyxy':b,'kind':'unknown','unknown_reason':'other','reason':why}

def main():
    source=R/'data/external_coco_scene_pilot_r1';m=read(source/'acquisition_manifest.json')
    out=R/'review_stage2/external_scene_pilot_r1'
    if (out/'manifest.json').exists():raise SystemExit('Frozen external pilot exists')
    for d in ('images','labels','views'):(out/d).mkdir(parents=True,exist_ok=True)
    defs={
      8762:{'objects':[
        body('body_1',[94,136,124,233],'motor_vehicle','Visible complete vertical circular-aspect housing with green round illuminated lens; not inferred merely from road position.'),
        body('body_2',[265,168,296,232],'motor_vehicle','Separate complete vertical housing with circular green aspect.'),
        body('body_3',[803,366,832,394],'pedestrian','Illuminated upright hand pictogram in a separate compact pedestrian signal housing; body kind does not depend on mapping orange hand to red/yellow.'),
        ignore('ignore_right_motor',[790,278,829,359],'Red point and housing/backplate visible but precise signal housing boundary under exposure unresolved; do not use entire plate as a fabricated tight body.'),
        ignore('ignore_back_ped',[770,360,800,398],'Rear/side housing next to hand signal, kind and full boundary unresolved.'),
        ignore('ignore_left_back',[127,357,161,413],'Rear/side signal-like housing, no readable front aspects to establish kind.'),
        ignore('ignore_horizon',[0,410,1024,683],'Dense tiny distant lights and dark road: full body existence/kind cannot be individually resolved at native source resolution; conservative excluded area, not ordinary negative background.')],
        'scene':'US_AZ90_Sierra_Vista_photo_4466652187','location_basis':'Photographer title explicitly names AZ-90 and Sierra Vista; visible English street sign and desert mountain road support it.',
        'planned_split':'val','notes':['Whole image and two 3x native-pixel zooms viewed. Streetlamp at top and street signs are background, not signal bodies.','Pedestrian hand body is reliable; color/arrow mapping left unknown.','Second review must verify first-draft body geometry and all ignore boundaries; no acceptance inherited from COCO.']},
      520009:{'objects':[
        body('body_1',[389,262,441,371],'motor_vehicle','Three separately visible circular-aspect hoods in one vertical body; adjacent no-U-turn sign is not an emitter/body.'),
        ignore('ignore_left_edge',[0,325,35,395],'Signal-like rear/side object cut by original left boundary; do not treat as a complete body.'),
        ignore('ignore_rear',[150,407,174,454],'Rear/side small signal housing with no readable front kind.')],
        'scene':'UK_Halifax_Town_Hall_photo_502213596','location_basis':'Flickr keywords explicitly England/Yorkshire/Halifax/West Yorkshire/Calderdale; distinctive town hall matches the actual photo.',
        'planned_split':'val','notes':['Full image plus native-pixel 3x detail viewed. Source COCO bbox includes no-U-turn plate and was not copied.','Detection body retained although green-tinted lower lens cannot safely establish active color; no off label inferred.','Independent reviewer should check exact top/bottom housing limits versus decorative backboard and no-U-turn plate.']},
      577932:{'objects':[
        body('body_1',[131,225,159,292],'motor_vehicle','Visible red circular top aspect and vertical black multi-aspect body; adjacent round restriction sign is a road sign, not another signal.'),
        {'id':'negative_sign','type':'hard_negative','bbox_xyxy':[157,264,177,293],'reason':'Adjacent circular restriction sign outside signal housing; no separate emitter.'}],
        'scene':'UK_Rochester_High_Street_photo_5159956078','location_basis':'Photographer title explicitly Rochester High Street; British streetscape/signage supports UK. Exact site confirmation still requires independent check; Flickr page currently404 while image and licensed oEmbed remain available.',
        'planned_split':'external_test_reserved','notes':['Whole image, larger unmarked source, grid and native-pixel 3x detail viewed.','Only one reliable target draft. Lower dark lens states and tiny pictogram not guessed.','Reserved for future final test; no model/threshold selection or inference performed. This one photo is not a sufficient final generalization test.']},
      534639:{'objects':[ignore('ignore_rail_main',[546,87,570,128],'Housing beside tram track, rail-specific versus road signal kind unresolved; cannot import generic traffic-light source category.'),ignore('ignore_rail_far',[615,172,628,198],'Distant track-side signal too small to establish project target kind.')],
        'scene':'US_Portland_Albina_Mississippi_photo_10190866013','location_basis':'Photographer title explicitly Portland TriMet MAX Albina/Mississippi station.','planned_split':'excluded','notes':['Whole source viewed; no reliable project motor-vehicle/pedestrian body confirmed. Explicit candidate exclusion, not a negative image.']},
      184400:{'objects':[ignore('ignore_truncated',[546,459,588,480],'Only top of a signal-like object at bottom image border; not a complete body.')],
        'scene':'UK_Portsmouth_St_Georges_Road_photo_9326233603','location_basis':'Photographer title names St Georges Road Portsmouth.','planned_split':'quarantine_license_conflict','notes':['Whole source viewed; sole source annotation is image-edge truncated.','COCO historical license id4 conflicts with current Flickr oEmbed CC-BY-NC-SA2.0. Quarantine from all project train/val/test; do not silently substitute CC-BY.']},
      176037:{'objects':[ignore('ignore_behind_bus',[282,131,305,167],'Mostly occluded/distant signal-like object behind bus; existence/kind/bounds unresolved.'),ignore('ignore_right_far',[540,192,568,222],'Tiny distant bright point and pole; cannot establish reliable body class.'),ignore('ignore_distant_street',[185,170,280,234],'Dense far traffic and street lights unresolved; not ordinary negative background.')],
        'scene':'US_NYC_MTA_photo_8140155314','location_basis':'Official MTA author, NYCB title and M5 South Ferry destination visible; precise junction unverified.','planned_split':'excluded','notes':['Whole image viewed; no reliable complete target body at current 640px source. Exclude this pilot sample; a higher source resolution could be re-reviewed as a new version.']}
    }
    entries=[];licenses=[];tasks=[]
    for i in m['entries']:
        cid=i['id'];d=defs[cid];sid=f'coco_scene_{cid:012d}'
        large=source/'larger_sources'/i['file_name'];image=large if cid in (8762,520009,577932) else R/i['local_image']
        dest=out/'images'/i['file_name'];shutil.copyfile(image,dest);w,h=Image.open(dest).size
        for o in d['objects']:
            x,y,u,v=o['bbox_xyxy'];assert 0<=x<u<=w and 0<=y<v<=h
        evidence=[source/'views'/i['file_name']]
        evidence+=sorted((source/'review_views').glob(str(cid)+'_*.png'))+sorted((source/'review_views').glob(str(cid)+'_grid.jpg'))
        ev=[{'path':p.relative_to(R).as_posix(),'sha256':sha(p)} for p in evidence]
        a={'schema_version':'0.1','label_version':'external-PC-AI-r1-20261025','candidate_id':sid,
            'image_path':dest.relative_to(R).as_posix(),'image_sha256':sha(dest),'image_size':[w,h],
            'reviewer':'Codex_PC_AI_external_scene_r1','reviewer_type':'AI','human_signoff':False,
            'recorded_at':datetime.now(timezone.utc).isoformat(),'review_status':'initial_AI_review_pending_genuine_independent',
            'objects':d['objects'],'evidence_sha256':ev,'actual_method':'Unmarked whole source and listed targeted native-pixel enlargements. Grid is coordinate aid, not a source image.',
            'source_reference_only':i['source_traffic_annotations'],'source_reference_size':[i['width'],i['height']],
            'source_boxes_copied_as_project_truth':False,'scene_id':d['scene'],'location_basis':d['location_basis'],
            'planned_split':d['planned_split'],'official_split':'unassigned','notes':d['notes'],
            'license_status':'quarantine_conflict' if cid==184400 else 'verified_CC_BY_2_0_current_oEmbed',
            'eligible_for_yolo_export':False,'training_release':False}
        label=out/'labels'/f'{sid}.json';save(label,a)
        e={'candidate_id':sid,'image':'images/'+i['file_name'],'image_sha256':sha(dest),
            'annotation':'labels/'+label.name,'annotation_sha256':sha(label),'label_version':a['label_version'],
            'first_pass_reviewer':a['reviewer'],'original_photo_id':i['flickr_photo_id'],'source_coco_id':cid,
            'source_variants_must_link':[i['local_image'],dest.relative_to(R).as_posix()],
            'scene_id':d['scene'],'planned_split':d['planned_split'],'official_split':'unassigned'}
        entries.append(e)
        licenses.append({'candidate_id':sid,'coco_license_id':i['license'],'current_flickr_license':i['oembed'].get('license'),
            'current_flickr_license_url':i['oembed'].get('license_url'),'photo_page':i['oembed'].get('web_page'),
            'author':i['oembed']['author_name'],'title':i['oembed']['title'],
            'oEmbed_evidence_file':'data/external_coco_scene_pilot_r1/acquisition_manifest.json',
            'oEmbed_evidence_sha256':sha(source/'acquisition_manifest.json'),'eligible_license':cid!=184400,
            'conflict_quarantined':cid==184400})
    manifest={'schema_version':'0.1','batch_id':'external_scene_pilot_r1','immutable':True,
        'recorded_at':datetime.now(timezone.utc).isoformat(),'images':len(entries),'entries':entries,
        'reviewer_type':'AI','human_signoff':False,'review_round':'initial_only_not_independent',
        'training_release':False,'license_quarantine_ids':['coco_scene_000000184400'],
        'source_licenses_file':'reports/external_scene_license_audit_r1.json'}
    save(out/'manifest.json',manifest)
    for e in entries:
        if e['source_coco_id'] not in (8762,520009,577932):continue
        tasks.append({'candidate_id':e['candidate_id'],'manifest':(out/'manifest.json').relative_to(R).as_posix(),
            'manifest_sha256':sha(out/'manifest.json'),'image_sha256':e['image_sha256'],
            'annotation_sha256':e['annotation_sha256'],'label_version':e['label_version'],
            'scope':'Genuine whole-image omission/kind/bounds review and independent geographic grouping check. Inspect original before first-pass boxes. Unknown colors do not invalidate body.',
            'status':'pending_independent_review_no_signature_created'})
    save(out/'independent_tasks.json',{'tasks':tasks,'reviewer_id':None,'human_signoff':False,'no_filled_review_records_created':True})
    save(R/'reports/external_scene_license_audit_r1.json',{'recorded_at':datetime.now(timezone.utc).isoformat(),
        'entries':licenses,'verified_current_CC_BY_2_0':5,'quarantined_license_conflict':1,
        'annotation_license':'COCO annotations CC-BY4.0; this does not replace per-photo license',
        'official_terms_evidence':'sources/external_scene_research/coco_terms_verified.htm',
        'license_legalcode_evidence':'sources/external_scene_research/cc_by_2_legalcode.html',
        'historical_acquisition_manifest_preserved':True})
    print(json.dumps({'external_initial_review':len(entries),'positive_body_draft_images':3,'body_drafts':5,
        'independent_review_pending':len(tasks),'license_verified_photos':5,'license_conflict_quarantine':1}))

if __name__=='__main__':main()
