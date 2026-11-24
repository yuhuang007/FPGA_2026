"""Summarize this independent experiment without changing original reports."""
import datetime
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
TASK=HERE.parents[1]


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def main():
    result=read(HERE/'reports/candidate_validation.json');probe=read(HERE/'reports/logits_probe.json')
    pc=read(HERE/'reports/pc_crosscheck.json');old=read(HERE/'reports/original_preservation.json')
    baseline=read(HERE/'protected_before.json')
    assert all(sha(Path(path))==value for path,value in baseline.items())
    first_pass=TASK/'review_stage2/first_pass'
    labels=[p for p in first_pass.rglob('*') if p.is_file()]
    manifests=[p for p in (TASK/'review_stage2').rglob('*.json') if any(x in p.name.lower() for x in ('manifest','frozen'))]
    review={'recorded_at':datetime.datetime.now().astimezone().isoformat(),
            'reviewer':'AI / Codex independent board-validation reviewer','human_signature':False,
            'completed_frozen_revised_label_reviews':0,'approved_revised_labels':0,
            'previous_8_candidate_prechecks_counted_as_formal_review':False,
            'first_pass_file_count':len(labels),'frozen_manifest_count':len(manifests),
            'observed_first_pass_files':[str(p.relative_to(TASK)) for p in labels],
            'observed_frozen_manifests':[str(p.relative_to(TASK)) for p in manifests],
            'status':'awaiting first immutable revised-label batch; do not promote source XML or visual notes to approved review',
            'new_grouping_materials_observed':[str(p.relative_to(TASK)) for p in (
                TASK/'data/provisional_groups.json',TASK/'data/near_duplicate_components.json',
                TASK/'reports/near_duplicate_review.json') if p.exists()],
            'required_for_batch':['original-image ID/SHA mapping','revised annotations and frozen version/SHA',
                                  'initial reviewer identity/method/timestamp and change notes',
                                  'near-duplicate/group mapping and unresolved arbitration items'],
            'PC_initial_records_modified':False}
    write(HERE/'reports/independent_review_progress.json',review)
    summary={'recorded_at':datetime.datetime.now().astimezone().isoformat(),
             'scope':'One random-weight logits-output candidate. No trained recognition release.',
             'candidate_numeric_passed':result['passed'] and probe['passed'] and pc['passed'],
             'original_probability_model_strict_numeric_status':'failed, retained unchanged',
             'original_model_and_reports_preserved':old['passed'] and pc['original_PC_model_and_report_preserved'],
             'onnx_sha256':result['build']['onnx_sha256'],'rknn_sha256':result['build']['rknn_sha256'],
             'score_activation':'cpu_stable_sigmoid_once','score_absolute_error_limit':.001,
             'score_limit_relaxed':False,'score_clipping_used':False,
             'export_contract_path':str(HERE/'reports/export_contract.json'),
             'micrograph':{'passed':probe['passed'],'score_error':probe['aggregate_score_error'],
                           'score_buckets':probe['aggregate_score_buckets'],
                           'report_path':str(HERE/'reports/logits_probe.json')},
             'full_candidate':{'passed':result['passed'],'input_count':5,
                               'raw_box_error':result['aggregate_box_raw_error'],
                               'raw_class_logits_error':result['aggregate_class_logits_error'],
                               'cpu_score_error':result['aggregate_cpu_score_error'],
                               'score_buckets':result['aggregate_score_buckets'],
                               'maximum_decoded_coordinate_error_input_px':max(r['decoded_box_error_input_px']['max_abs'] for r in result['comparisons']),
                               'NMS_comparison_passed':all(r['nms']['anchor_and_class_ids_equal'] for r in result['comparisons']),
                               'nonempty_NMS_and_single_sigmoid_fixture_passed':pc['postprocessing_fixture']['single_sigmoid_guard_passed'],
                               'failed_inputs':result['failed_inputs'],
                               'all_inputs_and_outputs_retained':True,
                               'report_path':str(HERE/'reports/candidate_validation.json')},
             'environment':{'toolkit2':'2.3.2','lite_api':'2.5.0','runtime':'2.3.0 (c949ad889d)','driver':'0.9.8',
                            'backend':'actual RK3588 NPU core0, CPU stable sigmoid/DFL/NMS',
                            'upgraded_or_reinstalled':False},
             'model_path':str(HERE/'artifacts/yolov8n_2class_640_UNTRAINED_raw6_logits_candidate.rknn'),
             'remote_directory':'/home/orangepi/fpga_gs_m401_v0_1_2_20261021/traffic_logits_candidate_20261024_r1',
             'full_log_path':str(HERE/'experiment.log'),
             'review_progress_path':str(HERE/'reports/independent_review_progress.json'),
             'completed_frozen_revised_label_reviews':0,
             'services_stopped_or_started':False,'m406_or_launcher_modified':False,
             'FPGA_live_or_business_udp_used':False,
             'limitations':result['limitations']}
    write(HERE/'reports/experiment_summary.json',summary)
    files=[p for p in HERE.rglob('*') if p.is_file() and p.name!='evidence.sha256']
    (HERE/'evidence.sha256').write_text('\n'.join(sha(p)+'  '+p.relative_to(HERE).as_posix() for p in sorted(files))+'\n',encoding='utf-8')
    print(json.dumps({'candidate_numeric_passed':summary['candidate_numeric_passed'],
                      'original_preserved':summary['original_model_and_reports_preserved'],
                      'formal_label_reviews':0,'first_pass_files':len(labels),
                      'frozen_manifests':len(manifests),'evidence_files':len(files)},indent=2))


if __name__=='__main__':main()
