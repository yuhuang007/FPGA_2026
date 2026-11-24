"""Report exact-version label progress separately from unchanged training gates."""
import csv, json, hashlib
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
from current_data_holds import current_holds

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    rows=list(csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig')))
    final=read(R/'review_stage2/final_candidates_r1/manifest.json')
    confirmed={e['candidate_id']:e for e in final['entries']}
    intake=read(R/'reports/independent_review_intake.json')
    ready=read(R/'reports/readiness.json')
    qualified=set(ready.get('qualified_original_ids',[]))
    holds,hold_source=current_holds()
    release_path=R/'data/released_original_groups.json'
    released={g['candidate_id']:g for g in read(release_path)['groups']} if release_path.exists() else {}
    route=read(R/'reports/ignore_handling_decision.json')
    safe_crops={}
    batches=route.get('validated_pilot_batches',[{'manifest':route['active_pilot'],'visual_review':route['visual_review'],'validation':route['actual_validation']}])
    for batch in batches:
        crop_path=R/batch['manifest'];crop_visual_path=R/batch['visual_review'];crop_validation_path=R/batch['validation']
        assert all(p.exists() for p in (crop_path,crop_visual_path,crop_validation_path))
        cm=read(crop_path);cv=read(crop_visual_path);cg=read(crop_validation_path)
        assert cv['pilot_manifest_sha256']==cg['pilot_manifest_sha256']==sha(crop_path)
        assert cv['passed'] and cg['passed']
        checked={v['candidate_id']:v for v in cv['entries'] if v['crop_context_passed_for_detection_pilot']}
        for v in cm['entries']:
            if v.get('crop_file') and v['candidate_id'] in checked:
                assert sha(R/v['crop_file'])==v['crop_sha256']==checked[v['candidate_id']]['crop_sha256']
                assert sha(R/v['yolo_label_file'])==v['yolo_label_sha256']
                assert v['candidate_id'] not in safe_crops,'Do not multiply-count original photos'
                safe_crops[v['candidate_id']]=v
    items=[];counts=Counter()
    for row in rows:
        path=R/row['annotation_file'];a=read(path);h=sha(path)
        reviews=[v for v in intake['reviews'] if v['candidate_id']==row['sample_id'] and v['annotation_sha256']==h]
        e=confirmed.get(row['sample_id']);e=e if e and e['annotation_sha256']==h else None
        historical_confirmation=e
        if row['sample_id'] in holds:e=None
        excluded=row['sample_id'] in intake['explicitly_excluded_ids']
        label_blockers=[];data_blockers=[]
        if not e and not excluded:
            label_blockers.append('exact_version_final_label_confirmation_pending')
        if row['sample_id'] in holds:
            label_blockers.append('newly_discovered_signal_region_integrity_hold')
        crop=safe_crops.get(row['sample_id'])
        crop=crop if crop and crop['source_annotation_sha256']==h and crop['source_image_sha256']==row['sha256'] else None
        if e and e['confirmed_body_ids'] and e['retained_ignore_ids'] and not crop:
            data_blockers.append('validated_clean_crop_required_not_ordinary_background')
        if crop and row['sample_id'] not in qualified:
            data_blockers.append('pilot_crop_must_be_rederived_after_original_split_release')
        if not excluded:
            if row['license_status']!='verified':data_blockers.append('license_unverified')
            if row['clean_original']!='verified':data_blockers.append('clean_original_review_pending')
            g=released.get(row['sample_id'],{})
            if g.get('group_status')!='verified':data_blockers.append('group_independence_unverified')
            if g.get('official_split') not in ('train','val','holdout'):data_blockers.append('official_split_unassigned')
            if g and g.get('annotation_sha256')!=h:data_blockers.append('group_release_label_binding_requires_new_version')
            if g.get('redundant_capture_of'):data_blockers.append('same_capture_reencoded_redundant')
        if row['sample_id'] in qualified:
            assert e and not label_blockers
            data_blockers=[]  # Readiness revalidated real production export + quality supplement.
        counts.update(label_blockers+data_blockers)
        items.append({'candidate_id':row['sample_id'],'active_annotation':path.relative_to(R).as_posix(),
            'active_annotation_sha256':h,'current_version_independent_review_records':len(reviews),
            'final_body_label_confirmed':bool(e and e['confirmed_body_ids']),
            'confirmed_body_ids':e['confirmed_body_ids'] if e else [],
            'validated_clean_crop_pilot':bool(crop),
            'validated_crop_target_count':crop['body_count_retained'] if crop else 0,
            'confirmed_conservative_exclusion':excluded,
            'body_color_or_arrow_unknown_is_not_a_detection_blocker':True,
            'body_only_confirmed_auxiliary_disagreements_preserved':bool(e and e.get('label_status')=='body_only_confirmed_auxiliary_disagreements_preserved'),
            'historical_confirmation_temporarily_withheld':bool(historical_confirmation and row['sample_id'] in holds),
            'label_blockers':label_blockers,'data_blockers':data_blockers,
            'human_signoff_required':False,'human_signoff_fabricated':False})
        items[-1]['qualified_all_sample_data_conditions']=row['sample_id'] in qualified
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),
        'first_pass_completed':len(rows),'independent_review_completed':intake['completed_independent_review_images'],
        'final_label_candidates':final['final_label_candidates'],
        'final_body_label_confirmed_images':sum(i['final_body_label_confirmed'] for i in items),
        'integrity_hold_source':hold_source,'active_integrity_hold_ids':sorted(holds),
        'explicitly_excluded_images':len(intake['explicitly_excluded_ids']),
        'qualified_all_data_conditions':ready.get('qualified_original400',0),
        'qualified_external_originals':ready.get('qualified_external_originals',0),
        'validated_clean_crop_pilot_originals':sum(i['validated_clean_crop_pilot'] for i in items),
        'validated_clean_crop_pilot_targets':sum(i['validated_crop_target_count'] for i in items),
        'blocker_counts':dict(counts),'human_signature_gate_added':False,
        'method':'Confirm body targets on exact reviewed SHA. Unknown color/arrow does not invalidate reliable body targets. Preserve ignore regions; ordinary YOLO export cannot turn them into background. Training counts remain subject to existing group/split/quantity gates.',
        'items':items}
    (R/'reports/incremental_sample_eligibility.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('first_pass_completed','independent_review_completed','final_label_candidates','final_body_label_confirmed_images','explicitly_excluded_images','qualified_all_data_conditions')}))


if __name__=='__main__':main()
