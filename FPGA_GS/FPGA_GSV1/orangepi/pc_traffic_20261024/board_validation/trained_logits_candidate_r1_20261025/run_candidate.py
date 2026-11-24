"""Isolated trained-weight build/numeric check. Never manages demo services."""
import datetime
import hashlib
import importlib.metadata as md
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXPECTED = 'ed944ebfeab6574b17577a57306e0017d751d992b5ad865723b1d5986c67ece2'
LIMITS = dict(raw_head_max_abs=.05, cpu_activated_score_max_abs=.001,
              decoded_box_max_abs_input_px=.5, paired_iou_median_min=.99)
NAMES = ['box_s8', 'class_logits_s8', 'box_s16', 'class_logits_s16', 'box_s32', 'class_logits_s32']
SHAPES = [(1,64,80,80),(1,2,80,80),(1,64,40,40),(1,2,40,40),(1,64,20,20),(1,2,20,20)]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(name, value):
    (HERE/'reports'/name).write_text(json.dumps(value, indent=2)+'\n')


def processes():
    return subprocess.run(['ps','-eo','pid,ppid,etime,args'], capture_output=True, text=True).stdout


def idle():
    ps = processes()
    conflicts = [x for x in ps.splitlines() if 'python' in x and
                 any(s in x for s in ('m406/demo', 'm405r2/demo', '--mode LIVE_FRONT', '--mode FILE_TEST'))]
    if conflicts:
        raise RuntimeError('Resource conflict; original service left untouched: '+str(conflicts))
    return ps


def protected():
    result = {}
    for folder in ('m406','traffic_logits_candidate_20261024_r1','traffic_preflight_20261024_r1'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.json','.onnx','.rknn'):
                result[str(p.relative_to(ROOT))] = sha(p)
    result['/usr/lib/librknnrt.so'] = sha('/usr/lib/librknnrt.so')
    return result


def sigmoid(x):
    x = np.asarray(x, dtype=np.float64)
    y = np.empty_like(x); pos = x >= 0
    y[pos] = 1/(1+np.exp(-x[pos]))
    z = np.exp(x[~pos]); y[~pos] = z/(1+z)
    return y


def decode(heads):
    boxes, scores = [], []
    for i, stride in enumerate((8,16,32)):
        raw, cls = heads[2*i:2*i+2]; h,w = raw.shape[2:]
        z = raw.astype(np.float64).reshape(4,16,h,w)
        p = np.exp(z-z.max(axis=1,keepdims=True)); p /= p.sum(axis=1,keepdims=True)
        d = (p*np.arange(16)[None,:,None,None]).sum(axis=1)
        yy,xx = np.mgrid[:h,:w]; x,y = xx+.5,yy+.5
        boxes.append(np.stack((x-d[0],y-d[1],x+d[2],y+d[3]),axis=-1).reshape(-1,4)*stride)
        # Raw classification logits: exactly one activation, no clipping/calibration.
        scores.append(sigmoid(cls)[0].reshape(2,-1).T)
    return np.concatenate(boxes), np.concatenate(scores)


def iou(a,b):
    inter = np.maximum(0,np.minimum(a[...,2:],b[...,2:])-np.maximum(a[...,:2],b[...,:2])).prod(axis=-1)
    aa = np.maximum(0,a[...,2:]-a[...,:2]).prod(axis=-1)
    bb = np.maximum(0,b[...,2:]-b[...,:2]).prod(axis=-1)
    return inter/np.maximum(aa+bb-inter,1e-12)


def nms(boxes,scores):
    found=[]
    for c in range(2):
        ids=np.flatnonzero(scores[:,c]>=.25)
        ids=ids[np.argsort(-scores[ids,c],kind='stable')]
        while len(ids):
            k=int(ids[0]); found.append((k,c,float(scores[k,c])))
            ids=ids[1:]
            if len(ids): ids=ids[iou(boxes[k],boxes[ids])<=.45]
    return found


def metrics(a,b):
    delta=np.abs(np.asarray(a,dtype=np.float64)-b).ravel()
    if not len(delta):return dict(count=0,status='not_covered')
    return dict(count=len(delta),max_abs=float(delta.max()),mean_abs=float(delta.mean()),
                rmse=float(np.sqrt((delta**2).mean())),
                **{f'p{p}_abs':float(np.percentile(delta,p)) for p in (50,95,99,99.9)})


def buckets(a,b):
    return {name:metrics(a[mask],b[mask]) for name,mask in
            [('low_lt_0.01',a<.01),('middle_0.01_to_0.99',(a>=.01)&(a<=.99)),('high_gt_0.99',a>.99)]}


def checks():
    h=[np.zeros(s,np.float32) for s in SHAPES]; b,s=decode(h)
    assert np.array_equal(b[0],[-56,-56,64,64]) and np.all(s==.5)
    assert np.array_equal(b[6400],[-112,-112,128,128])
    assert np.array_equal(b[8000],[-224,-224,256,256])
    assert np.isfinite(sigmoid(np.array([-1000,1000]))).all()
    bs=np.array([[0,0,10,10],[1,1,11,11],[0,0,10,10]],float)
    ss=np.array([[.9,0],[.8,0],[0,.85]])
    assert [(i,c) for i,c,_ in nms(bs,ss)]==[(0,0),(2,1)]
    # A second sigmoid incorrectly turns low scores into >=.5 candidates.
    assert len(nms(bs,np.full((3,2),.001)))==0
    assert len(nms(bs,sigmoid(np.full((3,2),.001))))>0
    return dict(uniform_DFL_grid=True,class_aware_NMS=True,sigmoid_once_guard=True,
                second_sigmoid_negative_control=True,stable_extreme_logits=True)


def main():
    (HERE/'reports').mkdir(exist_ok=True); (HERE/'actual').mkdir(exist_ok=True)
    export=json.loads((HERE/'inputs/export_validation.json').read_text())
    model=HERE/'inputs/yolov8n_body2_640_trained_raw6_logits.onnx'
    target=HERE/'trained_raw6_logits_fp16.rknn'
    report=dict(recorded_at=datetime.datetime.now().astimezone().isoformat(),
                passed=False,trained=True,scope='Isolated trained numerical candidate, not recognition accuracy',
                onnx_sha256=sha(model),checkpoint_sha256=export['checkpoint_sha256'],
                thresholds_fixed_before_execution=LIMITS,score_activation='cpu_stable_sigmoid_once',
                class_names=['motor_vehicle_body','pedestrian_body'],output_names=NAMES,
                no_reserved_finaltest_inference=True,no_service_changes=True,
                comparisons=[],implementation_checks=checks())
    before=protected(); save('protected_before.json',before)
    report['environment']={'python':sys.version,'executable':sys.executable,
        'packages':{n:md.version(n) for n in ('rknn-toolkit2','rknn-toolkit-lite2','numpy','onnx','onnxruntime')},
        'driver':subprocess.run(['modinfo','rknpu'],capture_output=True,text=True).stdout,
        'runtime_sha256':sha('/usr/lib/librknnrt.so'),'processes_before':idle(),
        'listeners_before':subprocess.run(['ss','-lntup'],capture_output=True,text=True).stdout}
    save('environment.json',report['environment'])
    try:
        import onnx
        from rknn.api import RKNN
        from rknnlite.api import RKNNLite
        assert sha(model)==EXPECTED and len(export['comparisons'])==8
        graph=onnx.load(str(model)); assert [o.name for o in graph.graph.output]==NAMES
        assert all(next(n.op_type for n in graph.graph.node if o.name in n.output)=='Conv' for o in graph.graph.output)
        assert not target.exists(), 'Never overwrite an existing candidate'
        builder=RKNN(verbose=True); t=time.perf_counter(); codes={}
        try:
            codes['config']=builder.config(mean_values=[[0,0,0]],std_values=[[255,255,255]],target_platform='rk3588',optimization_level=3)
            assert codes['config']==0
            codes['load']=builder.load_onnx(model=str(model));assert codes['load']==0
            codes['build']=builder.build(do_quantization=False);assert codes['build']==0
            codes['export']=builder.export_rknn(str(target));assert codes['export']==0
        finally:builder.release()
        report['build']=dict(passed=True,codes=codes,seconds=time.perf_counter()-t,quantization=False,target='rk3588')
        report['rknn_sha256']=sha(target); save('candidate_report.json',report)
        idle(); lite=RKNNLite(verbose=True)
        try:
            assert lite.load_rknn(str(target))==0
            assert lite.init_runtime(core_mask=RKNNLite.NPU_CORE_0)==0
            report['runtime_initialized']=True
            for fixture in export['comparisons']:
                idle(); name=fixture['fixture']
                ip=HERE/'inputs/fixtures'/f'{name}_rgb_u8.npy'
                rp=HERE/'inputs/fixtures'/f'{name}_onnx_raw.npz'
                assert sha(ip)==fixture['input_sha256'] and sha(rp)==fixture['raw_reference_sha256']
                rgb=np.load(ip,allow_pickle=False);assert rgb.shape==(640,640,3) and rgb.dtype==np.uint8
                z=np.load(rp,allow_pickle=False); assert z.files==NAMES
                reference=[z[n] for n in NAMES]
                inp=np.ascontiguousarray(rgb[None])
                t=time.perf_counter(); actual=lite.inference(inputs=[inp],data_format=['nhwc']);ms=(time.perf_counter()-t)*1000
                assert len(actual)==6
                for i,v in enumerate(actual): assert v.shape==SHAPES[i] and np.isfinite(v).all()
                ap=HERE/'actual'/f'{name}_rknn_raw.npz';np.savez_compressed(ap,**dict(zip(NAMES,actual)))
                heads=[dict(name=n,shape=list(a.shape),dtype=str(a.dtype),reference_range=[float(r.min()),float(r.max())],
                            actual_range=[float(a.min()),float(a.max())],**metrics(r,a)) for n,r,a in zip(NAMES,reference,actual)]
                rb,rs=decode(reference);ab,ass=decode(actual)
                be=metrics(rb,ab);se=metrics(rs,ass);pi=iou(rb,ab)
                rn=nms(rb,rs);an=nms(ab,ass)
                rk={(k,c) for k,c,_ in rn};ak={(k,c) for k,c,_ in an};common=sorted(rk&ak)
                same_indices=sorted({k for k,c in common})
                paired_nms_iou=np.asarray([float(iou(rb[k],ab[k])) for k in same_indices])
                fail=[]
                if any(h['max_abs']>LIMITS['raw_head_max_abs'] for h in heads):fail.append('raw_head_max_abs')
                if se['max_abs']>LIMITS['cpu_activated_score_max_abs']:fail.append('cpu_activated_score_max_abs')
                if be['max_abs']>LIMITS['decoded_box_max_abs_input_px']:fail.append('decoded_box_max_abs_input_px')
                if np.median(pi)<LIMITS['paired_iou_median_min']:fail.append('paired_iou_median_min')
                decoded=dict(box_error_input_px=be,score_error=se,paired_iou_median=float(np.median(pi)),
                             paired_iou_min=float(pi.min()),score_error_buckets=buckets(rs,ass))
                if 'preprocess' in fixture:
                    meta=fixture['preprocess'];gain=meta['gain'];pad=meta['padding_ltrb']
                    decoded['box_error_original_px_unclipped']=metrics((rb-np.array([pad[0],pad[1],pad[0],pad[1]]))/gain,
                                                                     (ab-np.array([pad[0],pad[1],pad[0],pad[1]]))/gain)
                asym=float(np.max(np.abs(rs[:,0]-rs[:,1])))
                entry=dict(fixture=name,input_sha256=sha(ip),onnx_reference_sha256=sha(rp),actual_npz_sha256=sha(ap),
                           heads=heads,decoded=decoded,npu_ms_single_observation=ms,
                           trained_class_asymmetry={'max_score_difference_between_classes':asym,'not_identical':bool(asym>1e-6),
                               'onnx_per_class_max':rs.max(axis=0).tolist(),'rknn_per_class_max':ass.max(axis=0).tolist()},
                           NMS={'threshold':.25,'iou_threshold':.45,'onnx_count':len(rn),'rknn_count':len(an),
                                'onnx_per_class':[sum(c==j for k,c,p in rn) for j in range(2)],
                                'rknn_per_class':[sum(c==j for k,c,p in an) for j in range(2)],
                                'same_anchor_class_count':len(common),'reference_only':len(rk-ak),'actual_only':len(ak-rk),
                                'same_anchor_box_iou_median':float(np.median(paired_nms_iou)) if len(paired_nms_iou) else None},
                           passed=not fail,failed_checks=fail)
                report['comparisons'].append(entry);save('candidate_report.json',report)
                save(f'{name}_NMS.json',{'onnx':[dict(anchor=k,cls=c,score=p,box_input_xyxy=rb[k].tolist()) for k,c,p in rn],
                                         'rknn':[dict(anchor=k,cls=c,score=p,box_input_xyxy=ab[k].tolist()) for k,c,p in an]})
                print(json.dumps({'fixture':name,'passed':entry['passed'],'failed_checks':fail,'raw_max':max(h['max_abs'] for h in heads),
                                  'score_max':se['max_abs'],'box_max':be['max_abs'],'paired_iou_median':float(np.median(pi)),
                                  'NMS_counts':[len(rn),len(an)]}),flush=True)
        finally:lite.release()
        report['nonempty_trained_fixture_checked']=any(c['NMS']['onnx_count']>0 and c['NMS']['rknn_count']>0 for c in report['comparisons'])
        report['learned_asymmetric_outputs_checked']=all(c['trained_class_asymmetry']['not_identical'] for c in report['comparisons'])
        report['passed']=bool(len(report['comparisons'])==8 and all(c['passed'] for c in report['comparisons']) and
                              report['nonempty_trained_fixture_checked'] and report['learned_asymmetric_outputs_checked'])
    except Exception:
        report['exception']=traceback.format_exc();print(report['exception'],flush=True)
    finally:
        after=protected();save('protected_after.json',after)
        report['protected_files_unchanged']=before==after
        report['processes_after']=processes()
        report['limitations']=['FP16 trained-weight numerical candidate only; no new accuracy evaluation or production release.',
            'Exactly8 supplied fixtures:3 nonholdout real images plus5 old SC/synthetic development fixtures. No reserved finaltest or new Chinese pilot inference.',
            'Training960 to deployment640 accuracy/small-object equivalence is not established.',
            'Single NPU timing observations are not sustained preview fps or simultaneous demo-load performance.',
            'All8400 paired decoded anchors evaluated. NMS membership differences near thresholds are reported separately, not hidden.',
            'No parameter/threshold/version scanning, INT8, calibration, service/default/model replacement.']
        report['passed']=bool(report['passed'] and report['protected_files_unchanged'])
        save('candidate_report.json',report)
    print(json.dumps({'passed':report['passed'],'protected_files_unchanged':report['protected_files_unchanged'],
                      'rknn_sha256':report.get('rknn_sha256')}),flush=True)
    return 0 if report['passed'] else 2


if __name__=='__main__':
    sys.exit(main())
