import json,hashlib,datetime
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
out=R/'review_stage2/independent_external_scene_r1/recheck_external_r2.jsonl'
assert not out.exists()
rows=[]
for t in read(R/'review_stage2/external_recheck_tasks_r2.json')['tasks']:
 mp=R/t['manifest'];assert sha(mp)==t['manifest_sha256'];e=next(x for x in read(mp)['entries'] if x['candidate_id']==t['candidate_id']);ap=mp.parent/e['annotation'];ip=mp.parent/e['image'];a=read(ap)
 assert sha(ip)==t['image_sha256']==e['image_sha256'];assert sha(ap)==t['annotation_sha256']==e['annotation_sha256'];assert a['label_version']==e['label_version']==t['label_version']
 roch=t['candidate_id'].endswith('577932')
 obs=([{'object':'body_1/negative_sign','conclusion':'原像素放大仍可见L形组合右下发光元件；原hard_negative已移除，组合保留ignore且不作为负背景符合证据。机动车灯存在可确认，物理灯体个数与完整边界不能从共同背板确定；当前排除训练的处理可接受。'}] if roch else [{'object':'body_1.bbox_xyxy','conclusion':'独立原图局部与4x坐标格核对：三层遮檐最左约389、右侧黑壳至约430、上遮檐约273、下壳约367。新[389,273,430,367]排除了上方背板和右下禁掉头标牌，当前几何修改可接受；本次不重评灯色。'}])
 evidence=[R/('review_stage2/independent_external_scene_r1/'+('000000577932_unmarked.png' if roch else '000000520009_unmarked.png'))]
 if not roch:
  grid=R/'reports/halifax_body_bounds_check.png';assert sha(grid)==a['new_geometry_evidence']['sha256'];evidence.append(grid)
 rows.append(dict(candidate_id=t['candidate_id'],image_sha256=sha(ip),reviewed_annotation_sha256=sha(ap),manifest_sha256=sha(mp),revision_manifest=t['manifest'],label_version=t['label_version'],reviewer_id='Codex_board_independent_AI_external_r2_20261025',reviewer_type='AI',independent_from_first_pass=True,reviewed_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),old_precheck_reused_as_formal_review=False,previous_review=t['previous_review'],old_review_acceptance_inherited=False,full_original_checked=False,omission_search_completed=False,attributes_checked=False,bounds_checked=True,kind_checked=roch,checks_scope=t['affected_fields'],decision_scope='Targeted amended fields only. Original full-image review retained; no new omission/color certification, no training approval.',actual_method=['Viewed existing unmarked original-pixel contextual crop; Halifax additionally checked coordinate grid. Read current SHA-bound amendment.'],decision='accept',findings=obs,PC_arbitration_required=[],viewed_evidence=[dict(path=p.relative_to(R).as_posix(),sha256=sha(p)) for p in evidence],corrected_annotation_file=None,human_signoff=False,training_approval=False))
out.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8');print(out)
