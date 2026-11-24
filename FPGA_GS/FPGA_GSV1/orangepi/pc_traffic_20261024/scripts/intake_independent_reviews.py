"""Bind genuine external review records to immutable images, labels and manifests.

Accepting a draft is never promoted to a training release. Original feedback is read-only.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import hashlib,json

R=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8'))

def validate_preserved_semantics(old,new,fields,kind_checked,attributes_checked,bounds_checked=True,checks_scope=None):
    """Unchanged semantics may retain their real prior check; changed ones may not."""
    assert fields and all(isinstance(f,str) and f for f in fields)
    old_objects={o['id']:dict(o) for o in old['objects']}
    new_objects={o['id']:dict(o) for o in new['objects']}
    additions=set(new_objects)-set(old_objects)
    assert set(old_objects)<=set(new_objects),'Object removal requires an explicit broader check'
    assert {f for f in fields if '.' not in f}==additions,'Undeclared new object'
    if additions:
        assert bounds_checked,'New ignore/negative instances need real bounds checks'
        for oid in additions:
            o=new_objects[oid]
            assert o['type'] in ('ignore','hard_negative'),'New positives need a broader check'
            if not kind_checked:
                # A global motor/ped-kind flag may truthfully remain false when
                # the reviewer explicitly checked only an unresolved ignore's
                # existence/type/reason/bounds. No class assertion is inherited
                # for the new object and the producer's false flag is preserved.
                assert o['type']=='ignore' and o.get('kind','unknown')=='unknown'
                assert set(o)<={'id','type','kind','bbox_xyxy','reason','unknown_reason'}
                assert isinstance(checks_scope,list),'New ignore/negative instances need real kind and bounds checks'
                scopes=[s for s in checks_scope if isinstance(s,dict) and s.get('object_id')==oid]
                assert len(scopes)==1
                s=scopes[0]
                assert s.get('type')=='ignore' and s.get('bbox_xyxy')==o['bbox_xyxy']
                checked_fields=set(s.get('fields',[]))
                assert {'type','bbox_xyxy','reason'}<=checked_fields
                assert checked_fields & {'existence_of_unresolved_visible_patch','existence_of_unresolved_visible_assembly'}
            if not attributes_checked:
                assert not set(o)&{'state','color_readable','symbol','arrow_direction','occlusion','truncated'},'New attributes need an actual attribute check'
    if not bounds_checked:
        assert {k:o['bbox_xyxy'] for k,o in old_objects.items()}=={k:o['bbox_xyxy'] for k,o in new_objects.items()},'Changed bounds require an actual bounds check'
    if not kind_checked:
        assert all(old_objects[k].get(f)==new_objects[k].get(f)
            for k in old_objects for f in ('type','kind','kind_basis','parent_id')),'Kind/association changes require a new kind check'
    if not attributes_checked:
        assert all(f in additions or f.endswith('.bbox_xyxy') for f in fields),'Changed attributes require an actual attribute check'
    for field in fields:
        if field in additions:continue
        oid,key=field.rsplit('.',1)
        assert oid in old_objects and oid in new_objects
        old_objects[oid].pop(key,None);new_objects[oid].pop(key,None)
    assert old_objects=={k:v for k,v in new_objects.items() if k not in additions},'Undeclared object changes cannot inherit prior review'

def review_file_time(path):
    try:
        return min(datetime.fromisoformat(json.loads(line)['reviewed_at']).timestamp()
            for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip())
    except (OSError,ValueError,KeyError,TypeError):return float('inf')

def preserved_check_is_traceable(record,records,check,seen=None):
    """Follow validated exact-version links without manufacturing new check flags."""
    assert check in ('kind','attributes','bounds')
    key=(record['source_file'],record['source_file_sha256'],record['line'],record['annotation_sha256'])
    seen=set() if seen is None else set(seen)
    if key in seen:return False
    seen.add(key)
    if record.get(check+'_recertified_this_record') is True:return True
    link=record.get('unchanged_semantics_prior_review')
    if not link:return False
    prior=next((p for p in records if p['candidate_id']==record['candidate_id']
        and p['image_sha256']==record['image_sha256']
        and all(p.get(k)==link.get(k) for k in ('source_file','source_file_sha256','line','annotation_sha256'))),None)
    return bool(prior and preserved_check_is_traceable(prior,records,check,seen))

def main():
    manifests={}
    manifest_paths=list((R/'review_stage2/frozen').glob('batch_*/manifest.json'))+list((R/'review_stage2/revisions').glob('**/manifest.json'))
    for p in manifest_paths:
        m=read(p);manifests[sha(p)]=(p.parent,m,{e['candidate_id']:e for e in m['entries']})
    records=[];invalid=[];files=[]
    attestation_path=R/'review_stage2/independent_codex_board_r2/remaining_review_attestations.json'
    attestations=read(attestation_path).get('entries',[]) if attestation_path.exists() else []
    for p in sorted((R/'review_stage2/independent_codex_board_r2').glob('*.jsonl'),key=review_file_time):
        raw=p.read_bytes();file_hash=hashlib.sha256(raw).hexdigest();accepted=[]
        try:
            payloads=[json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
            for n,a in enumerate(payloads,1):
                batch,m,entries=manifests[a['manifest_sha256']];e=entries[a['candidate_id']]
                assert a['image_sha256']==e['image_sha256']==sha(batch/e['image'])
                assert a['reviewed_annotation_sha256']==e['annotation_sha256']==sha(batch/e['annotation'])
                label=read(batch/e['annotation'])
                assert a['label_version']==e['label_version']==label['label_version']
                assert a['reviewer_type'] in ('AI','human') and a['reviewer_id']!=e['first_pass_reviewer']
                assert a['independent_from_first_pass'] is True and a['reviewed_at'] and a['actual_method']
                targeted=a.get('omission_search_completed') is False
                assert isinstance(a.get('bounds_checked'),bool)
                if not targeted:assert a['bounds_checked'] is True
                geometry_followup=False;prior_semantics_review=None
                if targeted:
                    assert label.get('supersedes_annotation_sha256') and a.get('checks_scope') and a.get('decision_scope')
                    assert any(r['candidate_id']==a['candidate_id'] and r['image_sha256']==a['image_sha256']
                               and r['review_scope']=='whole_image' for r in records), 'Targeted change check requires preserved genuine original whole-image review'
                    if not all(a.get(k) is True for k in ('kind_checked','attributes_checked','bounds_checked')):
                        # Carry only unchanged semantic fields from an actual
                        # exact-version prior review. Occlusion-only amendments
                        # can truthfully check attributes without rechecking kind.
                        fields=label['affected_fields']
                        old_entry=next((base/e['annotation'] for base,_,es in manifests.values() for e in es.values()
                                        if e['candidate_id']==a['candidate_id'] and e['annotation_sha256']==label['supersedes_annotation_sha256']),None)
                        assert old_entry is not None
                        validate_preserved_semantics(read(old_entry),label,fields,
                            a.get('kind_checked') is True,a.get('attributes_checked') is True,a.get('bounds_checked') is True,a.get('checks_scope'))
                        prior=next((r for r in records if r['candidate_id']==a['candidate_id']
                            and r['annotation_sha256']==label['supersedes_annotation_sha256']
                            and r['image_sha256']==a['image_sha256']
                            and all(a.get(k+'_checked') is True or preserved_check_is_traceable(r,records,k)
                                for k in ('kind','attributes','bounds'))
                            and r['decision'] in ('accept','needs_modify','uncertain')),None)
                        assert prior is not None,'Missing genuine prior semantic check for '+a['candidate_id']
                        assert sha(R/prior['source_file'])==prior['source_file_sha256']
                        prior_semantics_review={k:prior[k] for k in ('source_file','source_file_sha256','line','annotation_sha256')}
                        geometry_followup=all(f.endswith('.bbox_xyxy') for f in fields)
                else:
                    assert a.get('full_original_checked') is True
                    assert a.get('omission_search_completed') is True
                    assert a.get('kind_checked') is True and a.get('attributes_checked') is True
                assert not (a['reviewer_type']=='AI' and a.get('human_signoff'))
                assert a['decision'] in ('accept','needs_modify','uncertain','reject','exclude')
                if targeted:
                    no_inherited_acceptance=a.get('old_review_acceptance_inherited') is False
                    if not no_inherited_acceptance and a.get('previous_review_sha256'):
                        # A real producer's same-version supplement can complete
                        # an earlier record. Bind the original declaration instead
                        # of inventing or rewriting a missing field.
                        previous=R/a['previous_review']
                        assert sha(previous)==a['previous_review_sha256']
                        linked=[json.loads(l) for l in previous.read_text(encoding='utf-8-sig').splitlines() if l.strip()]
                        prior=next(x for x in linked if x['candidate_id']==a['candidate_id']
                            and x['reviewed_annotation_sha256']==a['reviewed_annotation_sha256'])
                        assert prior['reviewer_id']==a['reviewer_id'] and prior['image_sha256']==a['image_sha256']
                        assert prior['manifest_sha256']==a['manifest_sha256']
                        no_inherited_acceptance=prior.get('old_review_acceptance_inherited') is False
                    assert no_inherited_acceptance or (geometry_followup and a.get('previous_needs_modify_preserved') is True)
                else:
                    if a.get('old_precheck_reused_as_formal_review') is not False:
                        assert a.get('old_precheck_reused_as_formal_review') is None
                        # The independent producer may supply a missing contract
                        # field in a separate SHA-bound attestation. Preserve the
                        # original JSONL and never fill or sign it on their behalf.
                        assert any(t.get('source_file','').replace('\\','/')==p.relative_to(R).as_posix()
                            and t.get('source_file_sha256')==file_hash and t.get('reviewer_id')==a['reviewer_id']
                            and t.get('old_precheck_reused_as_formal_review') is False and t.get('attested_at')
                            for t in attestations), 'Missing independent SHA-bound no-precheck-reuse attestation'
                assert a.get('viewed_evidence')
                for ev in a['viewed_evidence']:
                    assert sha(R/ev['path'])==ev['sha256']
                accepted.append({'candidate_id':a['candidate_id'],'batch_id':m['batch_id'],
                    'manifest_sha256':a['manifest_sha256'],'image_sha256':a['image_sha256'],
                    'annotation_sha256':a['reviewed_annotation_sha256'],'label_version':a['label_version'],
                    'reviewer_id':a['reviewer_id'],'reviewer_type':a['reviewer_type'],
                    'human_signoff':a.get('human_signoff',False),'decision':a['decision'],
                    'review_scope':'targeted_changes' if targeted else 'whole_image',
                    'whole_image_omission_search_recertified':not targeted,
                    'geometry_only_followup':geometry_followup,
                    'unchanged_semantics_prior_review':prior_semantics_review,
                    'kind_recertified_this_record':a.get('kind_checked') is True,
                    'attributes_recertified_this_record':a.get('attributes_checked') is True,
                    'bounds_recertified_this_record':a.get('bounds_checked') is True,
                    'checks_scope':a.get('checks_scope'),'decision_scope':a.get('decision_scope'),
                    'supplemental_no_precheck_reuse_attestation':(
                        {'file':attestation_path.relative_to(R).as_posix(),'sha256':sha(attestation_path)}
                        if not targeted and a.get('old_precheck_reused_as_formal_review') is None else None),
                    'training_approval':a.get('training_approval',False),'reviewed_at':a['reviewed_at'],
                    'source_file':str(p.relative_to(R)).replace('\\','/'),'source_file_sha256':file_hash,'line':n,
                    'findings':a.get('findings',[]),'PC_arbitration_required':a.get('PC_arbitration_required',[]),
                    'grouping_review':a.get('grouping_review'),'corrected_annotation_file':a.get('corrected_annotation_file')})
            # Fail closed if the producer changed a file during validation.
            assert sha(p)==file_hash
            records.extend(accepted);files.append({'file':str(p.relative_to(R)).replace('\\','/'),'sha256':file_hash,'records':len(accepted)})
        except (AssertionError,KeyError,ValueError,OSError) as error:
            invalid.append({'file':str(p.relative_to(R)).replace('\\','/'),'error':type(error).__name__+': '+str(error),'counted':False})
    # Keep all source records; deduplicate counts for the same reviewer/label version.
    latest={}
    for a in sorted(records,key=lambda x:x['reviewed_at']):
        latest[(a['candidate_id'],a['annotation_sha256'],a['reviewer_id'])]=a
    active=list(latest.values());ids={a['candidate_id'] for a in active}
    for issue in invalid:
        completions=[]
        for review in active:
            source=R/review['source_file']
            raw=json.loads(source.read_text(encoding='utf-8-sig').splitlines()[review['line']-1])
            previous=raw.get('previous_review','').replace('\\','/')
            if previous==issue['file'] and raw.get('previous_review_sha256')==sha(R/issue['file']):
                completions.append({'file':review['source_file'],'sha256':review['source_file_sha256'],
                    'line':review['line'],'annotation_sha256':review['annotation_sha256']})
        issue['completed_by_validated_supplements']=completions
        issue['unresolved_contract_blocker']=not bool(completions)
    first_pass={p.stem:read(p) for p in (R/'review_stage2/first_pass').glob('*.json')}
    current_paths={p.stem:p for p in (R/'review_stage2/first_pass').glob('*.json')}
    revision_paths=[p for p in (R/'review_stage2/revisions').glob('**/s2tld1080_*.json') if read(p).get('supersedes_annotation_sha256')]
    for p in sorted(revision_paths,key=lambda p:datetime.fromisoformat(read(p)['recorded_at'])):
        current_paths[read(p)['candidate_id']]=p
    current_hashes={sid:sha(p) for sid,p in current_paths.items()}
    revisions=[]
    for p in (R/'review_stage2/revisions').glob('**/s2tld1080_*.json'):
        a=read(p)
        if a.get('supersedes_annotation_sha256'):
            h=sha(p);confirmed=any(x['candidate_id']==a['candidate_id'] and x['annotation_sha256']==h and x['decision']=='accept' for x in active)
            revisions.append({'candidate_id':a['candidate_id'],'revision_file':str(p.relative_to(R)).replace('\\','/'),
                'revision_sha256':h,'supersedes_annotation_sha256':a['supersedes_annotation_sha256'],
                'affected_fields':a.get('affected_fields',[]),'reconfirmation_completed':confirmed,
                'is_active_version':h==current_hashes[a['candidate_id']],
                'old_acceptance_inherited':False})
    ambiguous={sid for sid,p in current_paths.items() if any(o['type']=='ignore' for o in read(p)['objects'])}
    final_path=R/'review_stage2/final_candidates_r1/manifest.json'
    finalized={(e['candidate_id'],e['annotation_sha256']) for e in read(final_path)['entries']} if final_path.exists() else set()
    feedback_issues={a['candidate_id'] for a in active if a['annotation_sha256']==current_hashes[a['candidate_id']]
                     and (a['candidate_id'],a['annotation_sha256']) not in finalized
                     and (a['decision'] in ('needs_modify','uncertain','reject') or a['PC_arbitration_required'])}
    # An accepted conservative ignore is a data-export constraint, not an open
    # annotation disagreement or a request for a human signature.
    pending=set(feedback_issues)
    revision_pending={a['candidate_id'] for a in revisions if a['is_active_version'] and not a['reconfirmation_completed']}
    excluded=set()
    disposition_path=R/'reports/pc_sample_dispositions.json'
    if disposition_path.exists():
        for d in read(disposition_path)['entries']:
            if d['action']!='excluded_from_training':continue
            matches=[a for a in active if a['candidate_id']==d['candidate_id'] and a['annotation_sha256']==d['annotation_sha256']]
            assert matches and all(a['decision']=='accept' for a in matches)
            assert sha(R/d['independent_review_file'])==d['independent_review_file_sha256']
            # A later label invalidates an old exclusion just as it invalidates acceptance.
            if current_hashes[d['candidate_id']]!=d['annotation_sha256']:continue
            assert not any(o['type']=='body' for o in read(current_paths[d['candidate_id']])['objects'])
            excluded.add(d['candidate_id'])
    pending-=excluded
    result={'recorded_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'completed_independent_review_images':len(ids),'version_bound_review_records':len(active),
        'draft_decision_counts':dict(Counter(a['decision'] for a in active if a['review_scope']=='whole_image')),
        'targeted_change_decision_counts':dict(Counter(a['decision'] for a in active if a['review_scope']=='targeted_changes')),
        'human_signoff_images':len({a['candidate_id'] for a in active if a['human_signoff']}),
        'first_pass_ambiguous_images':len(ambiguous),'feedback_issue_images':len(feedback_issues),
        'current_version_review_disagreement_images':len({a['candidate_id'] for a in active
            if a['annotation_sha256']==current_hashes[a['candidate_id']] and a['decision'] in ('needs_modify','uncertain','reject')
            and (a['candidate_id'],a['annotation_sha256']) not in finalized}),
        'pending_arbitration_images':len(pending),'pending_arbitration_ids':sorted(pending),
        'active_revision_confirmation_pending_ids':sorted(revision_pending),
        'retained_ignore_export_constraint_ids':sorted(ambiguous-excluded),
        'independent_review_pending_ids':sorted(set(current_paths)-ids),
        'explicitly_excluded_ids':sorted(excluded),
        'invalid_or_in_progress_files':invalid,'validated_source_files':files,'reviews':active,
        'revisions':revisions,'training_releases_created':0,
        'scope':'Draft accept is not training approval. Changed annotation SHA requires fresh version-bound confirmation; original signatures and findings remain preserved.'}
    (R/'reports/independent_review_intake.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['completed_independent_review_images','draft_decision_counts','pending_arbitration_images','human_signoff_images','training_releases_created']}))

if __name__=='__main__': main()
