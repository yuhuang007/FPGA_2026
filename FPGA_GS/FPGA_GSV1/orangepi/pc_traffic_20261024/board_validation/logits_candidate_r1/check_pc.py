"""PC reference cross-check and nonempty postprocessing fixture; no training."""
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort

HERE=Path(__file__).resolve().parent
TASK=HERE.parents[1]


def extract(path,names,namespace):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    definitions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in definitions}==set(names)
    exec(compile(ast.Module(body=definitions,type_ignores=[]),str(path),'exec'),namespace)


def main():
    result=json.loads((HERE/'reports/candidate_validation.json').read_text())
    names=[o['name'] for o in result['contract']['outputs']]
    model=HERE/'artifacts/yolov8n_2class_640_UNTRAINED_raw6_logits_candidate.onnx'
    assert hashlib.sha256(model.read_bytes()).hexdigest()==result['build']['onnx_sha256']
    namespace={'np':np}
    extract(HERE/'experiment.py',['sigmoid'],namespace)
    previous=TASK/'board_validation/validate_numeric.py'
    assert hashlib.sha256(previous.read_bytes()).hexdigest()==result['contract']['decoder_source_sha256']
    extract(previous,['nms'],namespace)
    # With exactly one sigmoid: low logit -2 stays below .25; a second sigmoid would incorrectly retain it.
    boxes=np.array([[0,0,100,100],[5,5,105,105],[0,0,100,100],[200,200,250,250]],float)
    logits=np.array([[2,-12],[1.5,-12],[-12,2],[-2,-12]],float)
    probs=namespace['sigmoid'](logits)
    selected=namespace['nms'](boxes,probs)
    ids=[(a,c) for a,c,_ in selected]
    assert ids==[(0,0),(2,1)],ids
    doubled=[(a,c) for a,c,_ in namespace['nms'](boxes,namespace['sigmoid'](probs))]
    assert doubled!=ids
    opts=ort.SessionOptions();opts.intra_op_num_threads=2
    session=ort.InferenceSession(str(model),opts,providers=['CPUExecutionProvider'])
    checks=[]
    for fixture in result['comparisons']:
        name=fixture['fixture'];u8=np.load(HERE/'fixtures'/f'{name}_rgb_u8.npy')
        assert hashlib.sha256(u8.tobytes()).hexdigest()==fixture['input_sha256']
        board=np.load(HERE/'fixtures'/f'{name}_onnx_raw.npz')
        ref=session.run(names,{'images':np.ascontiguousarray(u8.transpose(2,0,1)[None],dtype=np.float32)/255})
        raw=[{'name':n,'max_abs':float(np.abs(a-board[n]).max())} for n,a in zip(names,ref)]
        checks.append({'fixture':name,'heads':raw,'passed':max(c['max_abs'] for c in raw)<1e-5})
    preserved=json.loads((HERE/'protected_before.json').read_text())
    after={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in preserved}
    assert after==preserved
    out={'passed':all(c['passed'] for c in checks),'onnxruntime':ort.__version__,'numpy':np.__version__,
         'pc_vs_board_onnx':checks,
         'postprocessing_fixture':{'scope':'Synthetic nonempty CPU regression, not visual accuracy',
                                  'selected_anchor_class_ids':ids,'expected_anchor_class_ids':[(0,0),(2,1)],
                                  'single_sigmoid_guard_passed':True,'different_class_overlap_retained':True,
                                  'same_class_overlap_suppressed':True,'nms_threshold':.25,'iou_threshold':.45},
         'original_PC_model_and_report_preserved':True,'original_hashes':after}
    (HERE/'reports/pc_crosscheck.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':out['passed'],'old_evidence_preserved':True,'nonempty_nms_fixture':ids},indent=2))


if __name__=='__main__':main()
