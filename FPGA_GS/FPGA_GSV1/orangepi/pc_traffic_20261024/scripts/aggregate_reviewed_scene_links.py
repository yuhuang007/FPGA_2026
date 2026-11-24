"""Aggregate already recorded visual observations; never grant split approval."""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import hashlib, json

R = Path(__file__).resolve().parents[1]

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    labels = {p.stem: (p, read(p)) for p in (R/'review_stage2/first_pass').glob('*.json')}
    proposals = {x['sample_id']: x for x in read(R/'data/provisional_groups.json')['groups']}
    scenes = defaultdict(list)
    for sid, (p, a) in labels.items():
        obs = a.get('group_observation')
        if obs:
            scenes[obs['scene']].append(sid)
    groups, constraints = [], []
    for scene, members in sorted(scenes.items()):
        members.sort()
        proposed_splits = sorted({proposals[s]['proposed_split'] for s in members if s in proposals})
        records = []
        for sid in members:
            p, a = labels[sid]
            assert sha(R/a['image_path']) == a['image_sha256']
            obs = a['group_observation']
            records.append({'candidate_id': sid, 'image_sha256': a['image_sha256'],
                'annotation_sha256': sha(p), 'annotation_file': p.relative_to(R).as_posix(),
                'visual_evidence': obs['same_scene_evidence'],
                'view_evidence': a.get('evidence_sha256', {}),
                'compared_candidates': obs['visual_compared_candidates']})
            for n in obs['visual_compared_candidates']:
                other = f's2tld1080_{n:04d}' if isinstance(n, int) else n
                if other == sid or other not in labels:
                    continue
                rel = obs.get('relation', 'unspecified')
                if rel == 'visually_distinct_scene_pending_route_link':
                    continue
                constraints.append({'a': sid, 'b': other, 'relation': rel,
                    'scope': 'same_recorded_scene' if other in members else 'conservative_route_or_overlap_link_pending_site_audit',
                    'evidence_annotation_sha256': sha(p), 'must_not_cross_split_until_resolved': True})
        groups.append({'scene': scene, 'count': len(members), 'members': records,
            'existing_proposed_splits': proposed_splits,
            'proposal_conflict': len(proposed_splits) > 1,
            'site_confirmed': False, 'official_split': 'unassigned'})
    out = {'recorded_at': datetime.now(timezone.utc).isoformat(),
        'method': 'Aggregate existing individual full-frame and native-crop review observations. This aggregation is not a new visual review, independent verification, human signature or split release.',
        'reviewer_type': 'AI', 'human_signoff': False, 'passed': False,
        'reviewed_observation_images': sum(g['count'] for g in groups),
        'scene_groups': groups, 'cross_sample_constraints': constraints,
        'existing_87_pair_review': {'file': 'reports/near_duplicate_review.json', 'sha256': sha(R/'reports/near_duplicate_review.json'), 'unchanged': True},
        'provisional_groups_sha256': sha(R/'data/provisional_groups.json'),
        'proposal_conflict_groups': [g['scene'] for g in groups if g['proposal_conflict']],
        'blocking': ['Independent site/route identity and group verification pending',
            'Official train/val/holdout split and manual scene/near-duplicate release pending',
            'Same-scene changed traffic/state is not sufficient reason to split neighboring captures']}
    (R/'reports/reviewed_scene_link_audit.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'observation_images': out['reviewed_observation_images'], 'scene_groups': len(groups),
        'constraints': len(constraints), 'proposal_conflicts': out['proposal_conflict_groups'], 'split_released': False}))

if __name__ == '__main__':
    main()
