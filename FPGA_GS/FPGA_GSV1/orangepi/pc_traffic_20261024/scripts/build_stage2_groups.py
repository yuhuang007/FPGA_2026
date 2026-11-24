"""Persist actual visual duplicate review and conservative, non-approved grouping.

Visual decisions are supplied separately by the reviewer, never inferred here.
The proposed split is diagnostic only; candidates.csv remains unassigned.
"""
from pathlib import Path
from collections import Counter
import csv, hashlib, json
import numpy as np
from PIL import Image

R=Path(__file__).resolve().parents[1]
def read(p): return json.loads((R/p).read_text(encoding='utf-8'))
def save(p,x): (R/p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    rows=list(csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig')))
    visuals=read('review_stage2/visual_snapshot_0400.json')
    pairs=read('reports/near_duplicate_candidates.json')['pairs']
    decisions=read('review_stage2/duplicate_visual_decisions.json')
    assert len(rows)==len(visuals)==400 and len(pairs)==len(decisions)==87
    parent=list(range(400))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return i
    def union(a,b): parent[root(b)]=root(a)
    dup=[]; redundant={}
    for k,(p,d) in enumerate(zip(pairs,decisions)):
        assert d['pair_index']==k and d['must_link'] is True
        a,b=[int(p[x].rsplit('_',1)[1]) for x in ('a','b')]
        union(a,b)
        aa=np.asarray(Image.open(R/rows[a]['image_path']).convert('RGB'))
        bb=np.asarray(Image.open(R/rows[b]['image_path']).convert('RGB'))
        delta=np.abs(aa.astype(np.int16)-bb.astype(np.int16))
        x={**p,**d,'file_sha_equal':rows[a]['sha256']==rows[b]['sha256'],
           'decoded_pixels_equal':bool(np.array_equal(aa,bb)),
           'decoded_mean_absolute_error':float(delta.mean()),'decoded_max_absolute_error':int(delta.max()),
           'decoded_pixel_sha_a':hashlib.sha256(aa.tobytes()).hexdigest(),
           'decoded_pixel_sha_b':hashlib.sha256(bb.tobytes()).hexdigest()}
        if d['decision']=='visually_identical_check_pixels':
            x['final_decision']='same_capture_reencoded' if not x['decoded_pixels_equal'] else 'decoded_exact_duplicate'
            x['interpretation']='相同画面内相机时间戳和车辆/行人位置的AI视觉判断；像素差异单独保留，不将MAE阈值当同帧证明。'
            redundant[max(a,b)]={'keep':min(a,b),'pair_index':k,'reason':x['final_decision']}
        else: x['final_decision']='same_scene_distinct_capture_must_link'
        dup.append(x)
    comps={}
    for i in range(400): comps.setdefault(root(i),[]).append(i)
    save('reports/near_duplicate_review.json',{'reviewer_type':'AI','human_confirmed':False,
        'pairs_reviewed':87,'pairs':dup,'redundant_candidates':redundant,
        'note':'同景不同帧保留候选并绑定同组；相同capture重复只保留较小索引，仍须独立复审。'})
    save('data/near_duplicate_components.json',{'method':'connected components of 87 visually confirmed must-link edges',
        'components':[{'component_id':f'nd_{min(v):04d}','members':[rows[i]['sample_id'] for i in v]} for v in comps.values()]})
    groups=[]
    for v in visuals:
        i=v['index']
        # Deliberately broad visual route groups. These are NOT named independent intersections.
        group='route_visual_A' if i<154 else 'route_visual_B'
        groups.append({'sample_id':rows[i]['sample_id'],'image_sha256':rows[i]['sha256'],
            'visual_scene':v['scene'],'duplicate_component':f'nd_{min(comps[root(i)]):04d}',
            'leakage_group':group,'proposed_split':'train' if group=='route_visual_A' else 'val',
            'official_split':'unassigned','site_id':None,'site_confirmed':False,
            'group_review_status':'AI_visual_conservative_pending_independent_and_human',
            'redundant':redundant.get(i),
            'basis':'whole-scene visual landmarks and recurring road layout; NOT filename prefix'})
    lookup={r['sample_id']:r for r in groups}
    violations=[p for p in pairs if lookup[p['a']]['proposed_split']!=lookup[p['b']]['proposed_split']]
    save('data/provisional_groups.json',{'status':'proposal_not_training_split','groups':groups,
        'rationale':[
            'route_visual_A: 树荫公交门岗主路、红漕路干道与饱和树冠队列未能证明独立路口，保守合组。',
            'route_visual_B: 住宅、夜雨、横排高楼下坡、园区环路多个反复路口，不能证明日夜独立，全部保守合组。',
            'H与M高楼下坡道路合并，I反复出现的弯道合并；G/O墙侧待转区日夜关联未排除，合并。',
            '两route组只是防泄漏约束，不能宣称已确认两个独立路口；若复审发现跨组同址，必须进一步合组。'],
        'external_test':{'available':False,'metrics':'N/A'},
        'regression_only':['SC_BT.mp4','SC_BT2.mp4','SC_YJ.mp4','SC_YJ2.mp4'],
        'regression_allowed_in_train_val_or_int8_calibration':False})
    save('reports/split_audit.json',{'passed':False,'reviewer_type':'AI','human_signoff':None,
        'candidate_count':400,'near_duplicate_pairs_visually_checked':87,
        'nontrivial_near_duplicate_components':sum(len(v)>1 for v in comps.values()),
        'same_capture_redundant_images':len(redundant),
        'proposed_group_counts':dict(Counter(r['leakage_group'] for r in groups)),
        'proposed_split_counts':dict(Counter(r['proposed_split'] for r in groups)),
        'near_duplicate_cross_proposed_split':len(violations),
        'official_split_counts':{'unassigned':400},
        'blocking':['independent visual site/group review pending','human confirmation required by annotation policy pending',
            'revised labels not all complete','route A/B independence not established'],
        'external_test_scenes':0,'final_generalization_metrics':'N/A'})
    print(json.dumps({'pairs':87,'redundant':redundant,'components':len(comps),
        'nontrivial_components':sum(len(v)>1 for v in comps.values()),'cross_proposal':len(violations)},ensure_ascii=False))
if __name__=='__main__': main()
