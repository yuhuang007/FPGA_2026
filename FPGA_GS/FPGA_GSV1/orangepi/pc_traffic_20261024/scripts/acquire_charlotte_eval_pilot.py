"""Acquire one pinned supplementary eval archive; never release native labels as truth."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/public_datasets/charlotte_eval_pilot_r1'
REVISION = '4528c40995c9fd3ae9649896158409bd84e21109'
EXPECTED_SHA = '26cc419e93ca5694be49750461144a45e587d2d88d23120de6735e747ab3ef49'
EXPECTED_BYTES = 2124473061


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / 'CTLD-day_img.7z'
    partial = archive.with_suffix('.7z.partial')
    manifest = OUT / 'acquisition_manifest.json'
    url = ('https://huggingface.co/datasets/samxu29/Charlotte_Area_Traffic_Light_Dataset/'
           f'resolve/{REVISION}/CTLD-day_img.7z?download=true')
    record = dict(recorded_at=datetime.now(timezone.utc).isoformat(),
                  purpose='Supplementary foreign independent evaluation candidate, not Chinese accuracy evidence',
                  revision=REVISION, url=url, expected_bytes=EXPECTED_BYTES,
                  expected_sha256=EXPECTED_SHA, license='MIT declared on pinned dataset card',
                  license_evidence='sources/external_scene_research/public_eval_research_r5/charlotte_readme.txt',
                  source_geography='Charlotte Area per publisher dataset name; precise route metadata not yet verified',
                  native_labels_are_project_truth=False, qualified_originals=0,
                  frozen_training_release_changed=False, status='acquiring')
    def save():
        manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    if not archive.exists():
        offset = partial.stat().st_size if partial.exists() else 0
        record['downloaded_bytes'] = offset
        save()
        response = requests.get(url, headers={'Range': f'bytes={offset}-'} if offset else {},
                                stream=True, timeout=(30, 60))
        response.raise_for_status()
        if offset:
            assert response.status_code == 206 and response.headers['Content-Range'].startswith(f'bytes {offset}-')
        tick = time.monotonic()
        with partial.open('ab' if offset else 'wb') as stream:
            for block in response.iter_content(4 * 1024 * 1024):
                stream.write(block)
                offset += len(block)
                assert offset <= EXPECTED_BYTES
                if time.monotonic() - tick > 25:
                    record.update(downloaded_bytes=offset, updated_at=datetime.now(timezone.utc).isoformat())
                    save()
                    print(json.dumps({'downloaded_bytes': offset, 'expected_bytes': EXPECTED_BYTES}), flush=True)
                    tick = time.monotonic()
        assert offset == EXPECTED_BYTES
        digest = hashlib.file_digest(partial.open('rb'), 'sha256').hexdigest()
        assert digest == EXPECTED_SHA, digest
        partial.rename(archive)
    assert archive.stat().st_size == EXPECTED_BYTES
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert digest == EXPECTED_SHA
    record.update(status='archive_SHA_verified_pending_bounded_visual_schema_audit',
                  downloaded_bytes=archive.stat().st_size, actual_sha256=digest,
                  completed_at=datetime.now(timezone.utc).isoformat())
    save()
    print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
