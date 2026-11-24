"""Fail closed; this script never starts training or accepts pseudo labels."""
import csv
import json
from pathlib import Path
from qualify_clean_originals import qualification_entries, assert_unique_originals, confirmed_current
from pilot_clean_crops import sha
from current_data_holds import current_holds

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/candidates.csv'
    rows = list(csv.DictReader(path.open(encoding='utf-8-sig'))) if path.exists() else []
    # Final labels alone cannot make ignore pixels safe ordinary YOLO background.
    # External originals have a separate intake; do not mutate original400 CSV.
    approved, invalid_releases, registry_files = [], [], []
    holds, hold_source = current_holds()
    held_entries = []
    current = confirmed_current()
    withheld_registry_entries = []
    for registry_path in sorted((ROOT / 'reports').glob('qualified_originals_r*.json')):
        try:
            registry = json.loads(registry_path.read_text(encoding='utf-8'))
            for key in ('production_manifest', 'validation', 'visual_QA'):
                assert sha(ROOT / registry[key]) == registry[key + '_sha256']
            active_ids = set()
            for e in registry['entries']:
                cid=e['candidate_id']; c=current.get(cid,{})
                reason = ('active_integrity_hold' if cid in holds else
                    'current_label_confirmation_missing_or_changed' if c.get('annotation_sha256')!=e['source_annotation_sha256']
                    or c.get('image_sha256')!=e['source_image_sha256'] else None)
                if reason:
                    withheld_registry_entries.append({'candidate_id':cid,'registry':registry_path.relative_to(ROOT).as_posix(),'reason':reason})
                    if cid in holds:held_entries.append(e)
                else:active_ids.add(cid)
            entries = qualification_entries(ROOT / registry['production_manifest'], ROOT / registry['validation'], ROOT / registry['visual_QA'], candidate_ids=active_ids)
            assert entries == [e for e in registry['entries'] if e['candidate_id'] in active_ids]
            assert_unique_originals(approved + entries)
            approved.extend(entries)
            registry_files.append({'path': registry_path.relative_to(ROOT).as_posix(), 'sha256': sha(registry_path), 'active_candidate_ids':sorted(active_ids)})
        except (AssertionError, KeyError, ValueError, OSError) as error:
            invalid_releases.append({'path': registry_path.relative_to(ROOT).as_posix(), 'error': str(error)})
    qualified_ids = {e['candidate_id'] for e in approved}
    intake_path = ROOT / 'reports/independent_review_intake.json'
    intake = json.loads(intake_path.read_text(encoding='utf-8')) if intake_path.exists() else {}
    excluded_ids = set(intake.get('explicitly_excluded_ids', []))
    external_ids = set()
    for p in (ROOT / 'review_stage2').glob('external_scene_pilot_r*/manifest.json'):
        external_ids.update(e['candidate_id'] for e in json.loads(p.read_text(encoding='utf-8'))['entries'])
    ext_path = ROOT / 'reports/external_scene_review_intake.json'
    external = json.loads(ext_path.read_text(encoding='utf-8')) if ext_path.exists() else {'entries': []}
    excluded_ids.update(e['candidate_id'] for e in external['entries'] if not e['confirmed_body_ids'])
    all_ids = {r['sample_id'] for r in rows} | external_ids
    groups, hashes = {}, {}
    for row in approved:
        groups.setdefault(row['leakage_group'], set()).add(row['split'])
        hashes.setdefault(row['source_image_sha256'], set()).add(row['split'])
    split_check = ROOT / 'reports/split_audit.json'
    audit = json.loads(split_check.read_text(encoding='utf-8')) if split_check.exists() else {}
    conversion = ROOT / 'reports/rknn_preflight.json'
    rknn = json.loads(conversion.read_text(encoding='utf-8')) if conversion.exists() else {}
    onnx = ROOT / 'reports/deployment_preflight.json'
    preflight = json.loads(onnx.read_text(encoding='utf-8')) if onnx.exists() else {}
    checks = {
        'qualified_batch_at_least_300': sum(r['split'] in ('train', 'val') for r in approved) >= 300,
        'all_candidates_reviewed_or_explicitly_excluded': bool(all_ids) and all_ids <= qualified_ids | excluded_ids,
        'approved_group_and_hash_exclusive': bool(approved) and all(
            len(x) == 1 for x in list(groups.values()) + list(hashes.values())),
        'train_and_val_present': {'train', 'val'} <= {r['split'] for r in approved},
        'manual_site_and_near_duplicate_audit': (audit.get('passed') is True
            and audit.get('two_AI_source_audits') is True and bool(audit.get('release'))
            and sha(ROOT / audit['release']) == audit.get('release_sha256')),
        'safe_clean_export_current_SHA_validated': bool(approved) and not invalid_releases,
        'onnx_preflight_passed': preflight.get('passed') is True,
        'rknn_fp16_build_passed_for_same_onnx': rknn.get('passed') is True
            and bool(rknn.get('onnx_sha256'))
            and rknn.get('onnx_sha256') == preflight.get('onnx_sha256'),
        'pytorch_gpu_training_smoke_passed': (
            json.loads((ROOT / 'reports/pytorch_cuda_smoke.json').read_text(encoding='utf-8')).get('passed') is True
            if (ROOT / 'reports/pytorch_cuda_smoke.json').exists() else False),
    }
    result = {'ready_to_train': all(checks.values()), 'candidate_images': len(all_ids),
              'qualified_images': len(approved), 'checks': checks,
              'qualified_original400': sum(e['candidate_id'].startswith('s2tld1080_') for e in approved),
              'qualified_external_originals': sum(not e['candidate_id'].startswith('s2tld1080_') for e in approved),
              'qualified_targets': sum(e['body_count'] for e in approved),
              'qualified_split_counts': {s: sum(e['split']==s for e in approved) for s in ('train','val','holdout')},
              'qualified_original_ids': sorted(qualified_ids), 'qualification_registries': registry_files,
              'invalid_or_stale_releases': invalid_releases,
              'active_integrity_hold_ids': sorted(holds), 'integrity_hold_source': hold_source,
              'previously_qualified_originals_temporarily_withheld': len(held_entries),
              'withheld_historical_registry_entries':withheld_registry_entries,
              'final_test_status': (f"{sum(e['split']=='holdout' for e in approved)} isolated heldout original(s); excluded from tuning/calibration. One Madrid pedestrian close-up alone is not adequate final-test coverage."
                  if any(e['split']=='holdout' for e in approved) else 'No qualified independent final-test image yet; reserved Madrid source is separate from tuning val.'),
              'coverage_limits': ('Val now includes pedestrian bodies; original/photo/site count remains small. Final-test motor, small/distant and broad scene coverage still missing.'
                  if any(e['split']=='val' and any(t['kind']=='pedestrian' for t in e['targets']) for e in approved)
                  else 'Current released val crops contain motor bodies only; pedestrian validation and wider scene coverage remain missing.'),
              'training_quantity_basis': 'Unique qualified train+val originals only; heldout photos and multiple crops do not satisfy300.',
              'historical_manual_gate_name': 'Existing key retained; real two-independent-AI site/near-duplicate records accepted. No human signature fabricated or required.',
              'warning': 'Counts are workflow gates, not a reliability guarantee.'}
    (ROOT / 'reports/readiness.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ready_to_train'] else 2)


if __name__ == '__main__':
    main()
