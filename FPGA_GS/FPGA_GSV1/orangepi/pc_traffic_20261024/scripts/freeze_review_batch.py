"""Freeze explicit revised AI labels for independent review, never sign for reviewer 2."""
from pathlib import Path
import csv,hashlib,json,shutil,sys,time
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    args=[a for a in sys.argv[1:] if a!='--no-readme']
    write_readme='--no-readme' not in sys.argv[1:]
    name=args[0] if args else 'batch_001'
    labels=sorted((R/'review_stage2/first_pass').glob('*.json'))
    if len(args)>1:
        indices={int(x) for x in args[1:]}
        labels=[p for p in labels if int(p.stem.rsplit('_',1)[1]) in indices]
        assert len(labels)==len(indices), 'Missing requested first-pass labels'
    out=R/'review_stage2/frozen'/name
    if out.exists():raise SystemExit('Refusing to overwrite immutable batch: '+str(out))
    out.mkdir(parents=True)
    for sub in ['images','labels','overlays','evidence','reference_only']:(out/sub).mkdir()
    entries=[]; tasks=[]
    for p in labels:
        label=json.loads(p.read_text(encoding='utf-8')); sid=label['candidate_id']
        src=R/label['image_path']; assert sha(src)==label['image_sha256']
        for source,target in [(src,out/'images'/f'{sid}.jpg'),(p,out/'labels'/p.name),
            (R/'review_stage2/overlays'/f'{sid}.jpg',out/'overlays'/f'{sid}.jpg')]:
            shutil.copy2(source,target)
        i=int(sid.rsplit('_',1)[1]); z=R/'review_stage2/zooms'/f'{i:04d}.png'
        if z.exists():shutil.copy2(z,out/'evidence'/z.name)
        evidence=[]
        for relative in label.get('evidence_files',[]):
            source=R/relative; target=out/'evidence'/source.name
            if target.exists():assert sha(target)==sha(source), 'Evidence filename collision'
            else:shutil.copy2(source,target)
            evidence.append({'file':'evidence/'+source.name,'sha256':sha(source),'original_path':relative})
        entries.append({'candidate_id':sid,'image':f'images/{sid}.jpg','image_sha256':sha(src),
            'annotation':f'labels/{p.name}','annotation_sha256':sha(p),
            'overlay':f'overlays/{sid}.jpg','overlay_sha256':sha(out/'overlays'/f'{sid}.jpg'),
            'first_pass_reviewer':label['reviewer'],'first_pass_reviewer_type':'AI',
            'human_signoff':False,'complete_image_annotation':label['complete_image_annotation'],
            'eligible_for_yolo_export':False,'label_version':label['label_version'],'evidence':evidence})
        tasks.append({'candidate_id':sid,'image_sha256':sha(src),'reviewed_annotation_sha256':sha(p),
            'reviewer_id':None,'reviewer_type':None,'independent_from_first_pass':None,'reviewed_at':None,
            'actual_method':[],'full_original_checked':False,'omission_search_completed':False,
            'bounds_checked':False,'kind_checked':False,'attributes_checked':False,
            'decision':None,'findings':[],'corrected_annotation_file':None,
            'human_signoff':False,'training_approval':False})
    for name2 in ['side_candidates.png','gate_0000_0007.png']:
        p=R/'review_stage2/zooms'/name2
        if p.exists():shutil.copy2(p,out/'evidence'/name2)
    for p in ['标注规范.md','data/provisional_groups.json','data/near_duplicate_components.json',
              'reports/near_duplicate_review.json','reports/split_audit.json','review_stage2/visual_snapshot_0400.json']:
        shutil.copy2(R/p,out/'reference_only'/Path(p).name)
    manifest={'batch_id':out.name,'created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'purpose':'Independent second pass of frozen AI first-pass drafts; NOT gold training labels',
        'count':len(entries),'class_order':['motor_vehicle_body','pedestrian_body'],
        'independent_review_completed':False,'human_confirmations_completed':0,
        'entries':entries,'arbitration_required':[
            'Unknown/ambiguous side and far signals must not become background in standard YOLO.',
            'Integrated countdown belongs to common housing only; never make a number an independent traffic light.',
            'Unknown color when only a number is illuminated; no inferred off/color/arrow.',
            'No first-pass AI decision qualifies as human signoff or independent second pass.']}
    save(out/'manifest.json',manifest)
    (out/'review_fillback.jsonl').write_text('\n'.join(json.dumps(t,ensure_ascii=False) for t in tasks)+'\n',encoding='utf-8')
    save(out/'difficult_cases.json',[{'candidate_id':e['candidate_id'],
        'issues':json.loads((out/e['annotation']).read_text(encoding='utf-8')).get('arbitration',[])} for e in entries])
    if write_readme: (out/'README.md').write_text('''# 冻结 AI 初审批次；尚非合格真值

先独立查看 images/ 原图，搜索全部灯体与漏标，再核 labels/ 与 overlays/。绿色body、黄色emitter、紫色ignore、橙色hard_negative。可使用 evidence/ 的原像素/最近邻放大；插值不能增加信息。

`manifest.json` 绑定原图、修订标签和带框图的 SHA256。`review_fillback.jsonl` 是空第二轮回填入口；请另存为新文件，填写真实 reviewer_id、AI/human、实际方法、时间、逐项检查及异议。不得修改冻结标签后仍签旧 SHA。对修框另存新标签，写 corrected_annotation_file；PC 仲裁后产生新版本。

第一轮全部由 Codex PC AI 完成，未有人类签署。所有标签 complete_image_annotation=false，主要因侧/远信号的 kind/外壳不确定；32 张不能直接导出训练，不能把 ignore 当背景。第二轮 AI 复审也不能冒充原规范的人类确认。提出排除的图仍需记录第二轮结论，不是纯负图。

类别0 motor_vehicle_body：有可见信号形态依据的机动车灯壳；类别1 pedestrian_body：可辨行人信号形态的灯壳。非机动车/未知不偷偷并入这两类。共壳一框，分壳分框；支架、外置计时器、LED文字和发光光晕不包入body。灯色与箭头只在可辨时单列，不由源类别或位置推断。control_relation始终unknown。

人工待确认集中项：逐图漏标与kind；侧/背面三孔灯的适用类别；共壳内嵌数字定义；夜景只见发光时的body排除；未知region裁决；路口/连续场景与重复组；最终数据放行。人类签署目前为0。

reference_only/ 含规范、400张初筛记录、87对近重复核查与保守分组。两视觉route只是泄漏约束，未证实独立路口。正式split仍unassigned；四原片整片仅regression，不进train/val/INT8；独立外部测试缺失。

验证命令（在项目根运行）：`.venv-train/Scripts/python.exe scripts/validate_review_batch.py review_stage2/frozen/批次名`。验证文件完整性不等于通过视觉/人类审核。
''',encoding='utf-8')
    files={str(p.relative_to(out)).replace('\\','/'):sha(p) for p in out.rglob('*') if p.is_file()}
    save(out/'files_sha256.json',files)
    print(json.dumps({'batch':str(out),'count':len(entries),'manifest_sha256':sha(out/'manifest.json')},ensure_ascii=False))
if __name__=='__main__':main()
