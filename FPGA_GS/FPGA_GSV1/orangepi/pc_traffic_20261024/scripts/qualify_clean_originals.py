"""Count exact-reviewed, licensed, split-bound and validated unique source photos."""
import argparse
import json
import csv
import hashlib
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pilot_clean_crops import ROOT, read, sha


def validate_contract(e, current, group, manifest, validated_ids, visual_ids):
    """All per-original conditions must hold, even before global quantity gates."""
    assert current and current['confirmed_body_ids'], 'current independent body confirmation missing'
    assert current['annotation_sha256'] == e['source_annotation_sha256'], 'stale label'
    assert current['image_sha256'] == e['source_image_sha256'], 'wrong source image'
    assert current['first_pass_reviewer'] and current['independent_reviewer']
    assert current['first_pass_reviewer'] != current['independent_reviewer'], 'same reviewer'
    assert {t['source_id'] for t in e['targets']} <= set(current['confirmed_body_ids'])
    assert group and group['group_status'] == 'verified', 'group not verified'
    assert group['annotation_sha256'] == e['source_annotation_sha256'], 'stale group binding'
    assert group['image_sha256'] == e['source_image_sha256']
    assert group['official_split'] in ('train', 'val', 'holdout')
    assert group['official_split'] == e['inherited_split'], 'wrong inherited split'
    assert group['leakage_group'] == e['inherited_group']
    assert group['license_status'] == group['clean_original'] == 'verified'
    assert not group.get('redundant_capture_of'), 'duplicate capture'
    assert e['split_assigned_before_derivation']
    assert manifest['original_split_release_verified']
    assert e['candidate_id'] in validated_ids, 'crop not validated'
    assert e['candidate_id'] in visual_ids, 'crop pixels lack visual QA'
    assert e['ignore_intersections'] == e['partial_body_intersections'] == 0


def assert_unique_originals(entries):
    for key in ('candidate_id', 'canonical_original_id', 'source_image_sha256'):
        values = [e[key] for e in entries]
        assert len(values) == len(set(values)), 'duplicate original/photo variant: ' + key
    for key in ('leakage_group', 'canonical_original_id', 'source_image_sha256'):
        groups = {}
        for e in entries:
            groups.setdefault(e[key], set()).add(e['split'])
        assert all(len(splits) == 1 for splits in groups.values()), 'cross-split identity: ' + key


def confirmed_current():
    original = read(ROOT / 'review_stage2/final_candidates_r1/manifest.json')
    external = read(ROOT / 'reports/external_scene_review_intake.json')
    rows = {r['sample_id']: r for r in csv.DictReader((ROOT / 'data/candidates.csv').open(encoding='utf-8-sig'))}
    revisions = read(ROOT / 'reports/independent_review_intake.json')['revisions']
    active = {e['candidate_id']: e for e in revisions if e.get('is_active_version', True)}
    current = {}
    for e in original['entries']:
        p = ROOT / (active[e['candidate_id']]['revision_file'] if e['candidate_id'] in active else rows[e['candidate_id']]['annotation_file'])
        if sha(p) == e['annotation_sha256']:
            current[e['candidate_id']] = e
    current.update({e['candidate_id']: e for e in external['entries']})
    return current


def qualification_entries(manifest_path, validation_path, visual_path, candidate_ids=None):
    m = read(manifest_path); validation = read(validation_path); visual = read(visual_path)
    assert validation['passed'] and visual['passed']
    assert sha(manifest_path) == validation['pilot_manifest_sha256'] == visual['production_manifest_sha256']
    gp = ROOT / m['original_group_release']
    assert sha(gp) == m['original_group_release_sha256'] == validation['original_group_release_sha256']
    release = read(gp)
    for evidence in release['evidence']:
        assert sha(ROOT / evidence['path']) == evidence['sha256'], 'group evidence changed'
    groups = {g['candidate_id']: g for g in release['groups']}
    quality_path = ROOT / ('reports/clean_original_quality_' + manifest_path.parent.name.removeprefix('clean_crop_release_') + '.json')
    quality = read(quality_path)
    assert quality['production_manifest_sha256'] == sha(manifest_path)
    assert sha(ROOT / quality['archive_provenance']) == quality['archive_provenance_sha256']
    assert sha(ROOT / quality['archive']) == quality['archive_sha256']
    for q in quality['entries']:
        g = groups[q['candidate_id']]
        assert q['source_image_sha256'] == g['image_sha256'] and q['byte_identical_archive_original']
        assert q['independent_whole_original_review_verified']
        assert sha(ROOT / q['independent_review_file']) == q['independent_review_file_sha256']
        groups[q['candidate_id']] = dict(g, clean_original='verified')
    final = confirmed_current()
    validated_ids = {e['candidate_id'] for e in validation['checks'] if e['pixel_exact'] and e['all_intersecting_bodies_included']}
    visual_ids = {e['candidate_id'] for e in visual['entries'] if e['crop_visual_QA_passed']}
    for e in visual['entries']:
        for key in ('prior_visual_QA', 'prior_validation', 'fresh_visual_QA'):
            if key in e:
                assert sha(ROOT / e[key]) == e[key + '_sha256'], 'visual evidence changed'
    result = []
    for e in m['entries']:
        if 'crop_file' not in e:
            continue
        if candidate_ids is not None and e['candidate_id'] not in candidate_ids:
            continue
        current = final.get(e['candidate_id']); group = groups.get(e['candidate_id'])
        validate_contract(e, current, group, m, validated_ids, visual_ids)
        for file_key, hash_key in (('source_annotation', 'source_annotation_sha256'), ('source_image', 'source_image_sha256'),
                                   ('crop_file', 'crop_sha256'), ('yolo_label_file', 'yolo_label_sha256')):
            assert sha(ROOT / e[file_key]) == e[hash_key], file_key + ' changed'
        ref = current['independent_review_source']
        file = ref.get('file', ref.get('source_file'))
        expected = ref.get('sha256', ref.get('source_file_sha256'))
        assert sha(ROOT / file) == expected, 'independent record changed'
        record = json.loads((ROOT / file).read_text(encoding='utf-8-sig').splitlines()[ref['line'] - 1])
        # Targeted checks can preserve earlier checks through a verified version chain;
        # the intake scripts, not this exporter, decide acceptance of that chain.
        assert record.get('candidate_id', record.get('sample_id')) == e['candidate_id']
        result.append({'candidate_id': e['candidate_id'], 'canonical_original_id': group['canonical_original_id'],
                       'source_image_sha256': e['source_image_sha256'], 'source_annotation': e['source_annotation'],
                       'source_annotation_sha256': e['source_annotation_sha256'],
                       'split': group['official_split'], 'leakage_group': group['leakage_group'],
                       'crop_file': e['crop_file'], 'crop_sha256': e['crop_sha256'],
                       'yolo_label_file': e['yolo_label_file'], 'yolo_label_sha256': e['yolo_label_sha256'],
                       'targets': e['targets'], 'body_count': len(e['targets']),
                       'first_pass_reviewer': current['first_pass_reviewer'], 'independent_reviewer': current['independent_reviewer'],
                       'independent_review_source': ref, 'human_signoff': False,
                       'eligible_for_dataset': True, 'global_training_release': False})
    assert_unique_originals(result)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--release', default='r1'); ap.add_argument('--finalize', action='store_true')
    args = ap.parse_args()
    manifest_path = ROOT / f'review_stage2/clean_crop_release_{args.release}/manifest.json'
    validation_path = ROOT / f'reports/clean_crop_release_validation_{args.release}.json'
    visual_path = ROOT / f'reports/clean_crop_release_visual_QA_{args.release}.json'
    m = read(manifest_path)
    if args.finalize:
        from current_data_holds import current_holds
        holds, _ = current_holds()
        assert not any(e['candidate_id'] in holds for e in m['entries']), 'Active integrity hold prevents new qualification'
    if args.finalize and not visual_path.exists():
        prior = {}
        fresh_path = ROOT / f'reports/clean_crop_release_fresh_visual_{args.release}.json'
        fresh = read(fresh_path) if fresh_path.exists() else {'entries': []}
        if fresh['entries']:
            assert fresh['production_manifest_sha256'] == sha(manifest_path)
        freshly_checked = {e['candidate_id']: e for e in fresh['entries']}
        for batch in read(ROOT / 'reports/ignore_handling_decision.json')['validated_pilot_batches']:
            pm = read(ROOT / batch['manifest']); pv = read(ROOT / batch['visual_review']); pg = read(ROOT / batch['validation'])
            assert pv['passed'] and pg['passed']
            assert sha(ROOT / batch['manifest']) == pv['pilot_manifest_sha256'] == pg['pilot_manifest_sha256']
            checked = {v['candidate_id']: v for v in pv['entries'] if v['crop_context_passed_for_detection_pilot']}
            for e in pm['entries']:
                if 'crop_file' in e and e['candidate_id'] in checked:
                    v = checked[e['candidate_id']]
                    assert v['all_visible_body_targets_checked'] and not v['new_truncated_body_seen'] and not v['unlabelled_signal_seen']
                    assert v['crop_sha256'] == sha(ROOT / e['crop_file']) == e['crop_sha256']
                    prior[e['candidate_id']] = (e, batch)
        qa = []
        for e in m['entries']:
            if 'crop_file' not in e:
                continue
            old, batch = prior.get(e['candidate_id'], (None, None))
            identical = bool(old) and all(old[key] == e[key] for key in ('source_image_sha256', 'source_annotation_sha256', 'crop_sha256', 'yolo_label_sha256', 'crop_xyxy', 'targets', 'obstacles'))
            if not identical:
                v = freshly_checked[e['candidate_id']]
                assert v['actual_visual_QA_passed'] and v['all_visible_body_targets_checked']
                assert not v['new_truncated_body_seen'] and not v['unlabelled_signal_seen']
                for key in ('source_annotation_sha256', 'crop_sha256', 'yolo_label_sha256'):
                    assert v[key] == e[key]
                assert sha(ROOT / v['viewed_source']) == v['viewed_source_sha256']
                assert sha(ROOT / v['viewed_crop']) == v['viewed_crop_sha256']
                qa.append({'candidate_id': e['candidate_id'], 'identical_to_actual_prior_visual_QA': False,
                           'crop_visual_QA_passed': True, 'fresh_visual_QA': fresh_path.relative_to(ROOT).as_posix(),
                           'fresh_visual_QA_sha256': sha(fresh_path), 'crop_sha256': e['crop_sha256'],
                           'yolo_label_sha256': e['yolo_label_sha256']})
                continue
            qa.append({'candidate_id': e['candidate_id'], 'identical_to_actual_prior_visual_QA': True, 'crop_visual_QA_passed': True,
                       'prior_visual_QA': batch['visual_review'], 'prior_visual_QA_sha256': sha(ROOT / batch['visual_review']),
                       'prior_validation': batch['validation'], 'prior_validation_sha256': sha(ROOT / batch['validation']),
                       'crop_sha256': e['crop_sha256'], 'yolo_label_sha256': e['yolo_label_sha256']})
        visual = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'passed': True,
                  'production_manifest_sha256': sha(manifest_path), 'entries': qa,
                  'method': 'Reuse only exact original pixels, crop bounds, obstacles, targets and label bytes from actual prior PC QA; changed crops require separate fresh actual visual evidence. No independent crop signature claimed.',
                  'human_signoff': False, 'new_images_visually_reviewed': sum(not e['identical_to_actual_prior_visual_QA'] for e in qa)}
        visual_path.write_text(json.dumps(visual, ensure_ascii=False, indent=2), encoding='utf-8')
    quality_path = ROOT / f'reports/clean_original_quality_{args.release}.json'
    if args.finalize and not quality_path.exists():
        groups = {e['candidate_id']: e for e in read(ROOT / m['original_group_release'])['groups']}
        rows = {r['sample_id']: r for r in csv.DictReader((ROOT / 'data/candidates.csv').open(encoding='utf-8-sig'))}
        current = confirmed_current(); provenance_path = ROOT / 'data/archive_provenance.json'
        archive_path = ROOT / 'data/s2tld_1080.zip'; provenance = read(provenance_path)
        assert sha(archive_path) == provenance['sha256']
        checks = []
        with zipfile.ZipFile(archive_path) as archive:
            names = {name: name for name in archive.namelist()}
            for name in archive.namelist():
                try:
                    names[name.encode('cp437').decode('gbk')] = name
                except (UnicodeError, LookupError):
                    pass
            for e in m['entries']:
                if 'crop_file' not in e:
                    continue
                if groups[e['candidate_id']]['clean_original'] == 'verified':
                    continue
                row = rows[e['candidate_id']]; ref = current[e['candidate_id']]['independent_review_source']
                file = ref.get('file', ref.get('source_file')); expected = ref.get('sha256', ref.get('source_file_sha256'))
                assert sha(ROOT / file) == expected
                review = json.loads((ROOT / file).read_text(encoding='utf-8-sig').splitlines()[ref['line'] - 1])
                if not review.get('full_original_checked'):
                    # Source bytes did not change. Preserve an actual earlier
                    # whole-original observation for image integrity only; the
                    # new label is separately checked on its own exact SHA.
                    whole=[v for v in read(ROOT/'reports/independent_review_intake.json')['reviews']
                           if v['candidate_id']==e['candidate_id'] and v['image_sha256']==e['source_image_sha256']
                           and v['review_scope']=='whole_image']
                    prior=max(whole,key=lambda v:v['reviewed_at'])
                    file=prior['source_file'];expected=prior['source_file_sha256']
                    assert sha(ROOT/file)==expected
                    review=json.loads((ROOT/file).read_text(encoding='utf-8-sig').splitlines()[prior['line']-1])
                assert review['full_original_checked'] and review['omission_search_completed']
                assert hashlib.sha256(archive.read(names[row['source_member']])).hexdigest() == e['source_image_sha256']
                checks.append({'candidate_id': e['candidate_id'], 'source_image_sha256': e['source_image_sha256'],
                               'source_member': row['source_member'], 'byte_identical_archive_original': True,
                               'independent_whole_original_review_verified': True,
                               'source_pixel_observation_not_current_label_omission_recertification':True,
                               'independent_review_file': file, 'independent_review_file_sha256': expected,
                               'basis': 'Original raw archive bytes, independently viewed full original, and actual PC source/crop QA; source timestamp is not an inference overlay.'})
        quality_path.write_text(json.dumps({'production_manifest_sha256': sha(manifest_path),
            'archive_provenance': provenance_path.relative_to(ROOT).as_posix(), 'archive_provenance_sha256': sha(provenance_path),
            'archive': archive_path.relative_to(ROOT).as_posix(), 'archive_sha256': sha(archive_path),
            'entries': checks, 'old_group_clean_original_metadata_preserved': True, 'human_signoff': False}, ensure_ascii=False, indent=2), encoding='utf-8')
    entries = qualification_entries(manifest_path, validation_path, visual_path)
    # Registries are snapshots; readiness revalidates against current label SHA.
    result = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'qualified_original_images': len(entries),
              'qualified_body_targets': sum(e['body_count'] for e in entries), 'split_counts': dict(Counter(e['split'] for e in entries)),
              'production_manifest': manifest_path.relative_to(ROOT).as_posix(), 'production_manifest_sha256': sha(manifest_path),
              'validation': validation_path.relative_to(ROOT).as_posix(), 'validation_sha256': sha(validation_path),
              'visual_QA': visual_path.relative_to(ROOT).as_posix(), 'visual_QA_sha256': sha(visual_path),
              'qualification_unit': 'unique original photo, one crop per source; global training gates separate',
              'entries': entries, 'global_training_release': False}
    dest = ROOT / f'reports/qualified_originals_{args.release}.json'
    if args.finalize:
        assert not dest.exists(), 'Published registry is immutable'
        dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        assert read(dest)['entries'] == entries
    print(json.dumps({k: result[k] for k in ('qualified_original_images', 'qualified_body_targets', 'split_counts')}))


if __name__ == '__main__':
    main()
