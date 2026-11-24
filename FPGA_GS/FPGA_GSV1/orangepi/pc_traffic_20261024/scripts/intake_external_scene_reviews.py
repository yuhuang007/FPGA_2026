"""Validate independent external pilot fillback against exact frozen versions.

Separate from the existing400-image intake. Unknown attributes never invalidate
reliable body geometry. No modified label inherits an earlier acceptance.
"""
from pathlib import Path
import json, hashlib
from datetime import datetime,timezone
from intake_independent_reviews import validate_preserved_semantics, review_file_time

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')

def validate_body_scope_clarification(raw, prior, label):
    """A source-bound optional wording note can clarify an existing accept only."""
    assert prior['decision']=='accept' and prior['raw_record']['independent_from_first_pass'] is True
    assert raw['record_kind']=='same_SHA_prior_scope_clarification_not_new_visual_review'
    assert raw['reviewer_type']=='AI' and not raw.get('human_signoff')
    assert raw['reviewer_id']!=label['reviewer']
    assert raw['candidate_id']==prior['candidate_id']==label['candidate_id']
    assert raw['reviewed_annotation_sha256']==prior['annotation_sha256']
    assert raw['image_sha256']==label['image_sha256']
    assert raw['manifest_sha256']==prior['raw_record']['manifest_sha256']
    assert raw['label_version']==label['label_version']
    assert raw['same_annotation_SHA_as_prior'] is True and raw['decision']=='accept'
    assert raw['decision_unchanged'] is True and raw['original_decision_changed'] is False
    assert raw['label_change_required'] is False and raw['new_visual_review_performed'] is False
    assert raw['new_sample_count']==0 and raw['unique_new_originals_reviewed']==0
    assert raw['optional_note_is_required_for_body_or_ignore_acceptance'] is False
    assert raw['has_unresolved_actual_body_or_ignore_annotation_dispute'] is False
    assert raw['PC_arbitration_required']==[]
    # Never let a clarification silently clear additional actual findings.
    assert prior['raw_record']['PC_arbitration_required']==[raw['prior_text_exact']]
    assert raw['prior_text_exact'].startswith('Optional documentation clarification:')
    assert raw['clarified_prior_field']=='PC_arbitration_required[0]'
    assert all(o['type'] not in ('lens','emitter') for o in label['objects'])

def main():
    manifest_paths=list((R/'review_stage2').glob('external_scene_pilot_r*/manifest.json'))
    manifest_paths+=list((R/'review_stage2/external_scene_revisions').glob('*/manifest.json'))
    manifests={sha(p):(p,read(p)) for p in manifest_paths}
    current={}
    for p,m in sorted(manifests.values(),key=lambda x:x[1]['recorded_at']):
        for e in m['entries']:current[e['candidate_id']]=(p,e)
    reviews=[];invalid=[];latest={};clarifications=[]
    folder=R/'review_stage2/independent_external_scene_r1';folder.mkdir(exist_ok=True)
    for p in sorted(folder.glob('*.jsonl'),key=review_file_time):
        if p.name.startswith('clarification_'):
            continue  # Scope notes are validated after original reviews; never counted as new reviews.
        h=sha(p);checked=[]
        try:
            for line_number,line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(),1):
                if not line.strip():continue
                raw=json.loads(line);mp,m=manifests[raw['manifest_sha256']]
                e=next(e for e in m['entries'] if e['candidate_id']==raw['candidate_id'])
                a=read(mp.parent/e['annotation']);image=mp.parent/e['image']
                assert sha(image)==raw['image_sha256']==e['image_sha256']==a['image_sha256']
                assert sha(mp.parent/e['annotation'])==raw['reviewed_annotation_sha256']==e['annotation_sha256']
                assert a['label_version']==raw['label_version']==e['label_version']
                assert raw['reviewer_id']!=a['reviewer'] and raw['independent_from_first_pass'] is True
                assert raw['reviewer_type']=='AI' and not raw.get('human_signoff')
                assert raw.get('bounds_checked') is True
                targeted=raw.get('omission_search_completed') is False
                if targeted:
                    assert a.get('supersedes_annotation_sha256') and raw.get('checks_scope')
                    assert isinstance(raw.get('full_original_checked'),bool)
                    assert any(v['candidate_id']==e['candidate_id'] and v['raw_record']['image_sha256']==a['image_sha256']
                               and v['raw_record'].get('omission_search_completed') is True for v in reviews)
                    assert raw.get('old_review_acceptance_inherited') is not True
                    if raw.get('kind_checked') is not True:
                        ancestor_sha=a['supersedes_annotation_sha256'];visited=set()
                        previous=None
                        while previous is None:
                            assert ancestor_sha not in visited, 'Cyclic label version chain'
                            visited.add(ancestor_sha)
                            previous=next((v for v in reviews if v['candidate_id']==e['candidate_id']
                                and v['annotation_sha256']==ancestor_sha),None)
                            if previous is not None:break
                            # Some historical PC geometry drafts were superseded
                            # before review. Trace their unchanged semantics all
                            # the way to a genuine record; never infer acceptance.
                            def label_version(digest):
                                pp,ee=next((pp,ee) for pp,mm in manifests.values() for ee in mm['entries']
                                    if ee['candidate_id']==e['candidate_id'] and ee['annotation_sha256']==digest)
                                assert sha(pp.parent/ee['annotation'])==digest
                                return read(pp.parent/ee['annotation'])
                            intermediate=label_version(ancestor_sha)
                            ancestor_sha=intermediate['supersedes_annotation_sha256']
                            older=label_version(ancestor_sha)
                            assert older['image_sha256']==intermediate['image_sha256']==a['image_sha256']
                            assert all(f.endswith('.bbox_xyxy') for f in intermediate['affected_fields'])
                            validate_preserved_semantics(older,intermediate,intermediate['affected_fields'],False,False,True,None)
                        old=read(R/previous['label_file'])
                        validate_preserved_semantics(old,a,a['affected_fields'],False,
                            raw.get('attributes_checked') is True,True,raw['checks_scope'])
                else:
                    assert raw.get('full_original_checked') is True and raw.get('omission_search_completed') is True and raw.get('kind_checked') is True
                if raw.get('attributes_checked') is not True:
                    # These external labels deliberately contain no emitter/color
                    # ground truth. A truthful body-only review may leave color
                    # checks false; do not manufacture attribute certification.
                    assert raw.get('checks_scope')
                    assert not any(o['type'] in ('emitter','lens') for o in a['objects'])
                    assert all(o.get('color_status')=='unknown_or_not_assessed_for_body_only'
                               for o in a['objects'] if o['type']=='body')
                assert raw.get('old_precheck_reused_as_formal_review') is not True
                assert raw['actual_method'] and raw['reviewed_at'] and raw['viewed_evidence']
                for ev in raw['viewed_evidence']:assert sha(R/ev['path'])==ev['sha256']
                assert raw['decision'] in ('accept','needs_modify','uncertain','reject','exclude')
                w,hsize=a['image_size'];ids={o['id'] for o in a['objects']};assert len(ids)==len(a['objects'])
                for o in a['objects']:
                    x,y,u,v=o['bbox_xyxy'];assert 0<=x<u<=w and 0<=y<v<=hsize
                    if o['type']=='body':assert o['kind'] in ('motor_vehicle','pedestrian')
                item={'candidate_id':e['candidate_id'],'annotation_sha256':e['annotation_sha256'],
                    'label_file':(mp.parent/e['annotation']).relative_to(R).as_posix(),
                    'source_file':p.relative_to(R).as_posix(),'source_file_sha256':sha(p),'line':line_number,
                    'reviewer_id':raw['reviewer_id'],'decision':raw['decision'],'reviewed_at':raw['reviewed_at'],
                    'review_scope':'targeted_changes' if targeted else 'whole_image',
                    'raw_record':raw,'is_current_version':current[e['candidate_id']][1]['annotation_sha256']==e['annotation_sha256']}
                checked.append(item)
            assert sha(p)==h
            reviews+=checked
        except (AssertionError,KeyError,ValueError,StopIteration,OSError) as exc:
            invalid.append({'file':p.relative_to(R).as_posix(),'error':type(exc).__name__+': '+str(exc),'counted':False})
    for p in sorted(folder.glob('clarification_*.jsonl')):
        try:
            for line_number,line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(),1):
                if not line.strip():continue
                raw=json.loads(line)
                if raw.get('record_kind')=='same_SHA_prior_scope_clarification_not_new_visual_review':
                    ref=raw['prior_review_evidence'];assert sha(R/ref['path'])==ref['sha256']
                    matching=[v for v in reviews if v['source_file']==ref['path']
                        and v['candidate_id']==raw['candidate_id']
                        and v['annotation_sha256']==raw['reviewed_annotation_sha256']]
                    assert len(matching)==1
                    v=matching[0];a=read(R/v['label_file'])
                    validate_body_scope_clarification(raw,v,a)
                    for ev in raw['prior_full_viewed_evidence_not_newly_viewed']:
                        assert sha(R/ev['path'])==ev['sha256']
                    clarifications.append({'candidate_id':raw['candidate_id'],
                        'annotation_sha256':v['annotation_sha256'],
                        'original_review':v['source_file'],'original_review_sha256':v['source_file_sha256'],
                        'source_file':p.relative_to(R).as_posix(),'source_file_sha256':sha(p),'line':line_number,
                        'scope':'Same-SHA existing body-only accept clarified: optional wording is not an actual body/ignore dispute.',
                        'new_review_count':0})
                    continue
                original=R/raw['original_review']
                assert sha(original)==raw['original_review_sha256']
                matching=[v for v in reviews if v['source_file']==original.relative_to(R).as_posix()
                    and v['candidate_id']==raw['candidate_id'] and v['annotation_sha256']==raw['reviewed_annotation_sha256']]
                assert len(matching)==1
                v=matching[0];a=read(R/v['label_file'])
                assert raw['image_sha256']==a['image_sha256']
                assert raw['manifest_sha256']==v['raw_record']['manifest_sha256']
                assert raw['label_version']==a['label_version']
                assert raw['independent_from_first_pass'] is True and raw['reviewer_id']!=a['reviewer']
                assert raw['reviewer_type']=='AI' and not raw.get('human_signoff')
                assert raw['current_annotation_disagreement_pending'] is False
                assert raw['future_ontology_condition_only'] is True and raw['clarification']
                assert v['decision']=='accept', 'Scope note cannot reverse a rejection/uncertainty/modification'
                # The producer explicitly confines this accepted ignore-only case
                # to future ontology expansion; no new labels/checks are inferred.
                assert not any(o['type']=='body' for o in a['objects'])
                clarifications.append({'candidate_id':raw['candidate_id'],'annotation_sha256':v['annotation_sha256'],
                    'original_review':v['source_file'],'original_review_sha256':v['source_file_sha256'],
                    'source_file':p.relative_to(R).as_posix(),'source_file_sha256':sha(p),'line':line_number,
                    'scope':'Current accepted ignore-only label has no pending annotation dispute; future ontology exclusion retained.',
                    'new_review_count':0})
        except (AssertionError,KeyError,ValueError,StopIteration,OSError) as exc:
            invalid.append({'file':p.relative_to(R).as_posix(),'error':type(exc).__name__+': '+str(exc),'counted':False})
    for v in sorted(reviews,key=lambda v:v['reviewed_at']):
        if v['is_current_version']:latest[v['candidate_id']]=v
    confirmed=[];pending=[]
    for sid,v in latest.items():
        raw=v['raw_record'];a=read(R/v['label_file'])
        scope_clarified=any(c['candidate_id']==sid and c['annotation_sha256']==v['annotation_sha256']
            and c['original_review_sha256']==v['source_file_sha256'] for c in clarifications)
        if v['decision']!='accept' or (raw.get('PC_arbitration_required') and not scope_clarified):
            pending.append(v);continue
        assert not a['license_status'].startswith('quarantine')
        confirmed.append({'candidate_id':sid,'image_sha256':a['image_sha256'],'annotation_file':v['label_file'],
            'annotation_sha256':v['annotation_sha256'],'label_version':a['label_version'],
            'first_pass_reviewer':a['reviewer'],'independent_reviewer':v['reviewer_id'],
            'confirmed_body_ids':[o['id'] for o in a['objects'] if o['type']=='body'],
            'retained_ignore_ids':[o['id'] for o in a['objects'] if o['type']=='ignore'],
            'independent_review_source':{k:v[k] for k in ('source_file','source_file_sha256','line')},
            'scene_id':a['scene_id'],'official_split':'unassigned','training_release':False,'human_signoff':False})
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'independent_review_completed':len({v['candidate_id'] for v in reviews}),
        'current_version_independent_review_completed':len(latest),'confirmed_body_label_images':sum(bool(e['confirmed_body_ids']) for e in confirmed),
        'confirmed_body_count':sum(len(e['confirmed_body_ids']) for e in confirmed),'entries':confirmed,
        'pending_disagreements':pending,'reviews':reviews,'invalid_or_in_progress_files':invalid,
        'qualification_requires_current_label_sha_clean_export_and_group_split':True,'qualified_all_data_conditions':0,
        'AI_records_represented_as_human':False,'training_release':False}
    report['validated_scope_clarifications_not_new_reviews']=clarifications
    report['pending_body_positive_current_version_confirmation_ids']=[sid for sid,(mp,e) in current.items()
        if sid not in latest and any(o['type']=='body' for o in read(mp.parent/e['annotation'])['objects'])]
    save(R/'reports/external_scene_review_intake.json',report)
    print(json.dumps({k:report[k] for k in ('independent_review_completed','current_version_independent_review_completed','confirmed_body_label_images','confirmed_body_count','qualified_all_data_conditions')}))

if __name__=='__main__':main()
