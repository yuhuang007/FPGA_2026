"""Acquire a small explicit Commons selection without importing source labels."""
import argparse
import io
import json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image
from pilot_clean_crops import ROOT, read, sha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--query', required=True)
    ap.add_argument('--batch', required=True)
    ap.add_argument('--ids', nargs='+', required=True)
    args = ap.parse_args()
    assert 1 <= len(args.ids) <= 4, 'Small acquisition batches only'
    source = ROOT / args.query
    query = read(source)
    assert query['http_status'] == 200
    out = ROOT / ('data/external_scene_candidates_' + args.batch)
    assert not out.exists(), 'Never overwrite an acquisition'
    existing = {e.get('candidate_id') for p in (ROOT/'data').glob('external_scene_candidates_*/acquisition_manifest.json')
                for e in read(p)['entries']}
    pages = {str(p['pageid']): p for p in query['response']['query']['pages'].values()}
    assert len(args.ids) == len(set(args.ids))
    for pid in args.ids:
        assert 'commons_scene_' + pid not in existing, 'Canonical photo already acquired'
        assert pages[pid]['imageinfo'][0]['extmetadata']['LicenseShortName']['value'] in (
            'CC0', 'CC BY 2.0', 'CC BY 3.0', 'CC BY 4.0', 'CC BY-SA 3.0', 'CC BY-SA 4.0')
    for sub in ('images', 'views', 'provenance'):
        (out/sub).mkdir(parents=True, exist_ok=True)

    def acquire(pid):
        page = pages[pid]; info = page['imageinfo'][0]; md = info['extmetadata']
        response = requests.get(info['thumburl'], headers={'User-Agent': 'TrafficBodyDatasetResearch/1.0'}, timeout=40)
        response.raise_for_status()
        assert len(response.content) < 20000000
        im = Image.open(io.BytesIO(response.content)); im.load()
        assert list(im.size) == [info['thumbwidth'], info['thumbheight']]
        path = out/'images'/('commons_' + pid + '.jpg'); path.write_bytes(response.content)
        view = im.convert('RGB'); view.thumbnail((900, 700))
        vp = out/'views'/path.name; view.save(vp, quality=92)
        metadata = out/'provenance'/('commons_' + pid + '_metadata.json')
        metadata.write_text(json.dumps({'recorded_at': datetime.now(timezone.utc).isoformat(),
            'query_evidence': args.query, 'query_evidence_sha256': sha(source), 'page': page,
            'download_http_status': response.status_code, 'no_source_project_labels': True}, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'candidate_id': 'commons_scene_' + pid, 'source_dataset': 'Wikimedia_Commons',
            'source_dataset_image_id': pid, 'photo_id': 'commons_page_' + pid,
            'title': page['title'], 'author': md.get('Artist', {}).get('value', ''),
            'photo_page': info['descriptionurl'], 'download_url': info['thumburl'],
            'original_full_resolution_size': [info.get('width'), info.get('height')],
            'source_resolution_variant': 'Official1280-wide full-context resampling, not original full-resolution bytes. All versions share canonical photo ID.',
            'current_license': md['LicenseShortName']['value'], 'current_license_url': md['LicenseUrl']['value'],
            'source_metadata': metadata.relative_to(ROOT).as_posix(), 'source_metadata_sha256': sha(metadata),
            'license_status': 'verified_current_Wikimedia_explicit_CC_license',
            'share_alike_required_for_shared_photo_derivatives': 'BY-SA' in md['LicenseShortName']['value'],
            'attribution_and_license_preserved_in_source_metadata': True,
            'image': path.relative_to(ROOT).as_posix(), 'image_sha256': sha(path), 'image_size': list(im.size),
            'unmarked_view': vp.relative_to(ROOT).as_posix(), 'source_reference_size': list(im.size),
            'source_annotations_reference_only': [], 'source_boxes_are_project_truth': False,
            'description': md.get('ImageDescription', {}).get('value'), 'commons_metadata': md,
            'review_status': 'acquired_not_reviewed', 'training_release': False}

    with ThreadPoolExecutor(max_workers=2) as pool:
        entries = list(pool.map(acquire, args.ids))
    result = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'batch': args.batch,
        'entries': entries, 'acquired_originals': len(entries), 'initial_review_completed': 0, 'training_release': False}
    (out/'acquisition_manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'acquired_originals': len(entries), 'ids': args.ids}))


if __name__ == '__main__':
    main()
