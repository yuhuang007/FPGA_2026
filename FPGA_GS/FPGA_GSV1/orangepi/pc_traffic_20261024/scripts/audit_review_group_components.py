"""Bind existing visual constraints to current labels; never approve a split."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv, hashlib, json

R = Path(__file__).resolve().parents[1]


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    rows = list(csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig')))
    proposals = {a['sample_id']: a for a in read(R/'data/provisional_groups.json')['groups']}
    labels = {a['sample_id']: (R/a['annotation_file'], read(R/a['annotation_file'])) for a in rows}
    parents = {sid: sid for sid in labels}
    edges = []

    def root(sid):
        while parents[sid] != sid:
            parents[sid] = parents[parents[sid]]
            sid = parents[sid]
        return sid

    def link(a, b, relation, evidence):
        assert a in labels and b in labels
        if a == b:
            return
        parents[root(b)] = root(a)
        edges.append({'a': a, 'b': b, 'relation': relation, 'evidence': evidence})

    scenes = defaultdict(list)
    for sid, (path, label) in labels.items():
        assert sha(R/label['image_path']) == label['image_sha256']
        obs = label.get('group_observation')
        if not obs or obs.get('relation') == 'visually_distinct_scene_pending_route_link':
            continue
        scenes[obs['scene']].append(sid)
        for other in obs['visual_compared_candidates']:
            other = f's2tld1080_{other:04d}' if isinstance(other, int) else other
            link(sid, other, obs['relation'], {'annotation': path.relative_to(R).as_posix(),
                'annotation_sha256': sha(path), 'visual_basis': obs['same_scene_evidence']})
    for scene, members in scenes.items():
        for sid in members[1:]:
            link(members[0], sid, 'recorded_same_scene_conservative_must_link', {'scene': scene})
    near_path = R/'reports/near_duplicate_review.json'
    near = read(near_path)
    for pair in near['pairs']:
        assert pair['must_link'] is True
        link(pair['a'], pair['b'], pair['final_decision'], {
            'file': near_path.relative_to(R).as_posix(), 'sha256': sha(near_path), 'pair_index': pair['pair_index']})

    components = defaultdict(list)
    for sid in labels:
        components[root(sid)].append(sid)
    output = []
    for members in sorted(components.values(), key=lambda a: min(a)):
        members.sort()
        split_proposals = sorted({proposals[sid]['proposed_split'] for sid in members})
        output.append({'component_id': 'review_link_'+members[0].rsplit('_', 1)[1],
            'members': members, 'count': len(members), 'proposed_splits': split_proposals,
            'proposal_conflict': len(split_proposals) > 1, 'official_split': 'unassigned',
            'independent_site_identity_confirmed': False})
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(),
        'method': 'Graph of already recorded individual visual comparisons, conservative same-scene constraints and existing 87 reviewed near-duplicate pairs; no new image review or site confirmation.',
        'active_label_count': len(labels), 'existing_near_duplicate_pairs': len(near['pairs']),
        'recorded_scene_count': len(scenes), 'edge_count': len(edges),
        'component_count': len(output), 'component_size_histogram': dict(Counter(x['count'] for x in output)),
        'proposal_conflicts': [x['component_id'] for x in output if x['proposal_conflict']],
        'images_without_individual_group_observation': [sid for sid, (_, a) in labels.items() if not a.get('group_observation')],
        'active_labels': {sid: {'file': p.relative_to(R).as_posix(), 'sha256': sha(p)} for sid, (p, _) in labels.items()},
        'components': output, 'constraints': edges,
        'passed': False, 'human_signoff': False, 'official_split_released': False,
        'blocking': ['Genuine independent group/site audit pending',
            'Route A/B independence is unproven even if recorded edges have no cross-proposal conflict',
            'Human confirmation and formal split release pending; singleton components do not establish independent sites']}
    (R/'reports/review_group_components_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['active_label_count', 'edge_count', 'component_count', 'component_size_histogram', 'proposal_conflicts', 'official_split_released']}))


if __name__ == '__main__':
    main()
