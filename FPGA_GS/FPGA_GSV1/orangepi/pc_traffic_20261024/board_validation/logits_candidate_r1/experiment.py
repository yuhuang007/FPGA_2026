"""One isolated logits-head candidate, with immutable original evidence.

Run in the existing Linux Toolkit2 environment. No application/port management.
"""
import collections
import datetime
import hashlib
import importlib.util
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto as T, helper as h, numpy_helper as nh
from rknn.api import RKNN
from rknnlite.api import RKNNLite

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'traffic_preflight_20261024_r1'
EXPECTED='5cb102190d135e7019f8ced291d853121b060de5995f0943da58611ee0898201'
NAMES=['box_s8','class_logits_s8','box_s16','class_logits_s16','box_s32','class_logits_s32']
SHAPES=[(1,64,80,80),(1,2,80,80),(1,64,40,40),(1,2,40,40),(1,64,20,20),(1,2,20,20)]
LIMITS={'box_raw_max_abs':.05,'class_logits_raw_max_abs':.05,
        'cpu_activated_score_max_abs':.001,'decoded_box_max_abs_input_px':.5,
        'paired_box_median_iou_min':.99}
spec=importlib.util.spec_from_file_location('unchanged_previous_decoder',OLD/'scripts/validate_numeric.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,obj):
    (HERE/'reports'/name).write_text(json.dumps(obj,indent=2)+'\n')


def sigmoid(x):
    """One CPU activation on logits only, no clipping or score calibration."""
    x=np.asarray(x,dtype=np.float64)
    out=np.empty_like(x)
    positive=x>=0
    out[positive]=1/(1+np.exp(-x[positive]))
    expx=np.exp(x[~positive]);out[~positive]=expx/(1+expx)
    return out


def metrics(reference,actual):
    error=np.abs(np.asarray(reference,dtype=np.float64)-actual).ravel()
    if not len(error):return {'count':0,'status':'not_covered'}
    return {'count':len(error),'max_abs':float(error.max()),'mean_abs':float(error.mean()),
            'rmse':float(np.sqrt(np.mean(error**2))),
            **{f'p{q}_abs':float(np.percentile(error,q)) for q in (50,95,99,99.9)}}


def buckets(reference,actual):
    reference=np.asarray(reference).ravel();actual=np.asarray(actual).ravel()
    masks={'low_p_lt_0.01':reference<.01,
           'middle_0.01_to_0.99':(reference>=.01)&(reference<=.99),
           'high_p_gt_0.99':reference>.99}
    return {k:metrics(reference[mask],actual[mask]) for k,mask in masks.items()}


def ensure_idle():
    ps=subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout
    conflicts=[line for line in ps.splitlines() if 'python' in line and
               any(x in line for x in ('m406/demo','m405r2/demo','main.py --mode LIVE'))]
    if conflicts:raise RuntimeError('Refusing resource competition; original demo left untouched: '+str(conflicts))
    return ps


def build(source,target):
    assert not target.exists(),'Refuse to overwrite any previous candidate'
    model=RKNN(verbose=True)
    t=time.perf_counter()
    try:
        returns={'config':model.config(mean_values=[[0,0,0]],std_values=[[255,255,255]],
                                      target_platform='rk3588',optimization_level=3)}
        assert returns['config']==0
        returns['load']=model.load_onnx(model=str(source));assert returns['load']==0
        returns['build']=model.build(do_quantization=False);assert returns['build']==0
        returns['export']=model.export_rknn(str(target));assert returns['export']==0
    finally:model.release()
    return {'passed':True,'steps':returns,'seconds':time.perf_counter()-t,
            'onnx_sha256':sha(source),'rknn_sha256':sha(target),
            'quantization':False,'target':'rk3588'}


def session(path):
    opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
    return ort.InferenceSession(str(path),opts,providers=['CPUExecutionProvider'])


def probe():
    logits=np.array([-12,-10,-8,-7.848,-6.461,-6,-5.075,-4,-2,0,2,4,6,8,10,12],np.float32)
    weight=np.zeros((16,3,1,1),np.float32);weight[:,0,0,0]=.125
    graph=h.make_graph([h.make_node('Conv',['input','weight','bias'],['class_logits'],kernel_shape=[1,1])],
                       'logits_probe',[h.make_tensor_value_info('input',T.FLOAT,[1,3,8,8])],
                       [h.make_tensor_value_info('class_logits',T.FLOAT,[1,16,8,8])],
                       [nh.from_array(weight,'weight'),nh.from_array(logits,'bias')])
    model=h.make_model(graph,opset_imports=[h.make_opsetid('',12)]);model.ir_version=9
    source=HERE/'artifacts/DIAGNOSTIC_ONLY_logits_probe.onnx';target=source.with_suffix('.rknn')
    assert not source.exists();onnx.checker.check_model(model);onnx.save(model,source)
    build_result=build(source,target);cpu=session(source);ensure_idle()
    lite=RKNNLite(verbose=True);records=[];all_ref=[];all_actual=[]
    try:
        assert lite.load_rknn(str(target))==0;assert lite.init_runtime(core_mask=RKNNLite.NPU_CORE_0)==0
        for value in (0,127,255):
            u8=np.full((1,8,8,3),value,np.uint8)
            ref=cpu.run(None,{'input':u8.transpose(0,3,1,2).astype(np.float32)/255})[0]
            got=lite.inference(inputs=[u8],data_format=['nhwc'])[0]
            assert got.shape==ref.shape==(1,16,8,8)
            rp,gp=sigmoid(ref),sigmoid(got)
            all_ref.append(rp.ravel());all_actual.append(gp.ravel())
            np.savez_compressed(HERE/'fixtures'/f'probe_{value}.npz',input=u8,onnx_logits=ref,rknn_logits=got,
                                onnx_cpu_score=rp,rknn_cpu_score=gp)
            records.append({'input_rgb_value':value,'raw_logits':metrics(ref,got),'activated_score':metrics(rp,gp),
                            'score_buckets':buckets(rp,gp),
                            'per_channel':[{'onnx_logit':float(ref[0,c,0,0]),'npu_logit':float(got[0,c,0,0]),
                                            'onnx_cpu_score':float(rp[0,c,0,0]),'npu_cpu_score':float(gp[0,c,0,0])}
                                           for c in range(16)]})
    finally:lite.release()
    ref=np.concatenate(all_ref);actual=np.concatenate(all_actual)
    out={'scope':'Diagnostic micrograph only','build':build_result,'score_activation':'cpu_stable_sigmoid_once',
         'score_threshold_fixed':.001,'records':records,'aggregate_score_error':metrics(ref,actual),
         'aggregate_score_buckets':buckets(ref,actual),
         'passed':all(r['activated_score']['max_abs']<=.001 and r['raw_logits']['max_abs']<=.05 for r in records)}
    write('logits_probe.json',out)
    print(json.dumps({'probe_passed':out['passed'],'score_error':out['aggregate_score_error']}),flush=True)
    return out


def export_candidate(source):
    assert sha(source)==EXPECTED
    old=onnx.load(source);model=onnx.load(source)
    assert [o.name for o in model.graph.output]==['box_s8','score_s8','box_s16','score_s16','box_s32','score_s32']
    changes=[];rename={};removed=[]
    for i,stride in enumerate((8,16,32)):
        name=f'score_s{stride}'
        candidates=[n for n in model.graph.node if name in n.output]
        assert len(candidates)==1 and candidates[0].op_type=='Sigmoid'
        n=candidates[0];assert len(n.input)==1 and len(n.output)==1
        assert not any(name in other.input for other in model.graph.node)
        rename[n.input[0]]=f'class_logits_s{stride}'
        changes.append({'removed_sigmoid_node':n.name,'old_probability_output':name,
                        'classification_conv_tensor':n.input[0],'new_output':f'class_logits_s{stride}'})
        removed.append(n.name)
    nodes=[n for n in model.graph.node if n.name not in removed]
    for n in nodes:
        for j,v in enumerate(n.input):
            if v in rename:n.input[j]=rename[v]
        for j,v in enumerate(n.output):
            if v in rename:n.output[j]=rename[v]
    del model.graph.node[:];model.graph.node.extend(nodes)
    for j,output in enumerate(model.graph.output):
        if j%2:output.name=NAMES[j]
    for v in model.graph.value_info:
        if v.name in rename:v.name=rename[v.name]
    # Preserve every initializer exactly, every other node except explicit tensor renames.
    assert [v.SerializeToString() for v in old.graph.initializer]==[v.SerializeToString() for v in model.graph.initializer]
    for before,after in zip([n for n in old.graph.node if n.name not in removed],model.graph.node):
        normal=onnx.NodeProto();normal.CopyFrom(after)
        reverse={b:a for a,b in rename.items()}
        for field in (normal.input,normal.output):
            for j,value in enumerate(field):
                if value in reverse:field[j]=reverse[value]
        assert before.SerializeToString()==normal.SerializeToString(),before.name
    h.set_model_props(model,{'score_activation':'cpu_stable_sigmoid_once',
                            'class_order':'0=motor_vehicle_body;1=pedestrian_body;UNTRAINED',
                            'parent_onnx_sha256':EXPECTED})
    onnx.checker.check_model(model)
    target=HERE/'artifacts/yolov8n_2class_640_UNTRAINED_raw6_logits_candidate.onnx'
    assert not target.exists();onnx.save(model,target)
    contract={'parent_onnx_sha256':EXPECTED,'onnx_sha256':sha(target),'untrained':True,
              'score_activation':'cpu_stable_sigmoid_once','npu_classification_outputs':'raw logits; NOT probabilities',
              'outputs':[{'name':n,'shape':list(s),'role':'class_logits' if j%2 else 'box_dfl_logits'}
                         for j,(n,s) in enumerate(zip(NAMES,SHAPES))],
              'preprocess':'unchanged RGB NHWC uint8, embedded mean0/std255; centered letterbox114',
              'box_DFL_NMS':'reuse SHA-recorded previous decoder, reg_max16/strides8,16,32/class-aware NMS',
              'decoder_source_sha256':sha(OLD/'scripts/validate_numeric.py'),
              'changes':changes,'unchanged_initializer_count':len(model.graph.initializer),
              'unchanged_other_nodes_verified':True,
              'ops_before':dict(collections.Counter(n.op_type for n in old.graph.node)),
              'ops_after':dict(collections.Counter(n.op_type for n in model.graph.node)),
              'thresholds_fixed_before_execution':LIMITS}
    write('export_contract.json',contract)
    return target,contract


def activate(outputs):
    return [sigmoid(o) if j%2 else o for j,o in enumerate(outputs)]


def full_candidate(probe_result):
    source=OLD/'artifacts/yolov8n_2class_640_UNTRAINED_raw6_rknn_preflight.onnx'
    candidate,contract=export_candidate(source)
    build_result=build(candidate,candidate.with_suffix('.rknn'));write('build_result.json',build_result)
    cpu=session(candidate);parent=session(source)
    assert [o.name for o in cpu.get_outputs()]==NAMES
    fixtures=json.loads((OLD/'reports/numeric_validation.json').read_text())['comparisons']
    ensure_idle();lite=RKNNLite(verbose=True);records=[];scores_ref=[];scores_actual=[];raw_box=[];raw_logits=[]
    try:
        assert lite.load_rknn(str(candidate.with_suffix('.rknn')))==0
        assert lite.init_runtime(core_mask=RKNNLite.NPU_CORE_0)==0
        for fixture in fixtures:
            name=fixture['fixture'];path=OLD/'fixtures'/f'{name}_rgb_u8.npy';u8=np.load(path)
            assert previous.array_sha(u8)==fixture['input_rgb_u8_sha256']
            np.save(HERE/'fixtures'/f'{name}_rgb_u8.npy',u8,allow_pickle=False)
            inp=np.ascontiguousarray(u8.transpose(2,0,1)[None],dtype=np.float32)/255
            ref=cpu.run(NAMES,{'images':inp});parent_probability=parent.run(None,{'images':inp})
            t=time.perf_counter();got=lite.inference(inputs=[u8[None]],data_format=['nhwc']);ms=(time.perf_counter()-t)*1000
            assert len(got)==6
            for j,(a,b,shape) in enumerate(zip(ref,got,SHAPES)):
                assert a.shape==b.shape==shape,(j,a.shape,b.shape)
                assert np.isfinite(b).all()
            np.savez_compressed(HERE/'fixtures'/f'{name}_onnx_raw.npz',**dict(zip(NAMES,ref)))
            np.savez_compressed(HERE/'fixtures'/f'{name}_npu_raw.npz',**dict(zip(NAMES,got)))
            ref_active=activate(ref);got_active=activate(got)
            heads=[]
            for j,(a,b) in enumerate(zip(ref,got)):
                if j%2:raw_logits.append((a.ravel(),b.ravel()))
                else:raw_box.append((a.ravel(),b.ravel()))
                heads.append({'name':NAMES[j],'shape':list(b.shape),'dtype':str(b.dtype),
                              'reference_range':[float(a.min()),float(a.max())],
                              'actual_range':[float(b.min()),float(b.max())],
                              'raw_error':metrics(a,b),
                              'passed':metrics(a,b)['max_abs']<=LIMITS['class_logits_raw_max_abs' if j%2 else 'box_raw_max_abs']})
            box_ref,score_ref=previous.decode(ref_active);box_actual,score_actual=previous.decode(got_active)
            scores_ref.append(score_ref.ravel());scores_actual.append(score_actual.ravel())
            parent_boxes,parent_scores=previous.decode(parent_probability)
            box_error=metrics(box_ref,box_actual);score_error=metrics(score_ref,score_actual)
            overlaps=previous.ious(box_ref,box_actual)
            nr=previous.nms(box_ref,score_ref);na=previous.nms(box_actual,score_actual)
            # These likely contain no boxes. All pre-NMS tensors/8400 boxes remain the main evidence.
            nms_ids_equal=[(a,c) for a,c,_ in nr]==[(a,c) for a,c,_ in na]
            parent_equivalence={
                'box_raw_max_abs':max(metrics(ref[j],parent_probability[j])['max_abs'] for j in (0,2,4)),
                'cpu_score_vs_original_probability':metrics(parent_scores,score_ref)}
            record={'fixture':name,'input_sha256':fixture['input_rgb_u8_sha256'],'letterbox':fixture['letterbox'],
                    'heads':heads,'cpu_sigmoid_scores':score_error,'score_buckets':buckets(score_ref,score_actual),
                    'decoded_box_error_input_px':box_error,
                    'decoded_box_error_original_px':metrics(previous.inverse(box_ref,fixture['letterbox']),previous.inverse(box_actual,fixture['letterbox'])),
                    'paired_box_iou_min':float(overlaps.min()),'paired_box_iou_median':float(np.median(overlaps)),
                    'nms':{'threshold':.25,'iou_threshold':.45,'reference_count':len(nr),'actual_count':len(na),
                           'anchor_and_class_ids_equal':nms_ids_equal,'empty_outputs_not_pass_criterion':True},
                    'parent_onnx_equivalence':parent_equivalence,'npu_single_observation_ms':ms,
                    'passed':all(o['passed'] for o in heads) and score_error['max_abs']<=.001 and
                             box_error['max_abs']<=.5 and np.median(overlaps)>=.99 and nms_ids_equal and
                             parent_equivalence['box_raw_max_abs']<1e-5 and
                             parent_equivalence['cpu_score_vs_original_probability']['max_abs']<1e-5}
            # Retain activated outputs and decodes even when a check fails.
            np.savez_compressed(HERE/'fixtures'/f'{name}_decoded.npz',onnx_boxes=box_ref,npu_boxes=box_actual,
                                onnx_scores=score_ref,npu_scores=score_actual)
            records.append(record);print(json.dumps(record),flush=True)
    finally:lite.release()
    a=np.concatenate(scores_ref);b=np.concatenate(scores_actual)
    pair_metrics=lambda pairs:metrics(np.concatenate([x for x,y in pairs]),np.concatenate([y for x,y in pairs]))
    result={'time':datetime.datetime.now().astimezone().isoformat(),'contract':contract,'build':build_result,
            'probe_passed':probe_result['passed'],'board_execution_passed':len(records)==5,
            'passed':len(records)==5 and all(r['passed'] for r in records),'comparisons':records,
            'aggregate_box_raw_error':pair_metrics(raw_box),'aggregate_class_logits_error':pair_metrics(raw_logits),
            'aggregate_cpu_score_error':metrics(a,b),'aggregate_score_buckets':buckets(a,b),
            'failed_inputs':[r['fixture'] for r in records if not r['passed']],
            'fixture_directory':str(HERE/'fixtures'),
            'score_threshold_unchanged':.001,'score_clipping_or_calibration_used':False,
            'limitations':['Random weights only; no recognition or trained-weight approval.',
                           'Full random model has only low scores; middle/high score coverage is separate diagnostic micrograph evidence.',
                           'Untrained symmetric class heads cannot verify learned semantic class order.',
                           'No live/UDP, service/default model replacement, or system/runtime upgrades.']}
    write('candidate_validation.json',result)
    print(json.dumps({'candidate_passed':result['passed'],'onnx_sha256':build_result['onnx_sha256'],
                      'rknn_sha256':build_result['rknn_sha256'],'score_error':result['aggregate_cpu_score_error']}),flush=True)


def main():
    for directory in ('artifacts','reports','fixtures'):(HERE/directory).mkdir(exist_ok=True)
    protected={str(p):sha(p) for name in ('artifacts','reports') for p in (OLD/name).rglob('*') if p.is_file()}
    write('original_protected_before.json',protected)
    write('execution_context.json',{'time':datetime.datetime.now().astimezone().isoformat(),'processes':ensure_idle(),
                                   'ports':subprocess.run(['ss','-lntup'],capture_output=True,text=True).stdout,
                                   'thresholds':LIMITS})
    try:
        # Check numerical stability without clipping extremes to make the gate pass.
        assert np.isfinite(sigmoid(np.array([-1000.,0.,1000.]))).all()
        p=probe()
        if p['passed']:full_candidate(p)
        else:write('candidate_validation.json',{'passed':False,'status':'probe_failed; full candidate not attempted','probe':p})
    finally:
        after={str(p):sha(p) for name in ('artifacts','reports') for p in (OLD/name).rglob('*') if p.is_file()}
        write('original_preservation.json',{'passed':protected==after,'before':protected,'after':after})
        assert protected==after,'Original evidence changed unexpectedly'


if __name__=='__main__':main()
