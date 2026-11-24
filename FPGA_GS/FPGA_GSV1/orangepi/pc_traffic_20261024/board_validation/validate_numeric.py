"""Offline ONNX/actual NPU comparison for UNTRAINED raw-six-head export only.

No server, sockets, video upload, services, or production model modifications.
Thresholds below are fixed before running. They are numeric checks, not accuracy.
"""
import datetime
import hashlib
import json
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from rknnlite.api import RKNNLite

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
NAMES = ['box_s8', 'score_s8', 'box_s16', 'score_s16', 'box_s32', 'score_s32']
SHAPES = [(1,64,80,80),(1,2,80,80),(1,64,40,40),(1,2,40,40),(1,64,20,20),(1,2,20,20)]
LIMITS = {'box_raw_max_abs': .05, 'score_raw_max_abs': .001,
          'decoded_box_max_abs_input_px': .5, 'decoded_score_max_abs': .001,
          'paired_box_median_iou_min': .99}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def array_sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def letterbox(bgr):
    h,w = bgr.shape[:2]
    gain = min(640/w, 640/h)
    nw,nh = round(w*gain),round(h*gain)
    left,top = (640-nw)//2,(640-nh)//2
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    out = np.full((640,640,3),114,np.uint8)
    out[top:top+nh,left:left+nw] = cv2.resize(rgb,(nw,nh),interpolation=cv2.INTER_LINEAR)
    return out, {'original_wh':[w,h], 'resized_wh':[nw,nh], 'gain':gain,
                 'padding_ltrb':[left,top,640-nw-left,640-nh-top],
                 'inverse':'subtract left/top then divide by scalar gain; optional clip to original extent'}


def inverse(boxes, meta, clip=False):
    b = boxes.copy().astype(np.float64)
    b[:,[0,2]] = (b[:,[0,2]]-meta['padding_ltrb'][0])/meta['gain']
    b[:,[1,3]] = (b[:,[1,3]]-meta['padding_ltrb'][1])/meta['gain']
    if clip:
        b[:,[0,2]] = b[:,[0,2]].clip(0,meta['original_wh'][0])
        b[:,[1,3]] = b[:,[1,3]].clip(0,meta['original_wh'][1])
    return b


def decode(outputs):
    boxes,scores = [],[]
    for level,stride in enumerate((8,16,32)):
        raw,score = outputs[level*2:level*2+2]
        _,_,h,w = raw.shape
        logits = raw.astype(np.float64).reshape(4,16,h,w)
        p = np.exp(logits-logits.max(axis=1,keepdims=True))
        p /= p.sum(axis=1,keepdims=True)
        d = (p*np.arange(16,dtype=np.float64)[None,:,None,None]).sum(axis=1)
        yy,xx = np.mgrid[:h,:w]
        x,y = xx+.5,yy+.5
        box = np.stack((x-d[0],y-d[1],x+d[2],y+d[3]),axis=-1).reshape(-1,4)*stride
        boxes.append(box)
        scores.append(score[0].reshape(2,-1).T)
    return np.concatenate(boxes), np.concatenate(scores)


def nms(boxes, scores, threshold=.25, iou_threshold=.45):
    # Multi-label, class-aware, stable tie ordering; outputs already sigmoid.
    selected = []
    for cls in range(2):
        ix = np.flatnonzero(scores[:,cls]>=threshold)
        ix = ix[np.argsort(-scores[ix,cls],kind='stable')]
        while len(ix):
            a = int(ix[0]); selected.append((a,cls,float(scores[a,cls])))
            if len(ix)==1: break
            tail = ix[1:]
            lt = np.maximum(boxes[a,:2],boxes[tail,:2])
            rb = np.minimum(boxes[a,2:],boxes[tail,2:])
            inter = np.maximum(0,rb-lt).prod(axis=1)
            area_a = np.maximum(0,boxes[a,2:]-boxes[a,:2]).prod()
            area_b = np.maximum(0,boxes[tail,2:]-boxes[tail,:2]).prod(axis=1)
            iou = inter/np.maximum(area_a+area_b-inter,1e-12)
            ix = tail[iou<=iou_threshold]
    return selected


def ious(a,b):
    inter = np.maximum(0,np.minimum(a[:,2:],b[:,2:])-np.maximum(a[:,:2],b[:,:2])).prod(axis=1)
    area = np.maximum(0,a[:,2:]-a[:,:2]).prod(axis=1)+np.maximum(0,b[:,2:]-b[:,:2]).prod(axis=1)
    return inter/np.maximum(area-inter,1e-12)


def implementation_checks():
    uniform = [np.zeros(s,np.float32) for s in SHAPES]
    b,s = decode(uniform)
    # Uniform logits: distance exactly mean(0..15)=7.5; anchor first cell=(.5,.5).
    assert np.array_equal(b[0],[-56,-56,64,64])
    assert np.array_equal(b[6400],[-112,-112,128,128])
    assert np.array_equal(b[8000],[-224,-224,256,256])
    assert s.shape==(8400,2) and not s.any()
    selected = nms(np.array([[0,0,10,10],[1,1,11,11],[0,0,10,10]],float),
                   np.array([[.9,0],[.8,0],[0,.85]],float))
    assert [(a,c) for a,c,_ in selected]==[(0,0),(2,1)]
    checks = []
    for h,w in [(720,1280),(719,1280),(301,101),(271,491)]:
        a = np.zeros((h,w,3),np.uint8); a[:] = [11,67,239]
        image,m = letterbox(a); l,t,r,bottom = m['padding_ltrb']; nw,nh=m['resized_wh']
        assert np.array_equal(image[t,l],[239,67,11]) # explicit BGR->RGB check
        mask = np.ones((640,640),bool); mask[t:t+nh,l:l+nw]=False
        assert np.all(image[mask]==114)
        edge = np.array([[0,0,w,h],[w*.2,h*.1,w*.8,h*.9]],float)
        projected=edge*m['gain']+np.array([l,t,l,t])
        error=float(np.abs(inverse(projected,m)-edge).max())
        assert error<1e-9
        # Rounded resize edge may differ from ideal continuous transform by <=0.5 model pixel.
        resize_error=max(abs(nw-w*m['gain']),abs(nh-h*m['gain']))
        assert resize_error<=.5+1e-9
        checks.append({'shape_hw':[h,w],**m,'roundtrip_error_original_px':error,
                       'rounded_resize_edge_error_model_px':resize_error,'rgb_and_padding_checked':True})
    return {'uniform_dfl_and_grid':True,'nms_class_separation_and_overlap':True,'geometry':checks}


def main():
    cv2.setNumThreads(1)
    processes = subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout
    conflicts=[line for line in processes.splitlines() if 'python' in line and
               any(token in line for token in ('m406/demo','m405r2/demo','main.py --mode LIVE'))]
    if conflicts:
        raise RuntimeError('Demo running; decline contention instead of stopping it: '+str(conflicts))
    model=HERE/'artifacts/yolov8n_2class_640_UNTRAINED_raw6_rknn_preflight.onnx'
    rknn_path=model.with_suffix('.rknn')
    assert sha(model)=='5cb102190d135e7019f8ced291d853121b060de5995f0943da58611ee0898201'
    report={'time':datetime.datetime.now().astimezone().isoformat(),'untrained':True,
            'scope':'Numeric deployment preflight only; no detection accuracy or service integration claim',
            'thresholds_fixed_before_execution':LIMITS,'implementation_checks':implementation_checks(),
            'onnx_sha256':sha(model),'rknn_sha256':sha(rknn_path),
            'preprocess':{'ONNX':'RGB float32 NCHW /255 once','RKNN':'RGB uint8 NHWC; embedded mean0/std255',
                          'resize':'cv2.INTER_LINEAR; Python round; centered floor left/top, remainder right/bottom',
                          'fill':114},
            'output_order':[{'name':n,'shape':list(s)} for n,s in zip(NAMES,SHAPES)],
            'class_order':{'0':'motor_vehicle_body','1':'pedestrian_body'},
            'class_order_status':'External two-class training contract; random weights have no learned semantic meaning',
            'processes_before':processes,'comparisons':[]}
    options=ort.SessionOptions(); options.intra_op_num_threads=2; options.inter_op_num_threads=1
    session=ort.InferenceSession(str(model),options,providers=['CPUExecutionProvider'])
    assert [o.name for o in session.get_outputs()]==NAMES
    lite=RKNNLite(verbose=True)
    fixtures=[]
    for color in ['RED','GREEN']:
        source=ROOT/'m406/evidence/exact_source'/f'{color}_raw.jpg'
        image=cv2.imread(str(source)); assert image is not None
        h,w=image.shape[:2]
        for mode in ['full','left_half']:
            roi=[0,0,w,h] if mode=='full' else [0,int(.12*h),int(.55*w),int(.66*h)]
            x1,y1,x2,y2=roi
            fixtures.append((f'{color}_{mode}',image[y1:y2,x1:x2],{'source':str(source),'source_sha256':sha(source),'source_roi_xyxy':roi}))
    yy,xx=np.mgrid[:301,:503]
    pattern=np.stack(((xx*3+yy)%256,(yy*7+31)%256,(xx+yy*11+83)%256),axis=-1).astype(np.uint8)
    fixtures.append(('SYNTHETIC_channel_ramp_odd_padding',pattern,{'source':'synthetic numeric fixture, not visual evidence'}))
    try:
        assert lite.load_rknn(str(rknn_path))==0
        assert lite.init_runtime(core_mask=RKNNLite.NPU_CORE_0)==0
        report['runtime_initialized']=True
        for name,image,provenance in fixtures:
            rgb,meta=letterbox(image)
            np.save(HERE/'fixtures'/f'{name}_rgb_u8.npy',rgb,allow_pickle=False)
            inp=np.ascontiguousarray(rgb.transpose(2,0,1)[None],dtype=np.float32)/np.float32(255)
            t=time.perf_counter(); reference=session.run(NAMES,{'images':inp}); cpu_ms=(time.perf_counter()-t)*1000
            t=time.perf_counter(); actual=lite.inference(inputs=[rgb[None]],data_format=['nhwc']); npu_ms=(time.perf_counter()-t)*1000
            assert len(actual)==6
            for index,shape in enumerate(SHAPES):
                assert tuple(actual[index].shape)==shape,(index,actual[index].shape,shape)
                assert np.isfinite(actual[index]).all()
            np.savez_compressed(HERE/'fixtures'/f'{name}_onnx_outputs.npz',**dict(zip(NAMES,reference)))
            np.savez_compressed(HERE/'fixtures'/f'{name}_rknn_outputs.npz',**dict(zip(NAMES,actual)))
            heads=[]
            for i,(a,b) in enumerate(zip(reference,actual)):
                delta=np.abs(a.astype(np.float64)-b)
                limit=LIMITS['score_raw_max_abs' if i%2 else 'box_raw_max_abs']
                heads.append({'name':NAMES[i],'actual_shape':list(b.shape),'actual_dtype':str(b.dtype),
                              'reference_range':[float(a.min()),float(a.max())],
                              'actual_range':[float(b.min()),float(b.max())],
                              'max_abs':float(delta.max()),'p99_abs':float(np.percentile(delta,99)),
                              'mean_abs':float(delta.mean()),'rmse':float(np.sqrt((delta**2).mean())),
                              'passed':bool(delta.max()<=limit)})
            rb,rs=decode(reference); ab,ass=decode(actual)
            box_error=float(np.abs(rb-ab).max()); score_error=float(np.abs(rs-ass).max())
            pair_iou=ious(rb,ab)
            decoded={'all_anchor_count':len(rb),'box_max_abs_input_px':box_error,
                     'score_max_abs':score_error,'paired_iou_min':float(pair_iou.min()),
                     'paired_iou_median':float(np.median(pair_iou)),
                     'box_max_abs_original_px_unclipped':float(np.abs(inverse(rb,meta)-inverse(ab,meta)).max()),
                     'box_max_abs_original_px_clipped':float(np.abs(inverse(rb,meta,True)-inverse(ab,meta,True)).max()),
                     'threshold_025_nms_counts':[len(nms(rb,rs)),len(nms(ab,ass))],
                     'passed':bool(box_error<=LIMITS['decoded_box_max_abs_input_px'] and
                                   score_error<=LIMITS['decoded_score_max_abs'] and
                                   np.median(pair_iou)>=LIMITS['paired_box_median_iou_min'])}
            # Independent selected-cell scalar DFL calculation catches channel/grid ordering mistakes.
            scalar_error=0.
            for level,stride in enumerate((8,16,32)):
                logits=actual[2*level]; h,w=logits.shape[2:]
                base=[0,6400,8000][level]
                for y,x in [(0,0),(h//2,w//2),(h-1,w-1)]:
                    d=[]
                    for side in range(4):
                        v=logits[0,side*16:(side+1)*16,y,x].astype(np.float64)
                        p=np.exp(v-v.max());d.append(float(sum(j*p[j] for j in range(16))/p.sum()))
                    expected=np.array([x+.5-d[0],y+.5-d[1],x+.5+d[2],y+.5+d[3]])*stride
                    scalar_error=max(scalar_error,float(np.abs(ab[base+y*w+x]-expected).max()))
            assert scalar_error<1e-9
            entry={'fixture':name,**provenance,'input_rgb_u8_sha256':array_sha(rgb),
                   'letterbox':meta,'heads':heads,'decoded':decoded,'scalar_decode_max_error':scalar_error,
                   'onnx_ms_single_observation':cpu_ms,'npu_ms_single_observation':npu_ms,
                   'passed':all(v['passed'] for v in heads) and decoded['passed']}
            report['comparisons'].append(entry)
            print(json.dumps(entry),flush=True)
    finally:
        lite.release()
    report['passed']=all(c['passed'] for c in report['comparisons']) and len(report['comparisons'])==5
    report['limitations']=[
        'Untrained head is near-constant and low-score; numeric agreement does not validate trained recognition.',
        'All 8400 unthresholded boxes and scores compared; empty post-NMS output is not used as a pass criterion.',
        'Single bounded NPU runs, not production throughput, accuracy, or multi-model contention benchmark.',
        'Trained model must repeat RGB/normalization, per-head, decoded/NMS and semantic-class checks.'
    ]
    (HERE/'reports/numeric_validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed':report['passed'],'report':str(HERE/'reports/numeric_validation.json')}),flush=True)


if __name__=='__main__':
    main()
