"""Temporary integrity holds supplement, never overwrite, frozen qualifications."""
from pilot_clean_crops import ROOT, read, sha


def current_holds():
    path = ROOT/'reports/crop_integrity_holds.json'
    if not path.exists():
        return {}, None
    result = read(path)
    holds = {}
    for entry in result['entries']:
        assert entry['status'] in ('active', 'resolved')
        for evidence in entry['evidence']:
            assert sha(ROOT/evidence['path']) == evidence['sha256'], 'Hold evidence changed'
        if entry['status'] == 'active':
            assert entry['applies_to_all_label_versions_until_explicit_resolution'] is True
            holds[entry['candidate_id']] = entry
        else:
            assert entry['resolution'] and entry['resolution_evidence']
            for evidence in entry['resolution_evidence']:
                assert sha(ROOT/evidence['path']) == evidence['sha256']
    return holds, {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
