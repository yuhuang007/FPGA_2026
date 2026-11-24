"""Incrementally merge remaining-queue whole-image reviews, preserving prior register.

Run intake_independent_reviews.py first.  Accept only the current annotation SHA
and a genuinely checked whole image, never blank queue templates or a stale accept.
PC arbitration requests stay pending; this program does not fabricate resolutions.
"""
import csv, hashlib, json, zipfile
from pathlib import Path
from datetime import datetime, timezone
from integrate_formal_reviews import structural_check

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')

def existing_accept_covers_same_record(entry, review, raw):
    """Retain an already adjudicated accept, never extend it to another record.

    Original first48 accepts can carry optional kind/site questions. Their
    recorded PC body/ignore disposition remains valid on that exact label and
    review; a later disagreement or changed SHA must still revoke it.
    """
    ref=entry.get('independent_review_source',{})
    same_binding=(ref.get('file')==review['source_file']
        and ref.get('sha256')==review['source_file_sha256'] and ref.get('line')==review['line'])
    # Aggregated fillbacks and their immutable part files can contain the exact
    # same signed AI record. Compare the entire record, not just accept/counts.
    if not same_binding and ref.get('file') and ref.get('line'):
        p=R/ref['file']
        if p.exists() and sha(p)==ref.get('sha256'):
            same_binding=json.loads(p.read_text(encoding='utf-8-sig').splitlines()[ref['line']-1])==raw
    return bool(raw.get('decision')=='accept' and entry.get('PC_resolution')
        and entry.get('annotation_sha256')==review['annotation_sha256']
        and same_binding
        and entry.get('original_arbitration_requests')==raw.get('PC_arbitration_required',[]))

def main():
    intake=read(R/'reports/independent_review_intake.json')
    queue=read(R/'review_stage2/remaining_independent_queue/queue_index.json')
    tasks={t['candidate_id']:t for b in queue['batches'] for t in b['tasks']}
    rows={r['sample_id']:r for r in csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig'))}
    fp=R/'review_stage2/final_candidates_r1/manifest.json';final=read(fp)
    entries={e['candidate_id']:e for e in final['entries']}
    lp=R/final['two_AI_review_ledger'];ledger=[json.loads(l) for l in lp.read_text(encoding='utf-8').splitlines() if l]
    keys={(v['candidate_id'],v['independent_review_record']['reviewed_annotation_sha256'],
           v['independent_review_record']['reviewer_id'],v['independent_review_record']['reviewed_at']) for v in ledger}
    latest={};added=[];pending=[];stale=[];new_records=0
    for v in sorted(intake['reviews'],key=lambda v:v['reviewed_at']):
        sid=v['candidate_id']
        # New SHA-bound revisions may also affect the first48. Their original
        # integration is preserved; incrementally consume later real records.
        if sid not in rows:continue
        source=R/v['source_file'];assert sha(source)==v['source_file_sha256']
        raw=json.loads(source.read_text(encoding='utf-8-sig').splitlines()[v['line']-1])
        assert raw.get('bounds_checked') is True or (v['review_scope']=='targeted_changes'
            and v.get('unchanged_semantics_prior_review'))
        if v['review_scope']=='whole_image':
            assert all(raw.get(k) is True for k in ('full_original_checked','omission_search_completed','kind_checked','attributes_checked'))
        else:
            assert v['review_scope']=='targeted_changes' and raw.get('checks_scope') and raw.get('decision_scope')
        assert raw['independent_from_first_pass'] and not raw.get('old_precheck_reused_as_formal_review')
        # Locate precisely the frozen version that was actually reviewed.
        manifests=list((R/'review_stage2/frozen').glob('batch_*/manifest.json'))+list((R/'review_stage2/revisions').glob('*/manifest.json'))
        mp=next(p for p in manifests if sha(p)==v['manifest_sha256']);m=read(mp)
        me=next(e for e in m['entries'] if e['candidate_id']==sid)
        label_path=mp.parent/me['annotation'];a=read(label_path)
        assert sha(label_path)==v['annotation_sha256']==raw['reviewed_annotation_sha256']
        assert sha(mp.parent/me['image'])==v['image_sha256']==a['image_sha256']
        assert a['label_version']==raw['label_version'] and a['reviewer']!=raw['reviewer_id']
        assert not (raw['reviewer_type']=='AI' and raw.get('human_signoff'))
        structural_check(a)
        binding={'file':v['source_file'],'sha256':v['source_file_sha256'],'line':v['line']}
        key=(sid,v['annotation_sha256'],v['reviewer_id'],v['reviewed_at'])
        if key not in keys:
            ledger.append({'candidate_id':sid,'first_pass':{'file':label_path.relative_to(R).as_posix(),
                'sha256':sha(label_path),'reviewer_id':a['reviewer'],'reviewer_type':'AI','reviewed_at':a['recorded_at']},
                'independent_review_source':binding,'independent_review_record':raw})
            keys.add(key);new_records+=1
        if sha(R/rows[sid]['annotation_file'])!=v['annotation_sha256']:
            stale.append({'candidate_id':sid,'reviewed_sha256':v['annotation_sha256'],'decision':v['decision']});continue
        latest[sid]=(v,raw,a,label_path,binding)
    dispositions_path=R/'reports/pc_sample_dispositions.json';dispositions=read(dispositions_path)
    revoked=[]
    for sid in list(entries):
        if sid in rows and sha(R/rows[sid]['annotation_file'])!=entries[sid]['annotation_sha256']:
            revoked.append({'candidate_id':sid,'previous_annotation_sha256':entries[sid]['annotation_sha256'],
                'reason':'Current label revision differs; no prior acceptance inherited.'})
            del entries[sid]
    changed=bool(revoked)
    for sid,(v,raw,a,label_path,binding) in latest.items():
        prior_accept=existing_accept_covers_same_record(entries.get(sid,{}),v,raw)
        if v['decision']!='accept' or (raw.get('PC_arbitration_required') and not prior_accept):
            pending.append({'candidate_id':sid,'decision':v['decision'],'annotation_sha256':v['annotation_sha256'],
                'findings':raw.get('findings',[]),'PC_arbitration_required':raw.get('PC_arbitration_required',[])})
            e=entries.get(sid,{})
            prior=e.get('prior_full_label_review',{})
            body_scope_preserves_this_auxiliary_disagreement=(
                e.get('label_status')=='body_only_confirmed_auxiliary_disagreements_preserved'
                and e.get('annotation_sha256')==v['annotation_sha256']
                and prior.get('file')==v['source_file'] and prior.get('sha256')==v['source_file_sha256']
                and prior.get('line')==v['line'])
            if sid in entries and not body_scope_preserves_this_auxiliary_disagreement:del entries[sid];changed=True
            continue
        if sid in entries and entries[sid]['annotation_sha256']==v['annotation_sha256']:continue
        assert sha(R/a['image_path'])==a['image_sha256']==rows[sid]['sha256']
        bodies=[o['id'] for o in a['objects'] if o['type']=='body'];ignores=[o['id'] for o in a['objects'] if o['type']=='ignore']
        entries[sid]={'candidate_id':sid,'image_sha256':a['image_sha256'],
            'annotation_file':label_path.relative_to(R).as_posix(),'annotation_sha256':sha(label_path),'label_version':a['label_version'],
            'first_pass_reviewer':a['reviewer'],'independent_reviewer':raw['reviewer_id'],
            'independent_review_source':binding,'confirmed_body_ids':bodies,'retained_ignore_ids':ignores,
            'label_status':'body_targets_confirmed_with_ignore_constraints' if bodies else 'ignore_only_explicit_body_training_exclusion',
            'confirmation_scope':('Original whole-image two-AI record plus actual changed-field check; unchanged fields retain their SHA-bound prior checks. No new whole-image omissions certified by this targeted record.'
                if v['review_scope']=='targeted_changes' else 'Exact-version whole-image two-AI review; body attributes unknown remain valid for body detection.'),
            'body_attribute_unknown_is_not_a_detection_blocker':True,'standard_full_image_yolo_label_compatible':bool(bodies) and not ignores,
            'independent_findings':raw.get('findings',[]),'original_arbitration_requests':[],
            'PC_resolution':('All changed fields accepted in a genuine targeted record; original whole-image findings remain preserved in ledger. Source ignores remain export constraints.'
                if v['review_scope']=='targeted_changes' else 'Uncontroversial exact-version whole-image accept; source ignores retained. No blanket human-signature requirement.'),
            'data_blockers':['original group and split verification required']+(['validated clean crop export required'] if bodies and ignores else []),
            'human_signoff':False,'AI_records_represented_as_human':False,'training_release':False}
        if not bodies and not any(d['candidate_id']==sid and d['annotation_sha256']==sha(label_path) for d in dispositions['entries']):
            dispositions['entries'].append({'candidate_id':sid,'annotation_sha256':sha(label_path),'manifest_sha256':raw['manifest_sha256'],
                'action':'excluded_from_training','reason':'No reliable body target; current independent accept confirms conservative exclusion, not negative background.',
                'independent_review_file':v['source_file'],'independent_review_file_sha256':v['source_file_sha256'],
                'independent_reviewer_id':raw['reviewer_id'],'training_approval':False,'human_signoff':False})
        added.append(sid);changed=True
    # Verify archive-source bytes for new accepts; source tags are never enough.
    if added:
        archive=R/'data/s2tld_1080.zip';assert sha(archive)==read(R/'data/archive_provenance.json')['sha256']
        with zipfile.ZipFile(archive) as z:
            names={}
            for name in z.namelist():
                names[name]=name
                try:names[name.encode('cp437').decode('gbk')]=name
                except (UnicodeEncodeError,UnicodeDecodeError):pass
            for sid in added:assert hashlib.sha256(z.read(names[rows[sid]['source_member']])).hexdigest()==rows[sid]['sha256']
    if changed or new_records:
        # Snapshot prior current register without overwriting any frozen batch.
        hist=R/'review_stage2/final_candidates_r1/history';hist.mkdir(exist_ok=True)
        snapshot=hist/(sha(fp)+'.json')
        if not snapshot.exists():snapshot.write_bytes(fp.read_bytes())
        lp.write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in ledger),encoding='utf-8')
        final.update({'recorded_at':datetime.now(timezone.utc).isoformat(),'entries':sorted(entries.values(),key=lambda e:e['candidate_id']),
            'independent_review_completed':intake['completed_independent_review_images'],'final_label_candidates':len(entries),
            'final_body_label_confirmed_images':sum(bool(e['confirmed_body_ids']) for e in entries.values()),
            'confirmed_body_count':sum(len(e['confirmed_body_ids']) for e in entries.values()),
            'confirmed_ignore_only_exclusions':sum(not e['confirmed_body_ids'] for e in entries.values()),
            'standard_full_image_yolo_label_compatible_images':sum(e['standard_full_image_yolo_label_compatible'] for e in entries.values()),
            'two_AI_review_ledger_sha256':sha(lp),'version_bound_review_records_preserved':len(ledger)})
        save(fp,final);save(dispositions_path,dispositions)
        save(R/'reports/formal_review_integration.json',{k:v for k,v in final.items() if k!='entries'})
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'whole_image_results_in_remaining_queue':sum(sid in tasks for sid in latest),
        'current_version_results_all_originals':len(latest),
        'new_confirmed_ids':added,'new_review_ledger_records':new_records,'pending_disagreements':pending,
        'stale_version_results_preserved_not_promoted':stale,'remaining_queue_images':len(tasks),
        'training_releases_created':0,'all_existing_final_entries_preserved_except_new_disagreement':True}
    report['stale_final_confirmations_revoked']=revoked
    save(R/'reports/remaining_review_integration.json',report)
    print(json.dumps({k:report[k] for k in ('whole_image_results_in_remaining_queue','new_confirmed_ids','new_review_ledger_records','remaining_queue_images')}))

if __name__=='__main__':main()
