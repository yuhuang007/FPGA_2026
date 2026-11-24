"""Validate the selected immutable source-supervised release, not historic exclusions."""
import collections
import hashlib
import json
import math
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import yaml
from PIL import Image
from source_partial_yolo import validate_release_entries, canonical
from qualify_clean_originals import confirmed_current
from current_data_holds import current_holds

ROOT = Path(__file__).resolve().parents[1]
RELEASE = 'datasets/public_body_r1/manifest.json'


def read(p):
    return json.loads((ROOT / p).read_text(encoding='utf-8'))


def sha(p):
    with (ROOT / p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def bound(ref):
    assert sha(ref['path']) == ref['sha256'], 'Stale evidence: ' + ref['path']


def validate():
    m = read(RELEASE)
    es = m['entries']
    validate_release_entries(es)
    assert m['route'] == 'source_positive_only_for_sparse_images'
    for ref in m['evidence']:
        bound(ref)
    audits = []
    for version, decision in [('r1', 'reuse_native_body_labels_with_targeted_repairs_and_grouped_train'),
                              ('r2', 'source_positive_reuse_and_bounded_loss_contract_supported_with_stated_limits')]:
        path = f'review_stage2/independent_external_scene_r1/public_dataset_compatibility_{version}.json'
        a = read(path)
        assert a['decision'] == decision and a['independent_from_PC_first_pass']
        assert not a['human_signoff']
        bound(a['request'])
        for e in a['source_evidence']:
            assert e['matches_requested_sha256']
            assert sha(e['path']) == e['actual_sha256'] == e['requested_sha256']
        request = read(a['request']['path'])
        for e in request['samples']:
            for key in ('image', 'view'):
                assert sha(e[key]) == e[key + '_sha256']
        audits.append({'path': path, 'sha256': sha(path), 'scope': a.get('pass_scope', a.get('source', 'sample audit'))})
    r2 = read(audits[1]['path'])
    bound(r2['additional_current_preparation_snapshot']['combined_manifest'])
    for ref in r2['implementation_review']['installed_reference_sources']:
        bound(ref)
    for ref in r2['implementation_review']['independently_executed_checks']:
        bound(ref)
    loss = read('reports/source_partial_loss_validation_r1.json')
    assert loss['passed'] and sha(loss['implementation']) == loss['implementation_sha256']
    assert loss['positive_priority_gradient_passed'] and loss['sparse_negative_classification_gradients_exactly_zero']
    assert loss['ordinary_detection_ema_roundtrip_passed']
    for family in ('s2tld720', 'tlony'):
        acq = read(f'data/public_datasets/{family}_r1/acquisition_manifest.json')
        archive = f'data/public_datasets/{family}_r1/{family}.zip'
        assert acq['verified'] and acq['repository_revision'] and acq['license']
        assert sha(archive) == acq['actual_sha256'] == acq['expected_sha256']
    legacy = {e['candidate_id']: e for e in read('datasets/clean_body_r3/manifest.json')['entries']}
    current = confirmed_current()
    holds, _ = current_holds()
    groups = {e['candidate_id']: e for e in read('data/group_releases/r4/manifest.json')['groups']}
    structure = {e['candidate_id']: e for e in read('reports/s2tld720_structure_audit_r1.json')['entries']}
    counts = collections.Counter()
    with zipfile.ZipFile(ROOT / 'data/public_datasets/s2tld720_r1/s2tld720.zip') as archive:
        for e in es:
            assert sha(e['image']) == e['image_sha256']
            assert canonical(ROOT / e['image']) == canonical(e['image_absolute'])
            assert sha(e['label']) == e['label_sha256']
            with Image.open(ROOT / e['image']) as im:
                iw, ih = im.size
                im.verify()
            rows = [(line.split()) for line in (ROOT / e['label']).read_text().splitlines() if line.strip()]
            assert len(rows) == e['body_count'] and rows
            for row in rows:
                assert len(row) == 5 and row[0] in ('0', '1')
                x, y, w, h = map(float, row[1:])
                assert all(math.isfinite(v) for v in (x, y, w, h))
                assert 0 < w <= 1 and 0 < h <= 1
                # Preserve native subpixel overhang (<=1px), never silently clip.
                assert min((x-w/2)*iw, (y-h/2)*ih) >= -1
                assert max((x+w/2)*iw-iw, (y+h/2)*ih-ih) <= 1
                counts[(e['split'], row[0])] += 1
            src = e['source']; family = src['family']
            if family == 'S2TLD720_native_day':
                original = structure[e['candidate_id']]
                assert original['storage_subset'] == 'normal_1'
                assert e['split'] == 'train' and e['supervision'] == 'positive_only'
                assert e['leakage_group'] == 'unresolved_route_A_B_joint_train'
                assert hashlib.sha256(archive.read(src['image_member'])).hexdigest() == e['image_sha256']
                assert hashlib.sha256(archive.read(src['annotation_member'])).hexdigest() == src['annotation_sha256']
                assert len(rows) == len(original['objects'])
                for row, obj in zip(rows, original['objects']):
                    assert row[0] == '0' and obj['source_class'] in ('red', 'green', 'yellow', 'off')
                    x,y,u,v = obj['bbox_xyxy']
                    expected = ((x+u)/2/iw, (y+v)/2/ih, (u-x)/iw, (v-y)/ih)
                    assert all(abs(float(a)-b) < 1e-8 for a,b in zip(row[1:], expected))
            elif family == 'TLoNY_native':
                assert e['split'] == 'train' and e['supervision'] == 'complete'
                assert e['leakage_group'] == 'TLoNY_Manhattan_unresolved_joint_train'
                assert sha(src['image']) == e['image_sha256']
                assert sha(src['annotation']) == src['annotation_sha256']
                original_rows = [r.split() for r in (ROOT/src['annotation']).read_text().splitlines() if r.strip()]
                expected = [[str(0 if int(r[0]) < 5 else 1)] + r[1:] for r in original_rows]
                assert rows == expected
                assert 'julien-riedel-alGtgU3MQu4-unsplash' not in e['candidate_id']
            else:
                assert family == 'legacy_verified_clean_crop' and e['supervision'] == 'complete'
                old = legacy[e['candidate_id']]; c = current[e['candidate_id']]
                assert e['candidate_id'] not in holds
                assert old['source_annotation_sha256'] == c['annotation_sha256']
                assert old['source_image_sha256'] == c['image_sha256']
                assert e['image_sha256'] == old['crop_sha256'] and e['label_sha256'] == old['yolo_label_sha256']
                assert groups[e['candidate_id']]['official_split'] == e['split'] == old['split']
                assert groups[e['candidate_id']]['leakage_group'] == e['leakage_group'] == old['leakage_group']
    assert len(es) == m['unique_originals'] == 972
    assert sum(e['split'] != 'holdout' for e in es) == m['train_val_originals'] == 971
    for split, ref in m['file_lists'].items():
        bound(ref)
        actual = (ROOT/ref['path']).read_text(encoding='utf-8').splitlines()
        assert actual == [e['image_absolute'] for e in es if e['split'] == split]
    assert sha(m['yaml']) == m['yaml_sha256']
    cfg = yaml.safe_load((ROOT/m['yaml']).read_text())
    assert cfg['nc'] == 2 and cfg['names'] == {0:'motor_vehicle_body', 1:'pedestrian_body'}
    assert set(cfg) == {'path','train','val','nc','names'}
    for split in ('train','val'):
        assert canonical(cfg[split]) == canonical(ROOT/m['file_lists'][split]['path'])
    split_audit = read('reports/split_audit.json')
    assert split_audit['passed'] and split_audit['two_AI_source_audits']
    assert sha(split_audit['release']) == split_audit['release_sha256']
    pre = read('reports/deployment_preflight.json'); rk = read('reports/rknn_preflight.json')
    assert pre['passed'] and rk['passed'] and pre['onnx_sha256'] == rk['onnx_sha256']
    assert read('reports/pytorch_cuda_smoke.json')['passed']
    weight = read('reports/pretrained_provenance.json')
    assert sha('artifacts/yolov8n_coco_official.pt') == weight['sha256']
    return {'recorded_at':datetime.now(timezone.utc).isoformat(), 'ready_to_train':True,
        'selected_release':RELEASE, 'selected_release_sha256':sha(RELEASE),
        'unique_train_val_originals':971, 'unique_holdout_originals':1,
        'source_supervised_public_originals':928, 'legacy_individually_confirmed_safe_originals':44,
        'body_targets':sum(counts.values()), 'independent_sample_method_audits':audits,
        'all_selected_entries_SHA_format_mapping_split_checked':True,
        'training_authorization':'Existing user authorization; compatible public native labels reused after sampled source/method audits. No per-photo AI signatures fabricated.',
        'historic_unselected_disputes':'Excluded from this release as entire images, never imported as negative backgrounds.',
        'coverage_limits':['Only5complete external val originals/8bodies; no China precision claim.',
            'Final test currently1pedestrian original, insufficient coverage; reserved from tuning.',
            'Production Trainer fit/val/save is verified during actual training, not preclaimed.',
            'normal_2 subset deferred; it is not uniformly night.'],
        'old_build_evidence_scope':'Architecture/deployment feasibility only; new trained weights require new export and board checks.'}


def main():
    try:
        result = validate()
    except Exception as exc:
        result = {'recorded_at':datetime.now(timezone.utc).isoformat(), 'ready_to_train':False,
                  'selected_release':RELEASE, 'error':f'{type(exc).__name__}: {exc}'}
        (ROOT/'reports/public_training_readiness_r1.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        raise
    (ROOT/'reports/public_training_readiness_r1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    main()
