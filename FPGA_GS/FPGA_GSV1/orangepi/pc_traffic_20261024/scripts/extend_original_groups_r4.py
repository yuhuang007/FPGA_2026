"""Publish only the three exactly bound source groups from genuine audit r3."""
import json
from datetime import datetime, timezone
from pilot_clean_crops import ROOT, read, sha


def main():
    out=ROOT/'data/group_releases/r4';assert not out.exists()
    old_path=ROOT/'data/group_releases/r3/manifest.json';old=read(old_path)
    pointer=read(ROOT/'data/released_original_groups.json')
    assert pointer['immutable_release_sha256']==sha(old_path)
    request_path=ROOT/'review_stage2/source_split_audit_r3/audit_request.json';request=read(request_path)
    review_path=ROOT/'review_stage2/independent_external_scene_r1/source_group_audit_r3.json';review=read(review_path)
    pc_path=ROOT/'review_stage2/source_split_audit_r3/pc_visual_observations.json';pc=read(pc_path)
    assert review['audit_completed'] and review['source_group_audit_passed'] and review['independent_from_PC_first_pass']
    assert not review['human_signoff'] and not review['training_release']
    assert review['audit_request']['sha256']==pc['request_sha256']==sha(request_path)
    assert review['PC_visual_observations_read']['sha256']==sha(pc_path)
    for e in review['evidence']:
        assert e['matches_requested_sha256'] and sha(ROOT/e['path'])==e['actual_sha256']==e['requested_sha256']
    for obs in pc['observations']:
        for e in obs['actually_viewed_pairs']:assert sha(ROOT/e['view'])==e['view_sha256']
    observations={e['candidate_id']:e for e in review['observations']}
    assert set(observations)=={e['candidate_id'] for e in request['external_candidates']}
    reserved=set(request['new_final_test_reserved_ids'])
    assert reserved==set(review['new_holdout_reservation']['candidate_ids'])
    assert pc['new_final_test_reserved_before_fitting'] is True
    assert reserved=={e['candidate_id'] for e in pc['observations'] if e['proposed_split']=='holdout'}
    assert not pc['training_started']
    licenses={e['candidate_id']:e for e in read(ROOT/'reports/external_scene_license_audit_r8.json')['entries']}
    external={e['candidate_id']:e for e in read(ROOT/'reports/external_scene_review_intake.json')['entries']}
    groups=list(old['groups']);old_ids={e['candidate_id'] for e in groups}
    for source in request['external_candidates']:
        cid=source['candidate_id'];assert cid not in old_ids
        obs=observations[cid];e=external[cid];license=licenses[cid]
        for key in ('source_group_independence_supported','independent_of_original400_joint_train_supported',
                    'independent_of_existing_eight_val_sources_supported','independent_of_madrid_holdout_supported'):
            assert obs[key] is True
        assert obs['image_sha256']==source['image_sha256']==e['image_sha256']
        for pair in obs['closest_pairs']:assert pair['actually_viewed'] and sha(ROOT/pair['view'])==pair['sha256']
        assert license['eligible_license'] and not license['conflict_quarantined']
        assert sha(ROOT/license['metadata_evidence_file'])==license['metadata_evidence_sha256']
        a=read(ROOT/e['annotation_file']);assert sha(ROOT/e['annotation_file'])==e['annotation_sha256']
        assert sha(ROOT/a['image_path'])==e['image_sha256']
        split='holdout' if cid in reserved else 'val';assert obs['proposed_split']==split
        groups.append({'candidate_id':cid,'canonical_original_id':source['photo_id'],'photo_id':source['photo_id'],
            'image_sha256':e['image_sha256'],'annotation_sha256':e['annotation_sha256'],
            'leakage_group':source['scene_id'],'official_split':split,'group_status':'verified',
            'source_family':'Wikimedia_Commons','source_variants_must_link':sorted(set(source['source_variants_must_link']+[source['image'],a['image_path']])),
            'all_future_variants_and_crops_inherit':True,'license_status':'verified','clean_original':'verified',
            'clean_source_scope':'Official full-context resampled photograph, not original full-resolution bytes; no model overlay.',
            'license_evidence':license,'evaluation_role':'final_test_reserved' if cid in reserved else 'tuning_validation',
            'never_use_for_tuning_or_INT8_calibration':cid in reserved,'reserved_before_model_fitting':cid in reserved,
            'verification_scope':review['pass_scope'],'same_physical_site_established':None,
            'unresolved_associations':obs['unresolved_associations']})
    assert groups[:len(old['groups'])]==old['groups']
    assert len({e['candidate_id'] for e in groups})==len(groups)
    evidence=old['evidence']+[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in (old_path,request_path,review_path,pc_path)]
    constraints=old.get('photo_split_constraints',[])+[{
        'photo_ids':['commons_page_173323959','commons_page_179853532'],
        'leakage_group':'PL_Krakow_29_Listopada_Commons173323959','split':'val',
        'relation':'Unresolved same-road association; must-link if second photo is later acquired. Same physical junction NOT confirmed.'}]
    result=dict(old,release_id='original_groups_r4',recorded_at=datetime.now(timezone.utc).isoformat(),groups=groups,evidence=evidence,
        supersedes={'path':old_path.relative_to(ROOT).as_posix(),'sha256':sha(old_path)},
        scope='Original400 joint train, nine audited external val groups, Madrid/Newton/CapeTown isolated holdout groups. Unlisted sources remain unassigned.',
        photo_split_constraints=constraints,
        final_test_status='Madrid, Newton and CapeTown reserved before fitting, excluded from tuning/calibration; small sample and incomplete safe export do not establish adequate independent final testing.',
        coverage_limits='Finite source separation only. Actual safe-crop class/scale coverage and sample quantity remain separate unfulfilled conditions.',
        coverage_or_training_approval=False,training_release=False)
    out.mkdir(parents=True)
    (out/'prior_split_audit_snapshot.json').write_bytes((ROOT/'reports/split_audit.json').read_bytes())
    dest=out/'manifest.json';dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'data/released_original_groups.json').write_text(json.dumps(dict(result,immutable_release=dest.relative_to(ROOT).as_posix(),immutable_release_sha256=sha(dest)),ensure_ascii=False,indent=2),encoding='utf-8')
    audit={'recorded_at':result['recorded_at'],'passed':True,'scope':'Finite source split risk closure only; label/export/coverage/quantity gates remain separate.',
        'release':dest.relative_to(ROOT).as_posix(),'release_sha256':sha(dest),'two_AI_source_audits':True,'human_signoff':False,
        'train_leakage_units':1,'independent_val_source_groups':9,'reserved_final_test_source_groups':3,
        'final_test_statistical_adequacy_approved':False,'training_release':False}
    (ROOT/'reports/split_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'released_originals':len(groups),'val_groups':9,'holdout_groups':3,'training_release':False}))


if __name__=='__main__':main()
