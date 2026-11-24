"""Publish the limited, evidence-bound original-photo split; no training approval."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from pilot_clean_crops import ROOT, read, sha


def main():
    out = ROOT / 'data/group_releases/r1'
    assert not (out / 'manifest.json').exists(), 'Published release is immutable'
    request_path = ROOT / 'review_stage2/source_split_audit_r1/audit_request.json'
    request = read(request_path)
    independent_path = ROOT / 'review_stage2/independent_external_scene_r1/source_group_audit_r1.json'
    independent = read(independent_path)
    clarification = read(ROOT / 'review_stage2/independent_external_scene_r1/source_group_audit_r1_intake_clarification.json')
    assert independent['independent_from_PC_first_pass'] is True
    assert independent['audit_request']['sha256'] == sha(request_path)
    assert clarification['completed_audit']['sha256'] == sha(independent_path)
    assert clarification['five_source_grouping_review_completed'] is True
    evidence = []
    for ref in request['evidence']:
        if ref['path'] == 'reports/resume_group_review.json':
            continue  # Dynamic supplement is separately frozen below, not old-SHA signed.
        assert sha(ROOT / ref['path']) == ref['sha256'], ref['path']
        evidence.append(ref)
    rows = list(csv.DictReader((ROOT / 'data/candidates.csv').open(encoding='utf-8-sig')))
    original_ids = {r['sample_id'] for r in rows}
    assert len(original_ids) == 400
    supplement_path = ROOT / 'reports/resume_group_review.json'
    supplement = read(supplement_path)
    for obs in supplement['observations']:
        assert obs['candidate_id'] in original_ids
        compared = {'s2tld1080_' + str(x).zfill(4) if isinstance(x, int) else x
                    for x in obs.get('visual_compared_candidates', [])}
        assert compared <= original_ids
    out.mkdir(parents=True, exist_ok=True)
    frozen_supplement = out / 'resume_group_review_snapshot.json'
    frozen_supplement.write_bytes(supplement_path.read_bytes())
    evidence.append({'path': frozen_supplement.relative_to(ROOT).as_posix(), 'sha256': sha(frozen_supplement),
                     'scope': 'Current PC-only internal original400 supplement; NOT old-SHA independent approval. All internal links contained in one train leakage group.'})
    for name in ('pc_visual_observations.json', 'pc_second_pair_observations.json'):
        p = ROOT / 'review_stage2/source_split_audit_r1' / name
        assert read(p)['request_sha256'] == sha(request_path)
        evidence.append({'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)})
    evidence.extend({'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for p in (
        request_path, independent_path,
        ROOT / 'review_stage2/independent_external_scene_r1/source_group_audit_r1_intake_clarification.json'))
    duplicate_review = read(ROOT / 'reports/near_duplicate_review.json')
    redundant = {'s2tld1080_' + str(k).zfill(4): 's2tld1080_' + str(v['keep']).zfill(4)
                 for k, v in duplicate_review['redundant_candidates'].items()}
    groups = []
    for row in rows:
        a = ROOT / row['annotation_file']
        assert sha(ROOT / row['image_path']) == row['sha256']
        groups.append({'candidate_id': row['sample_id'], 'canonical_original_id': row['sample_id'],
                       'image_sha256': row['sha256'], 'annotation_sha256': sha(a),
                       'leakage_group': 'unresolved_route_A_B_joint_train', 'official_split': 'train',
                       'group_status': 'verified', 'verification_scope': 'All observed and unresolved original400 associations contained within train; NOT a claim of one physical site.',
                       'same_physical_site_established': False, 'source_family': 'S2TLD_original400',
                       'redundant_capture_of': redundant.get(row['sample_id']),
                       'license_status': row['license_status'], 'clean_original': row['clean_original']})
    external = {e['candidate_id']: e for e in read(ROOT / 'reports/external_scene_review_intake.json')['entries']}
    licenses = {}
    for version in (1, 2):
        for item in read(ROOT / f'reports/external_scene_license_audit_r{version}.json')['entries']:
            licenses[item['candidate_id']] = item
    supported = set(clarification['candidate_validation_group_independence_supported'])
    for source in request['external_candidates']:
        cid = source['candidate_id']; e = external[cid]; license = licenses[cid]
        assert source['scene_id'] in supported
        assert license['eligible_license'] and not license['conflict_quarantined']
        assert sha(ROOT / license['oEmbed_evidence_file']) == license['oEmbed_evidence_sha256']
        a = read(ROOT / e['annotation_file'])
        assert sha(ROOT / e['annotation_file']) == e['annotation_sha256']
        assert sha(ROOT / a['image_path']) == a['image_sha256'] == e['image_sha256']
        # Larger-source variants differ in bytes; canonical photo ID binds them.
        variants = set(source['source_variants_must_link'] + [source['image'], a['image_path']])
        groups.append({'candidate_id': cid, 'canonical_original_id': 'flickr_photo_' + source['photo_id'],
                       'photo_id': source['photo_id'], 'image_sha256': e['image_sha256'],
                       'annotation_sha256': e['annotation_sha256'], 'leakage_group': source['scene_id'],
                       'official_split': 'val', 'group_status': 'verified',
                       'verification_scope': 'Two AI source/context reviews against original400 joint train; location evidence and ten nearest panels, not exhaustive1222 visual review.',
                       'source_family': 'independent_Flickr_photographs',
                       'source_variants_must_link': sorted(variants), 'all_future_variants_and_crops_inherit': True,
                       'license_status': 'verified', 'clean_original': 'verified',
                       'license_evidence': license})
    manifest = {'schema_version': 'original_group_release_v1', 'release_id': 'original_groups_r1',
                'recorded_at': datetime.now(timezone.utc).isoformat(), 'official_split_released': True,
                'scope': 'Original400 train leakage unit and exactly five independently audited val photos. Other external photos remain unassigned.',
                'evidence': evidence, 'groups': groups,
                'observed_relations': 'data/group_relations_r3.json',
                'unresolved_A_B_association_is_not_same_site_fact': True,
                'source_resolution_variants_and_crops_never_cross_splits': True,
                'SC_assets_included': False, 'human_signoff': False,
                'split_risk_audit_passed': True, 'coverage_or_training_approval': False,
                'final_test_status': 'Missing independently locked final-test group; validation is for tuning only.',
                'coverage_limits': 'Only five val source photos, three currently crop-validated motor-positive photos; pedestrian val coverage and representative independent test data still missing.',
                'training_release': False}
    dest = out / 'manifest.json'
    dest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    pointer = dict(manifest, immutable_release=dest.relative_to(ROOT).as_posix(), immutable_release_sha256=sha(dest))
    (ROOT / 'data/released_original_groups.json').write_text(json.dumps(pointer, ensure_ascii=False, indent=2), encoding='utf-8')
    audit = {'recorded_at': manifest['recorded_at'], 'passed': True,
             'scope': 'Group/split risk closure only; no dataset quantity/coverage/test/export approval.',
             'release': dest.relative_to(ROOT).as_posix(), 'release_sha256': sha(dest),
             'two_AI_source_audits': True, 'human_signoff': False,
             'train_leakage_units': 1, 'independent_val_source_groups': 5,
             'final_test_present': False, 'training_release': False}
    (ROOT / 'reports/split_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'released_originals': len(groups), 'train': 400, 'val_source_groups': 5, 'training_release': False}))


if __name__ == '__main__':
    main()
