"""Acquire only two traceable, explicitly licensed pedestrian-source originals."""
import io
import json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image
from pilot_clean_crops import ROOT, read, sha


def main():
    source = ROOT / 'sources/external_scene_research/commons_pedestrian_query_r1.json'
    query = read(source); assert query['http_status'] == 200
    out = ROOT / 'data/external_scene_candidates_r7'
    assert not (out / 'acquisition_manifest.json').exists(), 'Never overwrite acquired batch'
    for name in ('images', 'views', 'provenance'):
        (out / name).mkdir(parents=True, exist_ok=True)
    selected = []
    for p in query['response']['query']['pages'].values():
        info = p['imageinfo'][0]; md = info['extmetadata']
        if md['LicenseShortName']['value'] in ('CC0', 'CC BY 4.0'):
            selected.append((p, info, md))
    assert len(selected) == 2

    def acquire(item):
        page, info, md = item; pid = str(page['pageid'])
        resolution_path = ROOT / f'sources/external_scene_research/commons_pedestrian_resolution_{pid}.json'
        # Original downloads returned429 with Retry-After, retained in provenance.
        # Use the separately requested official full-context resolution variant;
        # never claim these are original full-resolution bytes or extra photos.
        resolution = read(resolution_path); assert resolution['http_status'] == 200
        variant = next(iter(resolution['response']['query']['pages'].values()))['imageinfo'][0]
        r = requests.get(variant['thumburl'], headers={'User-Agent': 'TrafficBodyDatasetResearch/1.0'}, timeout=35)
        r.raise_for_status(); assert len(r.content) < 20000000
        im = Image.open(io.BytesIO(r.content)); im.load()
        assert list(im.size) == [variant['thumbwidth'], variant['thumbheight']]
        path = out / 'images' / ('commons_' + pid + '.jpg'); path.write_bytes(r.content)
        view = im.convert('RGB'); view.thumbnail((900, 700)); vp = out / 'views' / path.name
        view.save(vp, quality=92)
        metadata = out / 'provenance' / ('commons_' + pid + '_metadata.json')
        metadata.write_text(json.dumps({'recorded_at': datetime.now(timezone.utc).isoformat(),
            'query_evidence': source.relative_to(ROOT).as_posix(), 'query_evidence_sha256': sha(source),
            'page': page, 'official_resolution_variant': resolution_path.relative_to(ROOT).as_posix(),
            'official_resolution_variant_sha256': sha(resolution_path),
            'no_source_project_labels': True}, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'candidate_id': 'commons_scene_' + pid, 'source_dataset': 'Wikimedia_Commons',
                'source_dataset_image_id': pid, 'photo_id': 'commons_page_' + pid,
                'title': page['title'], 'author': md.get('Artist', {}).get('value', ''),
                'photo_page': info['descriptionurl'], 'download_url': variant['thumburl'],
                'original_full_resolution_size': [info['width'], info['height']],
                'source_resolution_variant': 'Official1280-wide full-context resampling; original download429, not original full-resolution bytes. Canonical photo ID shared across all resolutions.',
                'current_license': md['LicenseShortName']['value'], 'current_license_url': md['LicenseUrl']['value'],
                'source_metadata': metadata.relative_to(ROOT).as_posix(), 'source_metadata_sha256': sha(metadata),
                'license_status': 'verified_current_Wikimedia_CC0_or_CC_BY',
                'image': path.relative_to(ROOT).as_posix(), 'image_sha256': sha(path), 'image_size': list(im.size),
                'unmarked_view': vp.relative_to(ROOT).as_posix(), 'source_reference_size': list(im.size),
                'source_annotations_reference_only': [], 'source_boxes_are_project_truth': False,
                'description': md.get('ImageDescription', {}).get('value'),
                'commons_metadata': md, 'review_status': 'acquired_not_reviewed', 'training_release': False}

    with ThreadPoolExecutor(max_workers=2) as pool:
        entries = list(pool.map(acquire, selected))
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'batch': 'r7', 'entries': entries,
              'acquired_originals': len(entries), 'initial_review_completed': 0, 'training_release': False}
    (out / 'acquisition_manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'acquired_originals': len(entries), 'ids': [e['candidate_id'] for e in entries]}))


if __name__ == '__main__':
    main()
