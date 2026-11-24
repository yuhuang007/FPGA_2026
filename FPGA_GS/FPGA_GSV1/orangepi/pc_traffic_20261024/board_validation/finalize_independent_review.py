"""Package existing visual findings; validate identity only, never auto-approve labels."""
import collections, datetime, hashlib, json, subprocess, sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
O=R/'review_stage2/independent_codex_board_r2'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    original=read(O/'integrity_before.json')
    changed=[p for p,s in original['protected_files'].items() if not Path(p).exists() or sha(Path(p))!=s]
    assert not changed, changed
    checks=[];all_records=[]
    for batch in ('batch_001','batch_002','batch_003'):
        records=[]
        for p in sorted(O.glob(batch+'_part_*_review.jsonl')):
            run=subprocess.run([sys.executable,str(R/'scripts/validate_review_batch.py'),str(R/'review_stage2/frozen'/batch),str(p)],capture_output=True,text=True,encoding='utf-8',check=True)
            check=json.loads(run.stdout);assert check['integrity_passed'];checks.append({'file':p.name,'validation':check})
            records.extend(json.loads(s) for s in p.read_text(encoding='utf-8').splitlines())
        manifest=read(R/'review_stage2/frozen'/batch/'manifest.json')
        assert [a['candidate_id'] for a in records]==[e['candidate_id'] for e in manifest['entries']]
        for a in records:
            for evidence in a['viewed_evidence']: assert sha(R/evidence['path'])==evidence['sha256']
        out=O/('fillback_'+batch+'.jsonl');assert not out.exists(), 'Preserve published results'
        out.write_text(''.join(json.dumps(a,ensure_ascii=False)+'\n' for a in records),encoding='utf-8')
        all_records.extend(records)
    assert len(all_records)==len({r['candidate_id'] for r in all_records})==48
    groups=read(R/'review_stage2/frozen/batch_001/reference_only/provisional_groups.json')['groups']
    by_id={g['sample_id']:g for g in groups}
    # These subsets describe visually reviewed continuity, not automatic similarity clusters.
    subsets={
      'bus_gate_boulevard':[f's2tld1080_{i:04d}' for i in range(15)]+['s2tld1080_0023','s2tld1080_0024','s2tld1080_0093','s2tld1080_0111'],
      'grey_building_crossroad':[f's2tld1080_{i:04d}' for i in range(16,21)],
      'round_tree_villa_crossroad':[f's2tld1080_{i:04d}' for i in range(212,224)]+['s2tld1080_0322','s2tld1080_0364'],
      'wet_road_LED_approach':['s2tld1080_0280','s2tld1080_0282','s2tld1080_0285']}
    membership=[]
    for scene,ids in subsets.items():
        gs=[by_id[c] for c in ids]
        membership.append({'independently_observed_continuity':scene,'candidate_ids':ids,
             'supplied_leakage_groups':sorted({g['leakage_group'] for g in gs}),
             'supplied_duplicate_components':sorted({g['duplicate_component'] for g in gs}),
             'supplied_proposed_splits':sorted({g['proposed_split'] for g in gs}),
             'supplied_official_splits':sorted({g['official_split'] for g in gs}),
             'proposed_cross_split_in_this_subset':len({g['proposed_split'] for g in gs})>1,
             'requirement':'Keep the observed continuous scene within one split; duplicate component alone is insufficient.'})
    result={'time':datetime.datetime.now().astimezone().isoformat(),'reviewer_type':'AI','human_signoff':False,'training_approval':False,
            'records':48,'old_prechecks_counted':0,'counts':dict(collections.Counter(a['decision'] for a in all_records)),
            'frozen_files_verified_unchanged':len(original['protected_files']),'changed_files':changed,
            'validation_scope':'Hash, identities, completeness of review records; NOT automatic visual approval.',
            'packet_validations':checks,'visually_observed_grouping_subsets':membership,
            'grouping_limits':['Only these 48 images were visually re-reviewed; supplied 400-image grouping and 87 edges were not independently re-reviewed in full.',
              'Different near-duplicate components do not establish different sites; route A/B independence remains unproved.',
              'Similar layouts in 0266, 0280-0285, 0339, 0390 need PC site adjudication, not assertion of an identical site.',
              '0015 and 0021 site relationship to adjacent reviewed scenes remains unresolved.',
              'Official splits remain unassigned. No human or training approval is produced.'],
            'needs_modify':[a['candidate_id'] for a in all_records if a['decision']=='needs_modify'],
            'uncertain':[a['candidate_id'] for a in all_records if a['decision']=='uncertain'],
            'combined_fillbacks':[str((O/('fillback_'+b+'.jsonl')).relative_to(R)) for b in ('batch_001','batch_002','batch_003')]}
    (O/'final_validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['records','counts','frozen_files_verified_unchanged','changed_files','needs_modify','uncertain','visually_observed_grouping_subsets']},ensure_ascii=True,indent=2))
if __name__=='__main__':main()
