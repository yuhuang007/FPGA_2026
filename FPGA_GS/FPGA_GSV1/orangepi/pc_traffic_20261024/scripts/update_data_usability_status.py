"""Current compact checkpoint: labels, safe export and scene conditions stay separate."""
from pathlib import Path
from datetime import datetime,timezone
import json
from current_data_holds import current_holds

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads((R/p).read_text(encoding='utf-8'))

def main():
    intake=read('reports/independent_review_intake.json')
    final=read('review_stage2/final_candidates_r1/manifest.json')
    ext=read('reports/external_scene_review_intake.json')
    clean=read('reports/ignore_handling_decision.json')
    ready=read('reports/readiness.json')
    rem=read('reports/remaining_review_integration.json')
    holds,hold_source=current_holds()
    body_scope=read('reports/body_detection_scope_intake.json')
    body_only={e['candidate_id'] for e in final['entries'] if e.get('label_status')=='body_only_confirmed_auxiliary_disagreements_preserved'}
    confirmed_withheld={e['candidate_id'] for e in final['entries'] if e['confirmed_body_ids'] and e['candidate_id'] in holds}
    current_original_confirmed=final['final_body_label_confirmed_images']-len(confirmed_withheld)
    pending_full=set(intake.get('pending_arbitration_ids',[]))
    external_manifests=sorted((R/'review_stage2').glob('external_scene_pilot_r*/manifest.json'))
    external_first=len({e['candidate_id'] for p in external_manifests for e in json.loads(p.read_text(encoding='utf-8'))['entries']})
    licenses={e['candidate_id']:e for p in sorted((R/'reports').glob('external_scene_license_audit_r*.json'))
        for e in json.loads(p.read_text(encoding='utf-8')).get('entries',[])}
    original_first=read('reports/continuation_checkpoint.json')['detailed_first_pass_count']
    counts={'first_pass_completed':original_first+external_first,
        'independent_review_completed':intake['completed_independent_review_images']+ext['independent_review_completed'],
        'final_body_label_confirmed':current_original_confirmed+ext['confirmed_body_label_images'],
        'qualified_all_data_conditions':ready['qualified_images']}
    a={'recorded_at':datetime.now(timezone.utc).isoformat(),'counts':counts,
        'counts_original400':{'first_pass_completed':original_first,'independent_review_completed':intake['completed_independent_review_images'],
            'final_body_label_confirmed':current_original_confirmed,'qualified_all_data_conditions':ready.get('qualified_original400',0)},
        'counts_external':{'first_pass_completed':external_first,'independent_review_completed':ext['independent_review_completed'],
            'final_body_label_confirmed':ext['confirmed_body_label_images'],'qualified_all_data_conditions':ready.get('qualified_external_originals',0),
            'license_verified_current_CC_BY':sum(e['eligible_license'] and 'licenses/by/' in e.get('current_flickr_license_url',e.get('current_license_url','')) for e in licenses.values()),
            'license_verified_current_CC0':sum(e['eligible_license'] and e.get('current_license')=='CC0' for e in licenses.values()),
            'quarantined_license_conflict':sum(e['conflict_quarantined'] for e in licenses.values())},
        'count_scope':'Unique original photo identities; higher/lower resolution variants and crops never add original counts. Final label count means confirmed body-positive images, not conservative ignore-only exclusions.',
        'ignore_route':clean['selected_route'],'actual_validated_clean_crop_originals':clean['actual_visual_and_geometry_validated_originals'],
        'actual_validated_clean_crop_targets':clean['actual_validated_body_targets'],
        'geometry_only_potential_clean_originals':clean['geometry_only_potential_originals'],
        'geometry_only_potential_clean_targets':clean['geometry_only_potential_body_targets'],
        'remaining_original_independent_reviews':400-intake['completed_independent_review_images'],
        'original_current_version_disagreements':intake['current_version_review_disagreement_images'],
        'original_full_label_disagreements_preserved':intake['current_version_review_disagreement_images'],
        'body_only_confirmed_auxiliary_disagreement_ids':sorted(body_only-set(holds)),
        'body_only_confirmed_auxiliary_disagreement_count':len(body_only-set(holds)),
        'full_label_disagreements_without_current_body_confirmation':sorted(pending_full-body_only),
        'body_scope_pending_ids':body_scope['body_scope_pending_ids'],
        'historical_body_confirmations_temporarily_withheld_ids':sorted(confirmed_withheld),
        'active_integrity_hold_ids':sorted(holds),'integrity_hold_source':hold_source,
        'original_targeted_amendments_pending_confirmation':len(intake.get('active_revision_confirmation_pending_ids',[])),
        'pending_annotation_disagreement_ids':intake.get('pending_arbitration_ids',[]),
        'original_final_conservative_exclusions':final['confirmed_ignore_only_exclusions'],
        'review_files_not_counted':intake.get('invalid_or_in_progress_files',[]),
        'external_current_version_disagreements':len(ext['pending_disagreements']),
        'external_body_positive_revision_confirmation_pending_ids':ext.get('pending_body_positive_current_version_confirmation_ids',[]),
        'active_revision_confirmation_pending_ids':intake.get('active_revision_confirmation_pending_ids',[]),
        'annotation_conditions':['Original400 whole-image independent reviews are complete. Resolve current body/ignore disputes with genuine SHA-bound targeted checks; do not redo completed initial reviews.',
            'External initial reviews are counted separately; only current independently accepted body-positive labels count as confirmed.',
            'Accepted conservative ignores remain export constraints, not unreviewed human-signature disputes.',
            'An explicit later body-only accept may confirm body/ignore while preserving earlier auxiliary-emitter disagreements. Auxiliary findings never become body-training attribute truth.',
            'Active newly discovered integrity holds suspend historical confirmations and qualifications until explicitly resolved; frozen evidence remains intact.'],
        'group_conditions':['A/B joint hold is uncertainty, not an assertion of one physical site. Same-scene observations and uncertain route links are separate in data/group_relations_r3.json.',
            'Original400 joint leakage group is train; nine independently audited external source groups are val. Madrid, Newton and CapeTown are separately reserved holdout before fitting. Source-group eligibility is separate from actual safe export and coverage.',
            'Other external scenes remain unassigned until source-group evidence is reviewed. All variants and crops of one source photo inherit the original split.',
            'Reserved holdout sources stay outside tuning/calibration. Actual safe qualified holdout coverage remains small; source reservation alone adds no qualified image. Rochester remains ignore-only excluded; four SC videos remain regression only.'],
        'training_started':False,'training_blocked_checks':[k for k,v in ready['checks'].items() if not v],
        'human_signature_gate_added':False,'historical_frozen_waiting_for_human_wording':'Preserved as history; current two-genuine-AI contract supersedes blanket human-signature wording.',
        'entry_points':{'clean_crop_pilot':clean['active_pilot'],'ignore_route_decision':'reports/ignore_handling_decision.json',
            'all_validated_clean_crop_pilots':[b['manifest'] for b in clean.get('validated_pilot_batches',[])],
            'final_original_labels':'review_stage2/final_candidates_r1/manifest.json','remaining_reviews':'review_stage2/remaining_independent_queue/queue_index.json',
            'external_labels':'review_stage2/external_scene_pilot_r1/manifest.json','external_review_intake':'reports/external_scene_review_intake.json',
            'all_external_initial_batches':[p.relative_to(R).as_posix() for p in external_manifests],
            'source_split_proposal':'data/proposed_source_split_r4.json','group_evidence_types':'data/group_relations_r3.json'}}
    a['entry_points']['source_split_audit_request']='review_stage2/source_split_audit_r1/audit_request.json'
    a['entry_points']['released_original_groups']='data/released_original_groups.json'
    a['entry_points']['latest_source_group_audit']='review_stage2/independent_external_scene_r1/source_group_audit_r3.json'
    a['entry_points']['qualified_originals']=[e['path'] for e in ready.get('qualification_registries',[])]
    a['production_clean_crop_originals']=ready['qualified_images']
    a['production_clean_crop_targets']=ready.get('qualified_targets',0)
    a['qualified_split_counts']=ready.get('qualified_split_counts',{})
    a['qualified_train_val_originals']=sum(ready.get('qualified_split_counts',{}).get(s,0) for s in ('train','val'))
    a['remaining_to_300_train_val_gate']=max(0,300-a['qualified_train_val_originals'])
    a['final_test_status']=ready.get('final_test_status')
    a['continuation']={'do_not_repeat_original_first_pass':True,'pending_PC_adjudications':intake.get('pending_arbitration_ids',[]),
        'await_genuine_change_checks_for_ids':intake.get('active_revision_confirmation_pending_ids',[]),
        'latest_PC_amendments':'review_stage2/revisions/pc_r2_017/manifest.json',
        'independent_reviewer_thread_id':'01a15e4b-f55b-78a1-a8e5-f71350baa433',
        'other_chat_messaging_authorized_by_user':True,
        'next_data_tasks':['Integrate genuine new original400 results and adjudicate current SHA disagreements; do not repeat completed five-source audit.',
            'Expand visually validated safe production crops, preserve immutable release versions and count each original once.',
            'Acquire/review more independent clean pedestrian validation and representative motor/small/distant final-test sources; do not tune on reserved Madrid.',
            'Continue targeted adjudications and current-SHA review intake. Keep existing300-original and all other training gates.']}
    transition=R/'reports/public_dataset_transition_checkpoint.json'
    if transition.exists():
        a['active_workflow']='Reuse compatible published labels; Chinese road scenes primary, foreign supplementary. Historic per-photo review counts remain distinct from published supervision and sampled audits.'
        a['active_workflow_checkpoint']='reports/public_dataset_transition_checkpoint.json'
        a['continuation']['next_data_tasks']=['Follow public dataset checkpoint; finish pinned Chinese S2TLD720 acquisition and sampled source-label compatibility audit.',
            'Native author labels may be reused after actual schema/quality/group checks under updated user instruction; repair actual defects, do not repeat all400 reviews.',
            'Keep source-label counts, true per-image final confirmations and sampled audits distinct. Preserve300 unique train+val originals and isolated validation/test.',
            'Do not import known failed/ignore-bearing old originals as ordinary full-frame backgrounds. Resume authorized training once the selected release meets its actual data conditions.']
        public_ready=R/'reports/public_training_readiness_r1.json'
        progress_path=R/'reports/public_training_progress_r1.json'
        if public_ready.exists():
            selected=read(public_ready)
            a['legacy_individual_review_counts']=dict(counts)
            a['selected_public_training_readiness']=selected
            a['legacy_route_training_blocked_checks']=a['training_blocked_checks']
            a['training_blocked_checks']=[] if selected.get('ready_to_train') else [selected.get('error','selected release not ready')]
            a['remaining_to_300_train_val_gate']=max(0,300-selected.get('unique_train_val_originals',0))
            a['source_supervision_is_not_per_photo_AI_confirmation']=True
        if progress_path.exists():
            actual=read(progress_path)
            a['training_started']=actual.get('optimizer_updates',0)>0
            a['actual_training_progress']=actual
            a['continuation']['next_data_tasks']=['Monitor the existing60epoch run; never launch duplicate training. Read reports/public_training_progress_r1.json.',
                'Integrate SHA-bound China r9-r11 independent reviews. Planned val/test crops remain proposals until reviewed and QA passed.',
                'Keep972-original training release immutable; future dataset versions cannot silently change this fit.',
                'After fit, validate new weights/precision and export classification logits; board candidate verification still required.']
            if actual.get('status')=='completed':
                a['training_completed']=True
                a['recognition_ready_for_production']=False
                a['continuation']['next_data_tasks']=['Training is completed60epochs/3801updates. Do not restart the same run.',
                    'Read reports/public_training_result_r1.json and reports/trained_logits_export_r1.json; PC trained export numeric checks passed.',
                    'Read the failed trained board candidate and reports/trained_fp16_diagnostic_r1.json. Keep original FP32 reference and fixed thresholds while diagnosing.',
                    'China3 current labels now confirmed; source independence and actual safe crops remain unreleased. Preserve all final-test reservations.',
                    'Improve independent road-view/China evaluation before product accuracy claims. Keep stable service/default/m406/FPGA unchanged.']
    for dest in ('reports/current_stage_progress.json','reports/data_usability_checkpoint.json'):
        (R/dest).write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'counts':counts,'original400':a['counts_original400'],'actual_clean_crop_originals':a['actual_validated_clean_crop_originals'],
        'actual_clean_crop_targets':a['actual_validated_clean_crop_targets'],'annotation_disagreements':a['original_current_version_disagreements']+a['external_current_version_disagreements']}))

if __name__=='__main__':main()
