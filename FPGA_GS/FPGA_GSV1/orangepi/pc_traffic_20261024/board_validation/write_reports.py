"""Publish only this task's build/numeric/independent-review evidence."""
import csv
import datetime
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'reports/board_preflight_r1'
REMOTE='/home/orangepi/fpga_gs_m401_v0_1_2_20261021/traffic_preflight_20261024_r1'


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def main():
    now=datetime.datetime.now().astimezone().isoformat()
    build=read(E/'build_result.json');env=read(E/'environment.json')
    numeric=read(E/'numeric_validation.json');pc=read(E/'pc_input_validation.json')
    initial=ROOT/'reports/rknn_preflight.json'
    backup=E/'rknn_preflight_before_this_task.json'
    if not backup.exists():backup.write_bytes(initial.read_bytes())
    expected=read(ROOT/'reports/deployment_preflight.json')['onnx_sha256']
    rknn=ROOT/'artifacts/yolov8n_2class_640_UNTRAINED_raw6_rknn_preflight.rknn'
    assert build['onnx_sha256']==expected=='5cb102190d135e7019f8ced291d853121b060de5995f0943da58611ee0898201'
    assert sha(rknn)==build['rknn_sha256']
    maximum_raw_box=max(h['max_abs'] for c in numeric['comparisons'] for h in c['heads'] if h['name'].startswith('box'))
    maximum_score=max(c['decoded']['score_max_abs'] for c in numeric['comparisons'])
    maximum_box=max(c['decoded']['box_max_abs_input_px'] for c in numeric['comparisons'])
    report={
        'passed':bool(build['passed'] and build['returncode']==0),
        'status':'same_sha_fp16_build_passed; board_execution_passed; strict_numeric_check_failed',
        'passed_scope':'Existing readiness contract: same-SHA config/load/build/export only; not numeric accuracy, data approval, CUDA readiness or training authorization',
        'recorded_at':now,'trained':False,'random_weights':True,
        'onnx_sha256':expected,'rknn_sha256':sha(rknn),
        'toolkit_version':env['packages']['rknn-toolkit2'],'lite_api_version':env['packages']['rknn-toolkit-lite2'],
        'runtime_version':'2.3.0 (c949ad889d@2024-11-07T11:35:33)',
        'driver_version':'0.9.8','runtime_sha256':env['system_runtime_sha256'],
        'environment_path':str(E/'environment.json'),
        'log_path':str(E/'build.log'),'remote_log_path':build['log_path'],
        'onnx_path':str(rknn.with_suffix('.onnx')),'rknn_path':str(rknn),
        'remote_directory':REMOTE,'remote_rknn_path':REMOTE+'/artifacts/'+rknn.name,
        'build':{**build,'model_precision_evidence':'Non-quantized build; verbose runtime/model tensor tables show FLOAT16 kernels and weights',
                 'config':'mean0/std255, rk3588, optimization_level3','calibration_used':False},
        'board_execution':{'passed':numeric['runtime_initialized'],'backend':'RKNNLite API / actual RK3588 NPU core0',
                           'fixed_inputs':5,'service_started_or_stopped':False,'business_ports_bound':False,
                           'log_path':str(E/'numeric_validation.log'),'fixture_directory':str(E/'fixtures'),
                           'performance_scope':'single-run timings only; no throughput benchmark'},
        'preprocessing_and_decoder':{
            'pc_independent_input_check_passed':pc['passed'],
            'pc_input_report':str(E/'pc_input_validation.json'),
            'input':numeric['preprocess'],'output_order':numeric['output_order'],
            'class_order':numeric['class_order'],
            'class_order_caveat':'ONNX has no class-name metadata. 0=motor_vehicle_body,1=pedestrian_body is external proposed training contract; untrained symmetric outputs cannot verify learned semantic order.',
            'decoder':'CPU softmax/DFL reg_max16, grid centers+0.5, strides8/16/32, scores already sigmoid, class-aware NMS',
            'geometry_and_decoder_unit_fixtures':numeric['implementation_checks']},
        'numeric_validation':{
            'passed':numeric['passed'],'status':'failed_fixed_0.001_score_absolute_error_limit',
            'report_path':str(E/'numeric_validation.json'),'thresholds':numeric['thresholds_fixed_before_execution'],
            'all_unthresholded_boxes_compared_per_input':8400,'six_raw_heads_compared':True,
            'maximum_raw_box_absolute_error':maximum_raw_box,
            'maximum_decoded_box_error_input_px':maximum_box,
            'maximum_decoded_score_absolute_error':maximum_score,
            'minimum_paired_median_iou':min(c['decoded']['paired_iou_median'] for c in numeric['comparisons']),
            'cause_evidence':'Independent Conv+Sigmoid micrograph reproduces low/high sigmoid saturation in this installed stack; do not attribute to RGB or DFL based on empty detections.',
            'sigmoid_probe_report':str(E/'sigmoid_probe.json'),
            'sigmoid_probe_log':str(E/'sigmoid_probe.log'),
            'threshold_changed_after_results':False,
            'not_accuracy_pass':True},
        'deployment':{'performed':False,'m406_modified':False,'launcher_default_modified':False,
                      'fpga_used':False,'live_or_udp_started':False,'system_or_dependencies_upgraded':False},
        'follow_up':['Repeat raw and decoded comparisons on actual trained weights and readable real lights before release.',
                     'If stricter sigmoid-tail fidelity is needed, evaluate documented compiler options or CPU sigmoid on a separately versioned logit-head export; current same-SHA model remains unchanged.',
                     'Do not change PC training gates or claim trained recognition improvement from this preflight.']}
    write(initial,report)
    rows=list(csv.DictReader((ROOT/'data/candidates.csv').open(encoding='utf-8-sig')))
    notes={
      0:{'omissions':'右侧约(1568,540)有独立小型亮灯候选，源XML未列；4倍最近邻裁剪后仍不能可靠辨认灯体类别/符号，交ignore或人工裁决，不直接补成机动车正例。',
         'bounds':'近灯源框基本围住竖直壳体；中间数字与圆灯同壳的body/倒计时排除边界需统一。远灯被树叶遮挡，源框包含亮区及叶片，不能当精确外壳真值。',
         'kind_and_attributes':'近处圆形绿灯可辨；远处及右侧小灯kind/箭头未知。数字不单独作为灯体。',
         'grouping':'与0096同一可见道路/摄像头构图，建议同场景组；不是仅按文件名推断。'},
      32:{'omissions':'原图全幅检查未确认其他清晰灯体；油罐车车顶高亮点是负样本候选，不作为信号灯。',
          'bounds':'两处竖直灯壳完整可见，源框基本贴合外壳，不能只截亮圆。',
          'kind_and_attributes':'两处圆绿灯可辨，支持机动车灯候选；控制关系仍unknown。',
          'grouping':'与0127的水印、卡车姿态、背景及两灯位置几乎相同，疑似重复压缩/重复取帧；RGB均差1.105/255，不能分到不同集合。'},
      64:{'omissions':'源XML只有左侧一个框；中间偏右约(670,530)还有独立红亮信号灯候选。4倍裁剪可见红亮形状但饱和，疑似行人图形，类别交裁决而非默认机动车。',
          'bounds':'左侧源框含上部枝叶遮挡和亮数字/信号部分；必须重新按可见物理壳体定义核边，不能直接沿用颜色框。',
          'kind_and_attributes':'亮红可见；箭头/行人类别需证据，数字不是红灯类别。遮挡/饱和分别标注。',
          'grouping':'未完成本图与全部候选的独立近重复核对。'},
      96:{'omissions':'右侧约(1568,540)仍有小型发光候选，源XML未覆盖；与0000一样需复查，不声明全图已穷尽。',
          'bounds':'近竖直壳体明确；远处源框只围亮形状，壳体被树叶遮挡，不宜作紧body框。',
          'kind_and_attributes':'近圆绿灯可辨；远绿形状不能可靠定箭头或类别。',
          'grouping':'与0000相同摄像头/场景但交通参与者不同，建议同场景组，不能当独立路口测试。'},
      127:{'omissions':'全幅未确认新增清晰灯体；车顶反光点不应误标。',
           'bounds':'两处壳体可见，源框与0032约差1～2像素，应统一body定义而非视为独立精度样本。',
           'kind_and_attributes':'两处圆绿可辨；无依据给出箭头或本车控制归属。',
           'grouping':'见0032：高置信近重复候选，保留同组且去重策略交PC。'},
      200:{'omissions':'原图左侧红箭头/圆绿灯及右侧绿灯组件未被三个源框完整覆盖；新增原图裁剪已保存。右下小绿亮区是否行人灯/数字仍不可辨。',
           'bounds':'wait_on框(951,111,1084,137)明显围LED文字，应作为硬负样本，不导出灯体；红/绿源框主要围发光区，夜间外壳边界不清，不等同紧body真值。',
           'kind_and_attributes':'红箭头及绿圆可见，但强眩光、雨夜和暗壳使灯体与方向细节不全；不能把文字或路面反射标为灯体。',
           'grouping':'仅核本图，未核对应连续雨夜片段的全体分组。'},
      300:{'omissions':'左侧远端约(820,445)还有一组红亮点，裁剪确认亮点存在但外壳/符号不足，需unknown/ignore裁决。',
           'bounds':'wait_on(960,402,1009,414)围的是LED文字，应移硬负；两个红框是发光孔/亮区，是否共用外壳需原尺寸/连续证据，不直接当两个body。',
           'kind_and_attributes':'红亮可见，原图尺寸不足以确定箭头；不得由道路位置或wait_on源类推断语义。',
           'grouping':'与雨夜200是否同一物理路口仅有相似布局，证据不足；不凭相似灯排确定同组或独立。'},
      399:{'omissions':'已全幅检查，右上横排灯体可见；车尾红灯和路牌为硬负，未确认其他清晰灯体。',
           'bounds':'横排源框基本围住远处暗壳/绿圆，较小；边界需像素级复核，不用放大插值补壳体。',
           'kind_and_attributes':'圆形绿亮区可辨，方向箭头不可确认；控制关系未知，kind按可见灯体证据复核。',
           'grouping':'未完成本图与其他候选的全局分组。'}
    }
    records=[]
    for index,note in notes.items():
        row=rows[index];image=ROOT/row['image_path'];xml=ROOT/row['source_xml']
        panel=ROOT/'review_stage2/panels'/f'{index:04d}.jpg'
        records.append({'index':index,'candidate_id':image.stem,'image_path':str(image),
                        'image_sha256':sha(image),'source_xml_path':str(xml),'source_xml_sha256':sha(xml),
                        'viewed_panel_path':str(panel),'viewed_panel_sha256':sha(panel),
                        'reviewer':'AI / Codex independent board-validation task','human_signoff':False,
                        'recorded_at':now,'actual_method':'Native 1920x1080 unmarked original rendered and visually inspected, then 1280x600 full-image/source-ROI panel; selected suspected omissions checked at 4x nearest-neighbor crop.',
                        'reviewed_label_version':'source XML only; revised first-pass label unavailable',
                        'stage':'independent_candidate_precheck_not_completed_second_label_review',
                        'decision':'return_findings_to_PC; no_training_approval','second_pass_completed':False,
                        'findings':note})
    review_out=ROOT/'reports/independent_review_r1'
    write(review_out/'candidate_precheck.json',records)
    first_pass=list((ROOT/'review_stage2/first_pass').glob('*'))
    first_pass=[p for p in first_pass if p.is_file()]
    snapshot=ROOT/'review_stage2/visual_decisions.json'
    try:visual_count=len(read(snapshot))
    except (FileNotFoundError,json.JSONDecodeError):visual_count=None
    status={'recorded_at':now,'reviewer':'AI / Codex; not human signoff',
            'candidate_count':len(rows),'independently_visually_prechecked_images':len(records),
            'completed_second_pass_label_reviews':0,'approved_for_training':0,
            'first_pass_label_files_at_check':len(first_pass),
            'partial_first_pass_visual_note_count_at_check':visual_count,
            'partial_visual_note_sha256':sha(snapshot) if snapshot.exists() else None,
            'status':'awaiting_versioned_first_pass_labels_and_grouping_evidence',
            'record_path':str(review_out/'candidate_precheck.json'),
            'required_materials':[
                'Versioned revised per-image body annotations, class/ignore/hard-negative regions and readable attributes; source XML alone is not first-pass completion.',
                'First-pass reviewer identity (AI explicitly allowed if declared), timestamp, actual full-image/zoom method, omissions and geometry changes for each submitted image.',
                'Manifest binding image SHA256, revised annotation SHA256 and candidate ID; fixed incremental batches are acceptable.',
                'Near-duplicate and same-site grouping table with visual evidence, uncertain links and proposed split boundaries; dHash proposals alone are not approved groups.',
                'PC arbitration mechanism/results for integrated countdown/body definition, ambiguous kind, glare and missing small lights.'
            ],
            'not_modified':['candidates.csv','annotations','review_stage2/first_pass','readiness.json',
                            'check_readiness.py','CUDA results','training gates'],
            'next_action':'On arrival of an immutable reviewed batch, inspect originals and revised labels independently per image; record disagreements and label version rather than copying initial approvals.'}
    write(ROOT/'reports/independent_review_status.json',status)
    print(json.dumps({'build_passed':report['passed'],'numeric_passed':numeric['passed'],
                      'max_score_error':maximum_score,'prechecked':len(records),
                      'second_pass_completed':0,'first_pass_label_files':len(first_pass)},indent=2))


if __name__=='__main__':main()
