"""Read-only precision diagnosis for the failed trained RKNN candidate."""
import copy
import json
import types
from datetime import datetime, timezone
import numpy as np
import torch
from ultralytics import YOLO
from export_trained_public_logits import ROOT, OUT, NAMES, sigmoid, raw_logits, sha


def errors(ref,actual):
    return {'raw_head_max_abs':max(float(np.abs(a.astype(float)-b.astype(float)).max()) for a,b in zip(ref,actual)),
        'cpu_sigmoid_score_max_abs':max(float(np.abs(sigmoid(ref[i])-sigmoid(actual[i])).max()) for i in (1,3,5))}


def main():
    report_path=ROOT/'reports/trained_fp16_diagnostic_r1.json'
    assert not report_path.exists()
    exp=json.loads((OUT/'export_validation.json').read_text('utf-8'))
    boardroot=ROOT/'board_validation/trained_logits_candidate_r1_20261025/remote_results'
    boardpath=boardroot/'reports/candidate_report.json';board=json.loads(boardpath.read_text('utf-8'))
    assert board['passed'] is False and board['onnx_sha256']==exp['onnx_sha256']
    checkpoint=ROOT/exp['checkpoint'];assert sha(checkpoint)==exp['checkpoint_sha256']
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction=False
    native=YOLO(str(checkpoint)).model.cpu().float().eval();native.fuse(verbose=False)
    native.model[-1].forward=types.MethodType(raw_logits,native.model[-1])
    gpu32=copy.deepcopy(native).cuda()
    gpu16=copy.deepcopy(native).cuda().half()
    # Isolate FP16 weight storage from FP16 feature/arithmetic propagation.
    rounded=copy.deepcopy(native).half().float().cuda()
    comparisons=[]
    for c in exp['comparisons']:
        name=c['fixture'];source=OUT/'fixtures'/f'{name}_rgb_u8.npy'
        assert sha(source)==c['input_sha256']
        rgb=np.load(source);inp=np.ascontiguousarray(rgb.transpose(2,0,1)[None],dtype=np.float32)/255
        with torch.inference_mode():
            x=torch.from_numpy(inp).cuda()
            p32=[v.cpu().numpy() for v in gpu32(x)]
            p16=[v.float().cpu().numpy() for v in gpu16(x.half())]
            weight16=[v.cpu().numpy() for v in rounded(x)]
        rawpath=OUT/'fixtures'/f'{name}_onnx_raw.npz';assert sha(rawpath)==c['raw_reference_sha256']
        onnx=[np.load(rawpath)[n] for n in NAMES]
        actualpath=next(boardroot.rglob(f'{name}_rknn_raw.npz'))
        bc=next(v for v in board['comparisons'] if v['fixture']==name)
        assert sha(actualpath)==bc['actual_npz_sha256']
        npu=[np.load(actualpath)[n] for n in NAMES]
        comparisons.append({'fixture':name,'gpu_FP32_vs_ONNX_FP32':errors(onnx,p32),
            'rounded_weight_FP32_vs_ONNX_FP32':errors(onnx,weight16),
            'GPU_FP16_vs_ONNX_FP32':errors(onnx,p16),
            'NPU_vs_ONNX_FP32':errors(onnx,npu),'NPU_vs_GPU_FP16':errors(p16,npu)})
    assert sha(checkpoint)==exp['checkpoint_sha256']
    maxima={k:{metric:max(v[k][metric] for v in comparisons) for metric in comparisons[0][k]}
        for k in comparisons[0] if k!='fixture'}
    result={'recorded_at':datetime.now(timezone.utc).isoformat(),'diagnostic_completed':True,
        'board_report':boardpath.relative_to(ROOT).as_posix(),'board_report_sha256':sha(boardpath),
        'checkpoint_sha256':exp['checkpoint_sha256'],'onnx_sha256':exp['onnx_sha256'],
        'optimizer_updates':0,'checkpoint_modified':False,'TF32_enabled':False,
        'FP16_reduced_precision_matmul_reduction_enabled':False,
        'fixture_count':len(comparisons),'no_new_or_reserved_test_inputs':True,
        'maxima':maxima,'comparisons':comparisons,
        'scope':'Precision-only diagnosis. Cannot approve a different threshold or prove recognition accuracy. GPU half is not RKNN hardware emulation.'}
    report_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(maxima,ensure_ascii=False))


if __name__=='__main__':main()
