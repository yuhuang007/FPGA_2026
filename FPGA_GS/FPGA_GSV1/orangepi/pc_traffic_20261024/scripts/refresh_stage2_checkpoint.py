"""Refresh factual continuation state without granting review/training approval."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv, hashlib, json, shutil, subprocess, sys

R=Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    intake_run=subprocess.run([sys.executable,str(R/'scripts/intake_independent_reviews.py')],capture_output=True,text=True,encoding='utf-8',check=True)
    intake=read(R/'reports/independent_review_intake.json')
    labels={p.stem:(p,read(p)) for p in (R/'review_stage2/first_pass').glob('*.json')}
    batches=[]
    for folder in sorted((R/'review_stage2/frozen').glob('batch_*')):
        if not (folder/'manifest.json').is_file(): continue
        proc=subprocess.run([sys.executable,str(R/'scripts/validate_review_batch.py'),str(folder)],
                            capture_output=True,text=True,encoding='utf-8',check=True)
        result=json.loads(proc.stdout)
        save(R/f'reports/review_{folder.name}_integrity.json',result)
        manifest=read(folder/'manifest.json')
        for entry in manifest['entries']:
            assert sha(labels[entry['candidate_id']][0])==entry['annotation_sha256']
        batches.append({'batch_id':folder.name,'images':manifest['count'],
                        'manifest_sha256':result['manifest_sha256'],'integrity_passed':True,
                        'fillback':str((folder/'review_fillback.jsonl').relative_to(R)).replace('\\','/')})
    path=R/'data/candidates.csv'
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig',newline='')))
    if not (R/'reports/candidates_before_resume.csv').exists():
        shutil.copy2(path,R/'reports/candidates_before_resume.csv')
    for row in rows:
        if row['sample_id'] not in labels: continue
        p,label=labels[row['sample_id']]
        assert sha(R/row['image_path'])==row['sha256']==label['image_sha256']
        current_path=p
        revisions=[a for a in intake['revisions'] if a['candidate_id']==row['sample_id']]
        if revisions:
            current_path=max((R/a['revision_file'] for a in revisions),key=lambda p:read(p)['recorded_at'])
        current_sha=sha(current_path)
        matching=[a for a in intake['reviews'] if a['candidate_id']==row['sample_id'] and a['annotation_sha256']==current_sha]
        if row['sample_id'] in intake.get('explicitly_excluded_ids',[]):
            row['review_status']='excluded'
            row['reviewer_2']=max(matching,key=lambda a:a['reviewed_at'])['reviewer_id']
            row['annotation_file']=str(current_path.relative_to(R)).replace('\\','/')
        if current_path!=p and row.get('annotation_file')!=str(current_path.relative_to(R)).replace('\\','/'):
            # A revision changes the reviewed SHA; the old release/signature cannot survive it.
            row['review_status']='pending_version_bound_reconfirmation'
            row['reviewer_2']=''
        # Draft accept never creates approved/excluded status.
        if row['review_status'] not in ('approved','excluded'):
            row['annotation_file']=str(current_path.relative_to(R)).replace('\\','/')
            row['reviewer_1']=label['reviewer']
            if matching:
                row['reviewer_2']=max(matching,key=lambda a:a['reviewed_at'])['reviewer_id']
                row['review_status']='reviewed_pending_arbitration_or_release'
            else:
                row['reviewer_2']=''
                row['review_status']='pending_version_bound_reconfirmation' if revisions else 'pending_independent_review'
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    proc=subprocess.run([sys.executable,str(R/'scripts/check_readiness.py')],
                        capture_output=True,text=True,encoding='utf-8')
    assert proc.returncode in (0,2),proc.stderr
    readiness=read(R/'reports/readiness.json')
    formal_path=R/'reports/formal_review_integration.json'
    formal=read(formal_path) if formal_path.exists() else {}
    active_reviewed=set();active_accepted=set()
    for row in rows:
        if not row.get('annotation_file'): continue
        current_sha=sha(R/row['annotation_file'])
        matching=[a for a in intake['reviews'] if a['candidate_id']==row['sample_id'] and a['annotation_sha256']==current_sha]
        if matching: active_reviewed.add(row['sample_id'])
        if any(a['decision']=='accept' for a in matching): active_accepted.add(row['sample_id'])
    old=R/'reports/independent_review_status.json'
    backup=R/'reports/independent_review_status_before_resume.json'
    if not backup.exists(): shutil.copy2(old,backup)
    status=read(old)
    if 'not_modified' in status:
        status['historical_precheck_not_modified']=status.pop('not_modified')
    for key in ['partial_first_pass_visual_note_count_at_check','partial_visual_note_sha256']:
        if key in status:
            status['historical_precheck_'+key]=status.pop(key)
    # This task performs first-pass continuation only. Never invent a second reviewer.
    status.update({'recorded_at':now,'candidate_count':len(rows),
        'completed_second_pass_label_reviews':intake['completed_independent_review_images'],
        'current_version_independent_reviews':len(active_reviewed),
        'current_version_draft_accepts':len(active_accepted),
        'final_body_label_confirmed_images':formal.get('final_body_label_confirmed_images',0),
        'final_label_candidates':formal.get('final_label_candidates',0),
        'label_review_contract':'Two genuine independent AI review records are allowed for label confirmation; AI is not human signoff. Group/split/ignore-safe export are separate data conditions; no new blanket human-signature gate.',
        'draft_decision_counts':intake['draft_decision_counts'],
        'pending_arbitration_images':intake['pending_arbitration_images'],
        'explicitly_excluded_images':len(intake.get('explicitly_excluded_ids',[])),
        'reconfirmation_queue_path':'review_stage2/reconfirmation_queue.json',
        'human_signoff_images':intake['human_signoff_images'],
        'first_pass_label_files_at_check':len(labels),
        'remaining_detailed_first_pass_images':len(rows)-len(labels),
        'approved_for_training':readiness['qualified_images'],
        'frozen_first_pass_images':sum(b['images'] for b in batches),
        'frozen_batches':batches,
        'status':'immutable_first_pass_batches_available_awaiting_genuine_independent_review',
        'next_action':'Review frozen originals independently before labels; save genuine version-bound fillback separately. First-pass continuation is not an independent second pass.',
        'historical_status_path':str(backup.relative_to(R)).replace('\\','/'),
        'training_approval_inferred_from_integrity':False})
    save(old,status)
    observations=[{'candidate_id':sid,'annotation_sha256':sha(p),**label['group_observation']}
                  for sid,(p,label) in sorted(labels.items()) if 'group_observation' in label]
    save(R/'reports/resume_group_review.json',{'recorded_at':now,'reviewer_type':'AI',
        'human_signoff':False,'approved_for_split':False,
        'existing_87_pair_review_preserved':'reports/near_duplicate_review.json',
        'observations':observations})
    remaining=[int(row['sample_id'].rsplit('_',1)[1]) for row in rows if row['sample_id'] not in labels]
    save(R/'reports/continuation_checkpoint.json',{'recorded_at':now,
        'candidate_count':len(rows),'detailed_first_pass_count':len(labels),
        'detailed_first_pass_indices':sorted(int(x.rsplit('_',1)[1]) for x in labels),
        'remaining_detailed_first_pass_count':len(remaining),
        'next_detailed_first_pass_index':remaining[0] if remaining else None,
        'next_detailed_first_pass_id':next((row['sample_id'] for row in rows if row['sample_id'] not in labels),None),
        'remaining_detailed_first_pass_ids':[row['sample_id'] for row in rows if row['sample_id'] not in labels],
        'frozen_batches':batches,'completed_independent_label_reviews':status['completed_second_pass_label_reviews'],
        'current_version_independent_reviews':len(active_reviewed),
        'current_version_draft_accepts':len(active_accepted),
        'final_body_label_confirmed_images':formal.get('final_body_label_confirmed_images',0),
        'final_label_candidates':formal.get('final_label_candidates',0),
        'explicitly_excluded_images':len(intake.get('explicitly_excluded_ids',[])),
        'pending_arbitration_images':intake['pending_arbitration_images'],
        'reconfirmation_pending_ids':[a['candidate_id'] for a in intake['revisions'] if a.get('is_active_version',True) and not a['reconfirmation_completed']],
        'approved_for_training':readiness['qualified_images'],'ready_to_train':readiness['ready_to_train'],
        'blocked_checks':[k for k,v in readiness['checks'].items() if not v],
        'full_image_completeness_is_not_implied_by_first_pass':True,
        'deployment_contract':'board_validation/logits_candidate_r1/reports/export_contract.json',
        'required_post_training':'Export trained classification logits, apply CPU stable sigmoid exactly once, rerun same-SHA board numerical checks; untrained preflight is not trained-weight approval.',
        'scope':'PC dataset/reports/scripts only; no stable service, m406 default or FPGA changes',
        'completed_work_reports':[name for name in [
            'reports/active_label_structure_audit.json','reports/reviewed_scene_link_audit.json',
            'reports/review_group_components_audit.json','reports/incremental_sample_eligibility.json',
            'reports/supplementary_review_evidence_index.json'] if (R/name).exists()],
        'latest_frozen_manifest':('review_stage2/frozen/'+batches[-1]['batch_id']+'/manifest.json') if batches else None,
        'next_phase':'Continue first-pass IDs listed here.' if remaining else
            'Initial review complete. Integrate genuine current-SHA independent fillback, confirm only changed versions, finish clean-crop export and evidenced group/split audit. Two genuine AI records allowed; no blanket human signature gate. No training while readiness is false.',
        'resume_instruction':'Skip existing first_pass labels and published batches. Prepare only a few full images and targeted crops; record actual viewed decisions, keep uncertainties pending, freeze new batch IDs without overwrites.'})
    print(json.dumps({'detailed_first_pass':len(labels),'frozen':sum(b['images'] for b in batches),
                      'next_index':remaining[0] if remaining else None,'ready_to_train':readiness['ready_to_train']}))

if __name__=='__main__': main()
