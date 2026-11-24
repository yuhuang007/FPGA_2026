"""Refresh the single chosen crop route from existing SHA-bound pilot evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, statistics
from current_data_holds import current_holds

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads((R/p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
def stats(values):return {'min':min(values),'median':statistics.median(values),'max':max(values)}

def main():
    dest='reports/ignore_handling_decision.json';old=read(dest)
    holds,hold_source=current_holds()
    current={e['candidate_id']:e for e in read('review_stage2/final_candidates_r1/manifest.json')['entries']}
    current.update({e['candidate_id']:e for e in read('reports/external_scene_review_intake.json')['entries']})
    crops=[];scan_by_id={};batches=[];stale_pilot_ids=set()
    for version in ('r3','r5','r6','r7','r8'):
        pilot=f'review_stage2/clean_crop_pilot_{version}/manifest.json';m=read(pilot)
        validation=f'reports/clean_crop_validation_{version}.json';visual=f'reports/clean_crop_visual_review_{version}.json'
        v=read(validation);q=read(visual)
        assert v['passed'] and q['passed']
        assert v['pilot_manifest_sha256']==q['pilot_manifest_sha256']==sha(pilot)
        batch_crops=[e for e in m['entries'] if e.get('crop_file')]
        checked={e['candidate_id']:e for e in q['entries'] if e['crop_context_passed_for_detection_pilot']}
        for e in batch_crops:
            if e['candidate_id'] in holds:continue
            if current.get(e['candidate_id'],{}).get('annotation_sha256')!=e['source_annotation_sha256']:
                stale_pilot_ids.add(e['candidate_id']);continue
            assert sha(e['crop_file'])==e['crop_sha256']==checked[e['candidate_id']]['crop_sha256']
            assert sha(e['yolo_label_file'])==e['yolo_label_sha256']
            assert sha(e['source_annotation'])==e['source_annotation_sha256']==current[e['candidate_id']]['annotation_sha256']
            assert sha(e['source_image'])==e['source_image_sha256']
        assert len(batch_crops)==v['originals'] and sum(e['body_count_retained'] for e in batch_crops)==v['targets']
        active_batch_crops=[e for e in batch_crops if e['candidate_id'] not in holds
            and current.get(e['candidate_id'],{}).get('annotation_sha256')==e['source_annotation_sha256']]
        crops.extend(active_batch_crops)
        scan_by_id.update({e['candidate_id']:e for e in m['geometry_only_scan']})
        batches.append({'manifest':pilot,'manifest_sha256':sha(pilot),'validation':validation,'visual_review':visual,
            'originals':len(batch_crops),'targets':v['targets'],'currently_usable_originals':len(active_batch_crops)})
    assert len({e['candidate_id'] for e in crops})==len(crops),'Never count overlapping pilot originals twice'
    pilot_count=len(crops);by_original={e['candidate_id']:e for e in crops};production_batches=[]
    ready=read('reports/readiness.json');qualified=set(ready.get('qualified_original_ids',[]))
    for registry in ready.get('qualification_registries',[]):
        assert sha(registry['path'])==registry['sha256']
        register=read(registry['path']);pm=read(register['production_manifest'])
        assert sha(register['production_manifest'])==register['production_manifest_sha256']
        assert read(register['validation'])['passed'] and read(register['visual_QA'])['passed']
        for e in pm['entries']:
            if e['candidate_id'] not in qualified or e['candidate_id'] not in registry['active_candidate_ids']:continue
            assert sha(e['crop_file'])==e['crop_sha256'] and sha(e['source_annotation'])==e['source_annotation_sha256']
            by_original[e['candidate_id']]=e
        production_batches.append({k:register[k] for k in ('production_manifest','production_manifest_sha256','validation','visual_QA')})
    crops=list(by_original.values())
    scan=list(scan_by_id.values())
    old.update({'recorded_at':datetime.now(timezone.utc).isoformat(),
        'active_pilot':pilot,'active_pilot_sha256':sha(pilot),
        'validated_pilot_batches':batches,'all_batches_use_one_clean_crop_standard_YOLO_route':True,
        'validated_production_batches':production_batches,'pilot_only_originals_before_production_union':pilot_count,
        'actual_validation_counting_rule':'Union by canonical source image ID; production crops replace corresponding pilot variants rather than add new originals.',
        'unfinished_run_not_counted':'review_stage2/clean_crop_pilot_r4/aborted_run.json',
        'superseded_pilots':['review_stage2/clean_crop_pilot_r1/manifest.json','review_stage2/clean_crop_pilot_r2/manifest.json'],
        'actual_visual_and_geometry_validated_originals':len(crops),
        'active_integrity_hold_ids':sorted(holds),'integrity_hold_source':hold_source,
        'historically_validated_pilots_retired_due_to_new_label_SHA':sorted(stale_pilot_ids),
        'actual_validated_body_targets':sum(e['body_count_retained'] for e in crops),
        'geometry_only_potential_originals':sum(e['has_candidate'] for e in scan),
        'geometry_only_potential_body_targets':sum(e['geometrically_retained_bodies'] for e in scan),
        'geometry_scan_originals':len(scan),'confirmed_source_body_targets':sum(e['confirmed_bodies'] for e in scan),
        'geometry_scan_scope':'Historical r3 scan (39 core originals and Arizona), plus selected r5-r8 originals. Not a scan of the whole growing current final-label register.',
        'geometry_scan_source_register_hashes_are_historical':True,
        'individual_pilot_source_labels_still_current_and_sha_verified':True,
        'pilot_area_retained':stats([e['retained_area_fraction'] for e in crops]),
        'pilot_linear_magnification_at_640':stats([e['magnification_vs_full_image_640'] for e in crops]),
        'pilot_body_short_side_pixels_at_640':stats([min(t['at_640_letterbox_size']) for e in crops for t in e['targets']]),
        'actual_validation':validation,'visual_review':visual,
        'actual_retained_class_counts':{kind:sum(t['kind']==kind for e in crops for t in e['targets']) for kind in ('motor_vehicle','pedestrian')},
        'biases':['Pedestrian and independent-scene coverage remain very small. Arizona pedestrian body is not safely retained by its crop. Flint and NYC252219 have confirmed body geometry but no safe context crop and are not exported. Houston retains only1/2 certified bodies.',
            'No negative-only original is represented in this positive pilot.',
            'Repeated S2TLD backgrounds and source watermark persist.',
            'Some crops are mostly sky and remove road context; monitor scale/context bias and weight each original once.',
            'Source-truncated bodies are obstacles; deployment image-edge coverage remains incomplete.'],
        'why_not_custom_ignore_loss':'The whole400 draft geometry snapshot proposes271 originals and511/631 bodies, including only17/28 pedestrian bodies. This substantial loss triggered reports/ignore_loss_feasibility_r1.json. Installed loss, augmentation and validator lack native ignore propagation; an isolated CPU gradient probe validates only algebra, not an end-to-end route. Keep the actually visually/pixel/loader validated clean-crop route as the sole supported first-round pipeline; add reviewed clean originals and report the quantity/context/pedestrian gaps. No custom training entry is maintained.',
        'validation_metric_scope':'Clean-crop body detection only. No ignore pixels are fed as ordinary background; this does not estimate source-full-frame recall or unknown targets.',
        'training_started':False,'training_release':False})
    assessment='reports/ignore_loss_feasibility_r1.json'
    old['ignore_aware_loss_assessment']={'path':assessment,'sha256':sha(assessment),'custom_training_pipeline_implemented':False}
    capacity='reports/clean_crop_capacity_original400.json'
    old['whole400_draft_geometry_capacity']={'path':capacity,'sha256':sha(capacity),
        'all_proposals_are_unapproved_geometry_only':True,
        'source_snapshot_may_precede_new_label_revisions':True}
    # These two ratios referred only to the historical core subset.
    for key in ('source_truncated_body_targets_not_exported','nontruncated_confirmed_bodies_retained_geometrically','nontruncated_confirmed_body_denominator'):
        if key in old:old['historical_core39_'+key]=old.pop(key)
    old['production_crop_policy']['avoid_ignore_padding']=m['rules']['ignore_padding']
    old['production_crop_policy']['minimum_context_pixels']=m['rules']['minimum_context']
    rp=R/'reports/readiness.json'
    if rp.exists():
        ready=read('reports/readiness.json')
        released=read('data/released_original_groups.json');groups=released['groups']
        released_ids={g['candidate_id'] for g in groups}
        old['original_scene_and_split_release_still_required']=any(e['candidate_id'] not in released_ids for e in crops)
        old['released_subset_original_scene_and_split_verified']=True
        old['original_scene_and_split_release_scope']=released['immutable_release']+': '+released['scope']
        old['production_qualified_originals']=ready.get('qualified_images',0)
        old['production_qualified_body_targets']=ready.get('qualified_targets',0)
        old['production_qualification_registries']=ready.get('qualification_registries',[])
        old['production_split_counts']=ready.get('qualified_split_counts',{})
        old['validation_class_counts']={k:sum(t['kind']==k for r in ready.get('qualification_registries',[])
            for e in read(r['path'])['entries'] if e['split']=='val' and e['candidate_id'] in r['active_candidate_ids'] for t in e['targets']) for k in ('motor_vehicle','pedestrian')}
        old['specific_unexported_confirmed_source']='Tashkent Commons149061007: main pedestrian body reliable, but padded lower-ignore and minimum available context conflict. No region removed or rule relaxed; no clean export.'
        old['current_final_test_status']=ready.get('final_test_status')
        old['production_crop_policy']['split_release']='Require immutable source-group release and exact source/label SHA before derivation; validate each export and visually review every changed crop.'
    (R/dest).write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'latest_pilot':pilot,'actual_originals':len(crops),'actual_targets':old['actual_validated_body_targets'],'geometry_scan_originals':len(scan)}))

if __name__=='__main__':main()
