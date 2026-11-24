"""Minimal independent Conv+Sigmoid reproduction of observed low-score error."""
import json
import hashlib
from pathlib import Path
import numpy as np
import onnx
from onnx import helper as h, numpy_helper as nh, TensorProto as T
from rknn.api import RKNN
from rknnlite.api import RKNNLite

HERE=Path(__file__).resolve().parents[1]


def main():
    logits=np.array([-12,-10,-8,-7.848,-6.461,-6,-5.075,-4,-2,0,2,4,6,8,10,12],np.float32)
    weight=np.zeros((16,3,1,1),np.float32);weight[:,0,0,0]=.125
    graph=h.make_graph([
        h.make_node('Conv',['input','weight','bias'],['conv'],kernel_shape=[1,1]),
        h.make_node('Sigmoid',['conv'],['score'])],
        'low_score_probe',[h.make_tensor_value_info('input',T.FLOAT,[1,3,8,8])],
        [h.make_tensor_value_info('score',T.FLOAT,[1,16,8,8])],
        [nh.from_array(weight,'weight'),nh.from_array(logits,'bias')])
    model=h.make_model(graph,opset_imports=[h.make_opsetid('',12)]); model.ir_version=9
    source=HERE/'artifacts/DIAGNOSTIC_ONLY_sigmoid_probe.onnx'
    target=source.with_suffix('.rknn')
    assert not target.exists()
    onnx.checker.check_model(model);onnx.save(model,source)
    r=RKNN(verbose=True)
    try:
        assert r.config(mean_values=[[0,0,0]],std_values=[[255,255,255]],target_platform='rk3588',optimization_level=3)==0
        assert r.load_onnx(model=str(source))==0
        assert r.build(do_quantization=False)==0
        assert r.export_rknn(str(target))==0
    finally:
        r.release()
    lite=RKNNLite(verbose=True)
    try:
        assert lite.load_rknn(str(target))==0
        assert lite.init_runtime(core_mask=RKNNLite.NPU_CORE_0)==0
        output=lite.inference(inputs=[np.zeros((1,8,8,3),np.uint8)],data_format=['nhwc'])[0]
        actual=output[0,:,0,0]
    finally:
        lite.release()
    expected=1/(1+np.exp(-logits.astype(np.float64)))
    report={'scope':'Diagnostic micrograph, not replacement of same-SHA full model',
            'rows':[{'logit':float(x),'reference_sigmoid':float(y),'npu':float(z),'abs_error':float(abs(y-z))}
                    for x,y,z in zip(logits,expected,actual)],
            'shape':list(output.shape),
            'onnx_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'rknn_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    (HERE/'reports/sigmoid_probe.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
