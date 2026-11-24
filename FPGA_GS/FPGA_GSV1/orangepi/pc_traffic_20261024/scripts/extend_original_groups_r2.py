"""Apply completed second source audit; preserve old releases and photo identities."""
import csv
import json
from datetime import datetime, timezone
from pilot_clean_crops import ROOT, read, sha


def main():
    out=ROOT/'data/group_releases/r2';assert not out.exists()
    old_path=ROOT/'data/group_releases/r1/manifest.json';old=read(old_path)
    request_path=ROOT/'review_stage2/source_split_audit_r2/audit_request.json';request=read(request_path)
    review_path=ROOT/'review_stage2/independent_external_scene_r1/source_group_audit_r2.json';review=read(review_path)
    assert review['audit_completed'] and review['independent_from_PC_first_pass']
    assert review['audit_request']['sha256']==sha(request_path)
    for e in review['evidence']:
        assert e['matches_requested_sha256'] and sha(ROOT/e['path'])==e['actual_sha256']==e['requested_sha256']
    pc_path=ROOT/'review_stage2/source_split_audit_r2/pc_visual_observations.json'
    assert read(pc_path)['request_sha256']==sha(request_path)
    for e in read(pc_path)['observations']:
        for p in e['actually_viewed_pairs']:assert sha(ROOT/p['view'])==p['view_sha256']
    source_observations={e['candidate_id']:e for e in review['observations']}
    ext={e['candidate_id']:e for e in read(ROOT/'reports/external_scene_review_intake.json')['entries']}
    license_entries={e['candidate_id']:e for version in (3,7)
                     for e in read(ROOT/f'reports/external_scene_license_audit_r{version}.json')['entries']}
    rows={r['sample_id']:r for r in csv.DictReader((ROOT/'data/candidates.csv').open(encoding='utf-8-sig'))}
    groups=[];rebindings=[]
    for g in old['groups']:
        g=dict(g)
        if g['candidate_id'] in rows:
            active=sha(ROOT/rows[g['candidate_id']]['annotation_file'])
            if active!=g['annotation_sha256']:
                rebindings.append({'candidate_id':g['candidate_id'],'old_annotation_sha256':g['annotation_sha256'],
                                   'new_annotation_sha256':active,'scope':'Same original image and split; annotation binding refreshed, no label/export acceptance inherited.'})
                g['annotation_sha256']=active
        groups.append(g)
    for source in request['external_candidates']:
        cid=source['candidate_id'];obs=source_observations[cid];e=ext[cid];license=license_entries[cid]
        assert all(obs[k] is True for k in ('source_group_independence_supported',
            'independent_of_original400_joint_train_supported','independent_of_existing_five_val_sources_supported'))
        assert obs['image_sha256']==source['image_sha256']==e['image_sha256']
        assert license['eligible_license'] and not license['conflict_quarantined']
        ep=license.get('oEmbed_evidence_file',license.get('metadata_evidence_file'))
        eh=license.get('oEmbed_evidence_sha256',license.get('metadata_evidence_sha256'))
        assert sha(ROOT/ep)==eh
        a=read(ROOT/e['annotation_file']);assert sha(ROOT/e['annotation_file'])==e['annotation_sha256']
        assert sha(ROOT/a['image_path'])==e['image_sha256']
        madrid=cid=='commons_scene_132116089';portland=cid=='coco_scene_000000309391'
        group='US_Portland_unresolved_photos_5329327710_10190866013' if portland else source['scene_id']
        groups.append({'candidate_id':cid,'canonical_original_id':source['photo_id'] if cid.startswith('commons_') else 'flickr_photo_'+source['photo_id'],
            'photo_id':source['photo_id'],'image_sha256':e['image_sha256'],'annotation_sha256':e['annotation_sha256'],
            'leakage_group':group,'official_split':'holdout' if madrid else 'val','group_status':'verified',
            'source_family':'Wikimedia_Commons' if cid.startswith('commons_') else 'independent_Flickr_photographs',
            'source_variants_must_link':sorted(set(source['source_variants_must_link']+[source['image'],a['image_path']])),
            'all_future_variants_and_crops_inherit':True,'license_status':'verified','clean_original':'verified',
            'clean_source_scope':'Official full-context resampled photograph, not original full-resolution bytes; no model overlay.' if cid.startswith('commons_') else 'Licensed source photograph with two actual whole-image AI reviews; not source dataset labels.',
            'license_evidence':license,'evaluation_role':'final_test_reserved' if madrid else 'tuning_validation',
            'never_use_for_tuning_or_INT8_calibration':madrid,'reserved_before_model_fitting':madrid,
            'verification_scope':'PC and independent source geography/context audit; no whole1222 visual claim, no label/crop/training approval from geography.',
            'same_physical_site_established':False if portland else None})
    out.mkdir(parents=True)
    prior_audit=out/'prior_split_audit_snapshot.json';prior_audit.write_bytes((ROOT/'reports/split_audit.json').read_bytes())
    evidence=old['evidence']+[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in (
        old_path,request_path,review_path,pc_path,ROOT/'reports/external_scene_license_audit_r7_scope_clarification.json')]
    result=dict(old,release_id='original_groups_r2',recorded_at=datetime.now(timezone.utc).isoformat(),groups=groups,evidence=evidence,
        scope='Original400 joint train, eight external val source groups, one isolated Madrid final-test candidate source. All unlisted sources remain unassigned.',
        supersedes={'path':old_path.relative_to(ROOT).as_posix(),'sha256':sha(old_path)},annotation_binding_refreshes=rebindings,
        photo_split_constraints=[{'photo_ids':['5329327710','10190866013'],'leakage_group':'US_Portland_unresolved_photos_5329327710_10190866013',
            'split':'val','relation':'Conservative unresolved same-city/rail-network association; NOT proved same junction. Excluded prior railway photo remains excluded.'}],
        final_test_status='One Madrid pedestrian-only close-up source reserved before fitting; no tuning/calibration use. Clean export remains separate; one atypical photo does not establish adequate independent final testing.',
        coverage_limits='Val scene coverage still small; pedestrian exports require actual geometry/pixel/visual checks. Final test lacks motor class and representative small/distant/context coverage.',
        coverage_or_training_approval=False,training_release=False)
    dest=out/'manifest.json';dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    pointer=dict(result,immutable_release=dest.relative_to(ROOT).as_posix(),immutable_release_sha256=sha(dest))
    (ROOT/'data/released_original_groups.json').write_text(json.dumps(pointer,ensure_ascii=False,indent=2),encoding='utf-8')
    audit={'recorded_at':result['recorded_at'],'passed':True,'scope':'Source split risk closure only, independent of label/export/quantity/coverage gates.',
           'release':dest.relative_to(ROOT).as_posix(),'release_sha256':sha(dest),'two_AI_source_audits':True,'human_signoff':False,
           'train_leakage_units':1,'independent_val_source_groups':8,'reserved_final_test_source_groups':1,
           'final_test_statistical_adequacy_approved':False,'training_release':False}
    (ROOT/'reports/split_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'released_originals':len(groups),'val_source_groups':8,'isolated_holdout_source_groups':1,'training_release':False}))


if __name__=='__main__':main()
