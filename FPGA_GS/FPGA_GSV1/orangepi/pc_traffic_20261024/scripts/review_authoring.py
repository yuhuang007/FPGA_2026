"""Serialize reviewer-entered findings only; never derive labels from XML or models."""
import json
from resume_stage2_review import R, O, record

def B(box,ident='body_1',kind='motor_vehicle',layout='vertical',occlusion='none',truncated=False):
    return {'id':ident,'type':'body','bbox_xyxy':box,'kind':kind,'layout':layout,
            'group_id':None,'occlusion':occlusion,'truncated':truncated,'control_relation':'unknown',
            'quality_flags':[],'kind_basis':'Visible signal housing and readable signal morphology; not assigned by road position or XML class.'}

def E(box,color,ident='emitter_1',parent='body_1',symbol='circle',arrow='unknown',flags=None):
    return {'id':ident,'type':'emitter','parent_id':parent,'bbox_xyxy':box,'state':color,
            'color_readable':color!='unknown','symbol':symbol,'arrow_direction':arrow,
            'quality_flags':flags or [],'unknown_reason':'saturation' if color=='unknown' else None}

def I(box,ident='ignore_1',reason='cannot_identify_kind'):
    return {'id':ident,'type':'ignore','bbox_xyxy':box,'kind':'unknown','unknown_reason':reason,
            'quality_flags':['ambiguous_body'],'control_relation':'unknown'}

def N(box,ident,reason):
    return {'id':ident,'type':'hard_negative','bbox_xyxy':box,'reason':reason}

def commit(entries):
    images=[]
    for i,entry in entries.items():
        objs,note,group=entry[:3]
        arbitration=entry[3] if len(entry)>3 else []
        images.append({'index':i,'full_image_checked':True,'detail_checked':True,
            'objects':objs,'note':note,
            'arbitration':arbitration+['Independent whole-image omission/geometry/kind review pending; no approval inherited from source XML.']+
                (['Unresolved ignore regions must be adjudicated or the image explicitly excluded; never silently exported as background.'] if any(x['type']=='ignore' for x in objs) else []),
            'group_observation':{'scene':group[0],'same_scene_evidence':group[1],
                'visual_compared_candidates':group[2],
                'relation':group[3] if len(group)>3 else 'same_scene_distinct_captures_must_link',
                'redundant_capture':False,'site_confirmed':False,'official_split':'unassigned','human_confirmed':False},
            'evidence':[f'review_stage2/resume_evidence/{i:04d}_full.jpg',f'review_stage2/resume_evidence/{i:04d}_contexts.png']})
    path=O/f'resume_decisions_{min(entries):04d}_{max(entries):04d}.json'
    assert not path.exists(),f'Decision packet already exists: {path}'
    path.write_text(json.dumps({'reviewer_type':'AI','human_signoff':False,'images':images},ensure_ascii=False,indent=2),encoding='utf-8')
    record(path)
