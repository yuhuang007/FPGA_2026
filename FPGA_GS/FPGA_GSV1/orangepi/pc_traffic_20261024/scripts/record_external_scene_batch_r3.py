"""Freeze the six actually viewed r3 photos; never import COCO boxes as truth."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil, re, html
from PIL import Image, ImageDraw
from record_external_scene_batch_r2 import body, ignore

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def negative(oid,b,reason):return dict(id=oid,type='hard_negative',bbox_xyxy=b,reason=reason)

def main():
    source=R/'data/external_scene_candidates_r3';acq=read(source/'acquisition_manifest.json')
    out=R/'review_stage2/external_scene_pilot_r3';assert not out.exists(),'Preserve frozen package'
    for sub in ('images','labels','views','evidence'):(out/sub).mkdir(parents=True,exist_ok=True)
    definitions={
      252219:dict(objects=[
        body('body_ped',[542,76,641,172],'pedestrian','Visible hand and unilluminated walking-person LED matrix share a single square physical housing. Complete square front and edge are visible; color is not a body-class requirement.','single'),
        ignore('ignore_adjacent_side_box',[646,83,692,173],'Separate side-facing dark box beside the square hand signal. Its exact physical association and kind are unresolved; do not silently count it as background or merge its geometry into the frontal body.')],
        scene='US_NYC_construction_photo_3232237447',
        location='Photo page has no location description/keywords. Actual construction signs explicitly mention New York/Manhattan and West 116th Street; exact camera junction unverified. Photographer residence is not scene metadata.',
        notes=['Whole unmarked preview and native3x grid viewed. Independent reviewer must check whether the adjacent dark box is a separate head or part of the visible housing; PC has kept it ignore instead of inventing the association.',
               'The nearby unresolved box may prevent a context-preserving clean crop; a reliable pedestrian body does not imply export eligibility.']),
      338560:dict(objects=[
        body('body_1',[244,160,274,179],'motor_vehicle','Three circular-aspect hoods within one horizontal head, independently separated from the other head on the same arm.','horizontal'),
        body('body_2',[324,159,354,179],'motor_vehicle','Separate horizontal three-circular-aspect head; not one box enclosing both heads or the green road sign.','horizontal'),
        ignore('ignore_near_rear_1',[173,95,219,116],'Near horizontal yellow housing seen from behind; front kind cannot be certified from the road position alone.'),
        ignore('ignore_near_rear_2',[279,92,329,114],'Second rear/oblique yellow housing with unreadable face; kind retained as unknown.'),
        ignore('ignore_right_oblique',[413,187,438,231],'Oblique vertical yellow assembly with small/blurred aspect details, complete front and kind not certified.')],
        scene='US_Houston_downtown_photo_4583091116',
        location='Actual photo meta keywords: usa, texas, houston, downtownhouston. US yellow horizontal road heads and streetscape are consistent. The author profile says Aberdeen, UK, which is explicitly not used as photo location.',
        notes=['Whole unmarked portrait and native1.6x upper-scene grid viewed. Tiny bodies have unknown color/arrow; source category boxes were not copied.',
               'Check both whole foreground and distant upper scene; the hydrant is ordinary foreground context, not a target.']),
      190923:dict(objects=[
        dict(body('body_truncated',[550,0,674,225],'motor_vehicle','Large visible vertical circular-aspect housing continues beyond original top border; only the visible housing is boxed.'),truncated=True),
        ignore('ignore_back_box',[539,226,642,352],'Dark reverse/side box below the top signal; no readable symbol or front establishes pedestrian versus other kind.'),
        ignore('ignore_far_street',[0,390,350,620],'Blurred far street/assemblies cannot support complete individual existence/kind/bounds review at this source resolution.')],
        scene='unverified_US_street_photo_3706332805',
        location='No usable public description/keywords found. ONE WAY sign, hand-style street hardware and streetscape suggest a US setting but no precise site or independent group is certified.',
        notes=['Whole unmarked portrait and native1.5x upper signal grid viewed. The only definite motor head is source-truncated and is an export obstacle, not a complete training positive.',
               'Explicitly exclude from clean-crop data unless another independently reviewed complete target can be evidenced.']),
      253835:dict(objects=[ignore('ignore_unsupported_rail_scene',[0,0,1024,768],
        'Swiss railway platform with track-side railway signals, not a certified project road motor/pedestrian instance. Explicit scene exclusion; never use as ordinary negative background.')],
        scene='CH_railway_photo_9683835627',
        location='Photographer title Waiting for the train, description Zug; actual SBB CFF FFS train/platform and rail signals match a railway setting. Author profile Zurich is not camera GPS.',
        notes=['Whole unmarked source and native3x signal/clock grid viewed. Source traffic-light annotation is not project truth.',
               'No project body-positive draft certified; railway signal ontology must not silently enter the two road classes.']),
      274272:dict(objects=[
        negative('negative_speed_1',[420,223,493,301],'Electronic red-ring 70 speed-limit sign, not a traffic-light body.'),
        negative('negative_speed_2',[621,221,694,299],'Second electronic red-ring 70 speed-limit sign.'),
        ignore('ignore_lane_panels',[328,287,992,377],'Green downward lane-control panels and dark reverse panels are partly behind the bus. Exact complete-body extent and inclusion in this project motor-body ontology need independent adjudication; do not infer complete hidden housings.')],
        scene='AU_Sydney_Harbour_Bridge_photo_8234130537',
        location='Actual photo keywords explicitly sydneyharbourbridge; PREPAY-M20 caption, bridge tower and lane-control installation are consistent. Exact photo location is not inferred from author profile.',
        notes=['Whole unmarked source and native upper-lane-panel grid viewed. Numeric speed signs are hard negatives; lit green arrows are separately acknowledged and not mislabeled as three-round heads.',
               'Conservative temporary exclusion for this source; unresolved lane-panel instance definition remains explicit.']),
      309391:dict(objects=[
        dict(body('body_top_truncated',[162,0,204,77],'motor_vehicle','Visible round-aspect road head continues above original top edge.'),truncated=True),
        body('body_left',[6,225,29,302],'motor_vehicle','Complete narrow frontal three-circular-aspect housing; exclude mounting pole.'),
        body('body_midleft',[182,255,208,310],'motor_vehicle','Complete frontal three-circular-aspect housing, not the sign or adjacent pole.'),
        body('body_mid',[329,235,351,281],'motor_vehicle','Separate frontal multi-circular-aspect housing on middle pole.'),
        body('body_high',[402,102,426,165],'motor_vehicle','Complete vertical three-aspect housing beside NO TURNS signage; circular faces are distinguishable.'),
        body('body_right',[949,294,977,352],'motor_vehicle','Complete frontal three-round housing on the right; exclude separate hand-signal head.'),
        body('body_ped_left',[145,319,168,346],'pedestrian','Visible upright hand pictogram within separate compact pedestrian housing.','single'),
        body('body_ped_right',[975,339,989,367],'pedestrian','Separate small upright hand-signal housing next to right motor head.','single'),
        ignore('ignore_upper_right',[754,0,910,98],'Small upper suspended and rear-facing structures lack reliable individual kind/bounds.'),
        ignore('ignore_far_scene',[440,79,895,264],'Dense small distant signal heads, road/tram corridor and crossing structures: full individual housing instances/kinds not certified; no fabricated three-hole labels.'),
        ignore('ignore_mid_reverse',[311,286,336,320],'Narrow side/rear signal box below the middle front head, unreadable kind.'),
        ignore('ignore_right_cluster',[882,251,942,354],'Oblique/reflected heads and panels left of the confirmed right front housing; complete kinds/bounds unresolved.'),
        ignore('ignore_right_border',[996,337,1023,415],'Large round-aspect head cut by original right boundary; exact source-truncated extent stays excluded.')],
        scene='US_Portland_downtown_photo_5329327710',
        location='Actual photo keywords include oregon, portland, downtown, tri, met; visible TriMet bus/rail-road corridor supports Portland. Possible relation to the already acquired Portland railway source is unresolved: conservatively must-link them for splitting until evidence separates sites.',
        notes=['Whole unmarked source, native coordinate grid and three native3x left/high/right details actually viewed. Every definite readable head is separately recorded; unresolved distant and reverse regions stay ignore.',
               'Many lamps show unusual simultaneous/colored faces; this review creates no emitter/color truth and does not map brightness to off.',
               'Broad distant ignore deliberately restricts export. Safe crop QA must retain all visible certified heads in each chosen region.'])}
    entries=[];licenses=[];tasks=[]
    for e in acq['entries']:
        if not e.get('image'):continue
        assert e['license_status']=='verified_current_oembed_CC_BY'
        d=definitions[e['coco_id']];sid=e['candidate_id'];src=R/e['image'];assert sha(src)==e['image_sha256']
        image=out/'images'/src.name;shutil.copy2(src,image);w,h=e['image_size']
        evidence=[R/e['unmarked_view'],source/'views'/f'{e["coco_id"]}_native_grid.png',R/e['source_oembed']]
        evidence+=sorted((source/'views').glob(f'{e["coco_id"]}_*_native3x.png'))
        if e.get('photo_page_evidence'):evidence.append(R/e['photo_page_evidence'])
        bindings=[]
        for p in evidence:
            dst=out/'evidence'/p.name;shutil.copy2(p,dst);bindings.append({'path':dst.relative_to(R).as_posix(),'sha256':sha(dst)})
        for o in d['objects']:
            x,y,u,v=o['bbox_xyxy'];assert 0<=x<u<=w and 0<=y<v<=h
        page=(R/e['photo_page_evidence']).read_text(encoding='utf-8')
        match=re.search(r'<meta[^>]+name="keywords"[^>]+content="([^"]*)"',page)
        a={'schema_version':'0.1','candidate_id':sid,'label_version':'external-PC-AI-r3-20261025',
            'image_path':image.relative_to(R).as_posix(),'image_sha256':sha(image),'image_size':[w,h],
            'reviewer':'Codex_PC_AI_external_scene_r3','reviewer_type':'AI','human_signoff':False,
            'recorded_at':datetime.now(timezone.utc).isoformat(),'review_status':'initial_AI_review_pending_genuine_independent',
            'actual_method':'Actually viewed unmarked whole photo and saved native detail/grid. Metadata source keywords separated from owner profile location. No source boxes imported.',
            'objects':d['objects'],'source_reference_only':e['source_annotations_reference_only'],
            'source_reference_size':e['source_reference_size'],'source_boxes_copied_as_project_truth':False,
            'scene_id':d['scene'],'location_basis':d['location'],'photo_keywords':html.unescape(match.group(1)) if match else None,
            'evidence_sha256':bindings,'notes':d['notes'],'license_status':e['license_status'],
            'planned_split':'unassigned_pending_group_audit' if e['coco_id'] in (252219,338560,309391) else 'excluded_pending_specific_resolution',
            'official_split':'unassigned','eligible_for_yolo_export':False,'training_release':False}
        lp=out/'labels'/f'{sid}.json';save(lp,a)
        im=Image.open(image).convert('RGB');draw=ImageDraw.Draw(im)
        for o in a['objects']:
            color={'body':'lime','ignore':'magenta','hard_negative':'orange'}[o['type']]
            draw.rectangle(o['bbox_xyxy'],outline=color,width=2);draw.text((o['bbox_xyxy'][0],o['bbox_xyxy'][1]),o['id'],fill=color,stroke_width=1,stroke_fill='black')
        im.thumbnail((900,650));im.save(out/'views'/image.name,quality=92)
        entries.append({'candidate_id':sid,'image':'images/'+image.name,'image_sha256':sha(image),'annotation':'labels/'+lp.name,
            'annotation_sha256':sha(lp),'label_version':a['label_version'],'first_pass_reviewer':a['reviewer'],
            'original_photo_id':e['photo_id'],'source_coco_id':e['coco_id'],'scene_id':d['scene'],
            'source_variants_must_link':[e['image'],image.relative_to(R).as_posix()],
            'planned_split':a['planned_split'],'official_split':'unassigned'})
        licenses.append({'candidate_id':sid,'author':e['author'],'photo_page':e['photo_page'],'title':e['title'],
            'current_flickr_license':e['current_license'],'current_flickr_license_url':e['current_license_url'],
            'oEmbed_evidence_file':e['source_oembed'],'oEmbed_evidence_sha256':e['source_oembed_sha256'],
            'eligible_license':True,'conflict_quarantined':False})
    mp=out/'manifest.json';save(mp,{'schema_version':'0.1','batch_id':'external_scene_pilot_r3','immutable':True,
        'recorded_at':datetime.now(timezone.utc).isoformat(),'images':len(entries),'entries':entries,
        'review_round':'initial_only_not_independent','reviewer_type':'AI','human_signoff':False,'training_release':False,
        'source_licenses_file':'reports/external_scene_license_audit_r3.json'})
    for e in entries:tasks.append({'candidate_id':e['candidate_id'],'manifest':mp.relative_to(R).as_posix(),'manifest_sha256':sha(mp),
        'image_sha256':e['image_sha256'],'annotation_sha256':e['annotation_sha256'],'label_version':e['label_version'],
        'scope':'Actual independent body-only whole-image omissions/kind/bounds review. Check NYC adjacent box, Houston separate horizontal heads, Portland all small/side heads, Sydney lane-panel ontology and original truncation. Unknown color is no exclusion reason. Source group observations are not split release.',
        'status':'pending_genuine_independent_review'})
    save(out/'independent_tasks.json',{'tasks':tasks,'training_release':False})
    save(R/'reports/external_scene_license_audit_r3.json',{'recorded_at':datetime.now(timezone.utc).isoformat(),
        'entries':licenses,'verified_current_CC_BY':len(licenses),'quarantined_license_conflict':0,'training_release':False})
    print(json.dumps({'actual_initial_external_originals':len(entries),'draft_bodies':sum(sum(o['type']=='body' for o in d['objects']) for d in definitions.values()),
        'independent_reviews_created':0,'manifest_sha256':sha(mp)}))

if __name__=='__main__':main()
