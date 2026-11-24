"""Bind explicitly authored independent findings to immutable packet identities."""
import collections,datetime,hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
O=R/'review_stage2/independent_codex_board_r2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    authored=Path(sys.argv[1]);data=read(authored);batch=data['batch'];part=data['part'];base=R/'review_stage2/frozen'/batch
    manifest=read(base/'manifest.json');entries={e['candidate_id']:e for e in manifest['entries']}
    templates={a['candidate_id']:a for a in map(json.loads,(base/'review_fillback.jsonl').read_text(encoding='utf-8').splitlines())}
    records=[]
    for observation in data['reviews']:
        cid=observation['candidate_id'];e=entries[cid];a=dict(templates[cid]);assert sha(base/e['image'])==e['image_sha256'];assert sha(base/e['annotation'])==e['annotation_sha256']
        paths=[O/'views'/batch/(cid+'_full.jpg'),O/'views'/batch/(cid+'_detail.jpg')]
        assert all(p.exists() for p in paths)
        a.update({'reviewer_id':'Codex_board_independent_AI_20261024_r2','reviewer_type':'AI','independent_from_first_pass':True,
                  'reviewed_at':datetime.datetime.now().astimezone().isoformat(),'label_version':e['label_version'],
                  'manifest_sha256':sha(base/'manifest.json'),
                  'actual_method':['Independent visual inspection of unmarked full original resized to 960x540; no initial boxes in full view.',
                                   'Read frozen per-object JSON, then inspect independently generated contextual crops with boxes, nearest-neighbor <=4x; interpolation adds no evidence.',
                                   'Compare visible scene/vehicle/layout across this reviewed block and inspect supplied grouping/split status; not a complete 400-image pair audit.'],
                  'viewed_evidence':[{'path':str(p.relative_to(R)),'sha256':sha(p)} for p in paths],
                  'full_original_checked':True,'omission_search_completed':True,'omission_search_scope':'Full-frame visual search at stated display scale; not assertion all tiny unresolvable bodies exhausted.',
                  'bounds_checked':True,'kind_checked':True,'attributes_checked':True,
                  'decision':observation['decision'],'decision_scope':'Frozen AI draft accept/revise/uncertain, not training release or human certification',
                  'findings':observation['findings'],'grouping_review':observation['grouping_review'],
                  'PC_arbitration_required':observation.get('PC_arbitration_required',[]),'human_signoff':False,'training_approval':False,
                  'old_precheck_reused_as_formal_review':False})
        records.append(a)
    target=O/f'{batch}_part_{part:02d}_review.jsonl';assert not target.exists(),'Do not overwrite published review'
    target.write_text(''.join(json.dumps(a,ensure_ascii=False)+'\n' for a in records),encoding='utf-8')
    protected=read(O/'integrity_before.json')['protected_files'];changed=[p for p,want in protected.items() if not Path(p).exists() or sha(Path(p))!=want];assert not changed
    all_records=[]
    for p in sorted(O.glob('batch_*_review.jsonl')):all_records.extend(json.loads(s) for s in p.read_text(encoding='utf-8').splitlines())
    assert len({a['candidate_id'] for a in all_records})==len(all_records)
    summary={'updated_at':datetime.datetime.now().astimezone().isoformat(),'reviewer_type':'AI','human_signoff':False,
             'completed_independent_frozen_label_reviews':len(all_records),'old_prechecks_counted':0,'training_approvals':0,
             'decisions':dict(collections.Counter(a['decision'] for a in all_records)),
             'by_label_version':dict(collections.Counter(a['label_version'] for a in all_records)),
             'published_files':[str(p.relative_to(R)) for p in sorted(O.glob('batch_*_review.jsonl'))],
             'frozen_files_unchanged':True,'arbitration':[{'candidate_id':a['candidate_id'],'items':a['PC_arbitration_required']} for a in all_records if a['PC_arbitration_required']]}
    (O/'progress.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'saved':str(target),'records':len(records),'total':len(all_records),'decisions':summary['decisions']},ensure_ascii=True))
if __name__=='__main__':main()
