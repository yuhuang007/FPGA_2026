"""Prepare source-bound leakage checks, never infer independence from hash distance."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, csv, hashlib, io, json, zipfile
import numpy as np
from PIL import Image, ImageDraw

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dhash(im):
    a=np.asarray(im.convert('L').resize((17,16),Image.Resampling.LANCZOS))
    return int.from_bytes(np.packbits(a[:,1:]>a[:,:-1]).tobytes(),'big')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='review_stage2/source_split_audit_r1')
    ap.add_argument('--ids',nargs='+')
    ap.add_argument('--evidence',nargs='+')
    ap.add_argument('--reserved-final-test-ids',nargs='+',default=[])
    args=ap.parse_args()
    out=R/args.output;assert not out.exists(),'Preserve audit packet'
    out.mkdir();(out/'views').mkdir()
    archive=R/'data/s2tld_1080.zip';provenance=read(R/'data/archive_provenance.json')
    assert sha(archive)==provenance['sha256']
    originals=[]
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not name.lower().endswith(('.jpg','.jpeg')):continue
            raw=z.read(name);im=Image.open(io.BytesIO(raw));im.draft('RGB',(512,288));im.load()
            originals.append({'source_member':name,'sha256':hashlib.sha256(raw).hexdigest(),'dhash':dhash(im)})
        assert len(originals)==1222
        original_hashes={x['sha256'] for x in originals}
        ext=[]
        latest={}
        mps=list((R/'review_stage2').glob('external_scene_pilot_r*/manifest.json'))+list((R/'review_stage2/external_scene_revisions').glob('*/manifest.json'))
        for mp in sorted(mps,key=lambda p:read(p)['recorded_at']):
            for e in read(mp)['entries']:latest[e['candidate_id']]=(mp,e)
        for mp,e in latest.values():
                if args.ids and e['candidate_id'] not in args.ids:continue
                p=mp.parent/e['image'];assert sha(p)==e['image_sha256']
                if e['candidate_id'] in {'coco_scene_000000184400','coco_scene_000000577932','coco_scene_000000534639','coco_scene_000000176037'}:continue
                a=read(mp.parent/e['annotation']);im=Image.open(p).convert('RGB');eh=dhash(im)
                closest=sorted(originals,key=lambda x:(eh^x['dhash']).bit_count())[:2];pairs=[]
                for k,near in enumerate(closest):
                    nearim=Image.open(io.BytesIO(z.read(near['source_member']))).convert('RGB')
                    can=Image.new('RGB',(800,350),'#202020');d=ImageDraw.Draw(can)
                    for j,source in enumerate((im,nearim)):
                        v=source.copy();v.thumbnail((390,310));can.paste(v,(j*400,30))
                    d.text((5,7),e['candidate_id']+' vs archived source; screening pair only',fill='white')
                    view=out/'views'/f'{e["candidate_id"]}_nearest_{k+1}.jpg';can.save(view,quality=90)
                    pairs.append({'source_member':near['source_member'],'source_sha256':near['sha256'],
                        'dhash256_distance':(eh^near['dhash']).bit_count(),'view':view.relative_to(R).as_posix(),'view_sha256':sha(view)})
                ext.append({'candidate_id':e['candidate_id'],'photo_id':e['original_photo_id'],'image':p.relative_to(R).as_posix(),
                    'image_sha256':e['image_sha256'],'exact_archive_sha_overlap':e['image_sha256'] in original_hashes,
                    'scene_id':e['scene_id'],'location_evidence':a['location_basis'],'source_variants_must_link':e['source_variants_must_link'],
                    'closest_screening_pairs':pairs,
                    'planned_split':'holdout_reserved_before_fitting' if e['candidate_id'] in args.reserved_final_test_ids else e.get('planned_split','unassigned_pending_group_audit')})
    evidence_paths=['data/archive_provenance.json','reports/archive_metadata_audit.json','data/group_relations_r3.json',
        'reports/near_duplicate_review.json','reports/resume_group_review.json','data/proposed_source_split_r4.json',
        'reports/external_scene_license_audit_r1.json','reports/external_scene_license_audit_r2.json',
        'review_stage2/independent_external_scene_r1/external_scene_r1_review.jsonl']
    if args.ids:
        evidence_paths=['data/archive_provenance.json','reports/archive_metadata_audit.json','data/group_relations_r3.json',
            'reports/near_duplicate_review.json','data/group_releases/r1/manifest.json',
            'reports/external_scene_license_audit_r3.json','reports/external_scene_license_audit_r7.json',
            'sources/external_scene_research/commons_pedestrian_query_r1.json']
    if args.evidence:evidence_paths=args.evidence
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'reviewer':'Codex_PC_AI_source_audit_preparation',
        'reviewer_type':'AI','human_signoff':False,'archive_originals_screened':len(originals),'external_candidates':ext,
        'original400_policy':{'planned_split':'train','joint_leakage_unit':'unresolved_route_A_B_joint_hold',
            'same_physical_site_claim':False,'preserve_observed_and_uncertain_edges_separately':True},
        'all_exact_hashes_disjoint':all(not x['exact_archive_sha_overlap'] for x in ext),
        'screening_is_not_independence_proof':True,'visual_pair_review_completed':False,
        'required_independent_review':['Verify saved geographic source evidence and the actual source scenes, not filename dates or source dataset names.',
            'Check closest source pairs in small views and existing same-scene/near-duplicate constraints; record any unresolved cross-source association.',
            'Keep all resolution variants, crops and original-photo identities in one split. All original400 stay on training side.',
            'Do not claim a valid final test set. Do not sign label/crop/training approval from this scene review.',
            'State whether evidence supports independent validation groups; otherwise identify exact missing evidence.'],
        'evidence':[{'path':p,'sha256':sha(R/p)} for p in evidence_paths],
        'passed':False,'official_split_released':False,'training_release':False,
        'final_test_status':('Explicit new candidates reserved before any fitting: '+', '.join(args.reserved_final_test_ids)+'. Excluded from tuning/calibration; group/clean export still require verification; no test adequacy claimed.'
            if args.reserved_final_test_ids else 'Existing final-test sources remain isolated from tuning/calibration; this packet does not approve coverage.'),
        'new_final_test_reserved_ids':args.reserved_final_test_ids}
    (out/'audit_request.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'archive_originals_screened':len(originals),'external_candidates':len(ext),
        'exact_hash_overlap':any(e['exact_archive_sha_overlap'] for e in ext),'official_split_released':False}))

if __name__=='__main__':main()
