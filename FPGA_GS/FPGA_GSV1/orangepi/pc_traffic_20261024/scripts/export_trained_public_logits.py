"""Export the finished selected checkpoint; never mutate training or deployment."""
import ast
import collections
import copy
import hashlib
import json
import types
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
import onnx
import onnxruntime as ort
import onnxsim
import torch
from onnx import helper, numpy_helper
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'artifacts/public_body_r1_trained_logits_r1'
NAMES = [v for s in (8,16,32) for v in (f'box_s{s}', f'class_logits_s{s}')]
LIMITS = {'raw_head_max_abs':.001, 'decoded_box_max_abs_input_px':.01,
          'cpu_activated_score_max_abs':.00001}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sigmoid(x):
    x = np.asarray(x,dtype=np.float64)
    out = np.empty_like(x)
    positive = x >= 0
    out[positive] = 1/(1+np.exp(-x[positive]))
    expx = np.exp(x[~positive])
    out[~positive] = expx/(1+expx)
    return out


def raw_logits(self,x):
    outputs = []
    for i in range(self.nl):
        outputs.extend((self.cv2[i](x[i]), self.cv3[i](x[i])))
    return tuple(outputs)


def main():
    progress = json.loads((ROOT/'reports/public_training_progress_r1.json').read_text('utf-8'))
    assert progress['status'] == 'completed' and progress['completed_epochs'] == 60
    assert progress['optimizer_updates'] > 0 and progress['production_train_val_save_verified']
    checkpoint = ROOT/progress['best_checkpoint']
    digest = sha(checkpoint)
    assert not OUT.exists(), 'Frozen export: inspect existing report; never overwrite'
    OUT.mkdir()
    torch.set_num_threads(4)
    native = YOLO(str(checkpoint)).model.float().cpu().eval()
    assert native.names == {0:'motor_vehicle_body', 1:'pedestrian_body'}
    native.fuse(verbose=False)
    head = native.model[-1]
    assert head.nc == 2 and head.reg_max == 16 and list(head.stride.cpu().numpy()) == [8,16,32]
    head.export = True
    head.dynamic = False
    head.format = 'onnx'
    raw_model = copy.deepcopy(native)
    raw_model.model[-1].forward = types.MethodType(raw_logits,raw_model.model[-1])
    initial = OUT/'trained_raw6_logits.onnx'
    torch.onnx.export(raw_model,torch.zeros(1,3,640,640),str(initial),opset_version=12,
        input_names=['images'],output_names=NAMES,do_constant_folding=True,dynamic_axes=None)
    graph, valid = onnxsim.simplify(onnx.load(initial))
    assert valid
    constants = {i.name:numpy_helper.to_array(i) for i in graph.graph.initializer}
    changes = []
    for node in graph.graph.node:
        if node.op_type != 'Resize':
            continue
        attrs = {a.name:helper.get_attribute_value(a) for a in node.attribute}
        assert attrs['mode'] == b'nearest' and attrs['coordinate_transformation_mode'] == b'asymmetric'
        assert attrs['nearest_mode'] == b'floor'
        assert np.array_equal(constants[node.input[2]],np.array([1,1,2,2]))
        # Reuse the previously independently validated exact2x RKNN rewrite.
        del node.attribute[:]
        node.attribute.extend([helper.make_attribute('mode','nearest'),
            helper.make_attribute('coordinate_transformation_mode','half_pixel')])
        changes.append({'node':node.name,'scale':[1,1,2,2],
            'old':'asymmetric/floor', 'new':'half_pixel/round_prefer_floor(default)'})
    assert len(changes) == 2
    helper.set_model_props(graph,{'score_activation':'cpu_stable_sigmoid_once',
        'checkpoint_sha256':digest, 'trained':'true','class_order':'motor_vehicle_body,pedestrian_body'})
    onnx.checker.check_model(graph)
    deployed = OUT/'yolov8n_body2_640_trained_raw6_logits.onnx'
    onnx.save(graph,deployed)
    # Extract only pure, SHA-bound previous decoder functions: no board imports.
    decoder = ROOT/'board_validation/validate_numeric.py'
    prior_contract = json.loads((ROOT/'board_validation/logits_candidate_r1/reports/export_contract.json').read_text())
    assert sha(decoder) == prior_contract['decoder_source_sha256']
    tree = ast.parse(decoder.read_text('utf-8'))
    namespace = {'np':np,'cv2':cv2}
    funcs = [v for v in tree.body if isinstance(v,ast.FunctionDef) and v.name in ('letterbox','decode','nms')]
    assert len(funcs) == 3
    exec(compile(ast.Module(body=funcs,type_ignores=[]),str(decoder),'exec'),namespace)
    options = ort.SessionOptions(); options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(deployed),options,providers=['CPUExecutionProvider'])
    assert [e.name for e in session.get_outputs()] == NAMES
    manifest = json.loads((ROOT/'datasets/public_body_r1/manifest.json').read_text('utf-8'))
    selected = [next(e for e in manifest['entries'] if e['source']['family'] == 'S2TLD720_native_day'),
        next(e for e in manifest['entries'] if e['source']['family'] == 'TLoNY_native'
            and any(line.startswith('1 ') for line in (ROOT/e['label']).read_text().splitlines())),
        next(e for e in manifest['entries'] if e['split'] == 'val')]
    fixtures = []
    for e in selected:
        assert e['split'] != 'holdout'
        assert sha(ROOT/e['image']) == e['image_sha256']
        rgb,meta = namespace['letterbox'](cv2.imread(str(ROOT/e['image'])))
        fixtures.append((e['candidate_id'],rgb,{'source':e['image'],'source_sha256':e['image_sha256'],
            'split':e['split'],'preprocess':meta,'purpose':'numerical equivalence only, not accuracy measurement'}))
    for p in sorted((ROOT/'board_validation/logits_candidate_r1/fixtures').glob('*_rgb_u8.npy')):
        fixtures.append((p.stem.replace('_rgb_u8',''),np.load(p),{'source':p.relative_to(ROOT).as_posix(),
            'source_sha256':sha(p),'purpose':'existing development/regression fixture only; never train/val/calibration'}))
    (OUT/'fixtures').mkdir()
    checks = []
    for name,rgb,meta in fixtures:
        inp = np.ascontiguousarray(rgb.transpose(2,0,1)[None],dtype=np.float32)/255
        with torch.inference_mode():
            standard = native(torch.from_numpy(inp)).numpy()
            expected_raw = [v.numpy() for v in raw_model(torch.from_numpy(inp))]
        actual_raw = session.run(NAMES,{'images':inp})
        activated = [sigmoid(v) if i%2 else v for i,v in enumerate(actual_raw)]
        boxes,scores = namespace['decode'](activated)
        xywh = standard[0,:4].T
        want_boxes = np.concatenate((xywh[:,:2]-xywh[:,2:]/2,xywh[:,:2]+xywh[:,2:]/2),axis=1)
        errors = {'raw_head_max_abs':max(float(np.abs(a-b).max()) for a,b in zip(expected_raw,actual_raw)),
            'decoded_box_max_abs_input_px':float(np.abs(boxes-want_boxes).max()),
            'cpu_activated_score_max_abs':float(np.abs(scores-standard[0,4:].T).max())}
        assert all(errors[k] < v for k,v in LIMITS.items()), (name,errors)
        np.save(OUT/'fixtures'/f'{name}_rgb_u8.npy',rgb)
        np.savez_compressed(OUT/'fixtures'/f'{name}_onnx_raw.npz',**dict(zip(NAMES,actual_raw)))
        meta.update(fixture=name,input_sha256=sha(OUT/'fixtures'/f'{name}_rgb_u8.npy'),
            raw_reference_sha256=sha(OUT/'fixtures'/f'{name}_onnx_raw.npz'),
            errors=errors,passed=True,nonempty_NMS_detection_count=len(namespace['nms'](boxes,scores)))
        checks.append(meta)
    # A second Sigmoid is demonstrably wrong for already activated scores.
    logits = np.array([[2.,-12.],[-12.,2.],[-2.,-12.]])
    guard_boxes = np.array([[0,0,100,100],[0,0,100,100],[200,200,250,250]],float)
    keep = [(a,c) for a,c,_ in namespace['nms'](guard_boxes,sigmoid(logits))]
    assert keep == [(0,0),(1,1)]
    assert [(a,c) for a,c,_ in namespace['nms'](guard_boxes,sigmoid(sigmoid(logits)))] != keep
    assert np.isfinite(sigmoid(np.array([-1000.,0.,1000.]))).all()
    assert sha(checkpoint) == digest
    outputs = [{'name':e.name,'shape':e.shape,'role':'class_logits' if i%2 else 'box_dfl_logits'}
               for i,e in enumerate(session.get_outputs())]
    result = {'recorded_at':datetime.now(timezone.utc).isoformat(),'passed':True,'trained':True,
        'checkpoint':checkpoint.relative_to(ROOT).as_posix(),'checkpoint_sha256':digest,
        'checkpoint_not_modified':True,'release':progress['release'],'release_sha256':progress['release_sha256'],
        'onnx':deployed.relative_to(ROOT).as_posix(),'onnx_sha256':sha(deployed),
        'training_imgsz':960,'deployment_imgsz':640,'imgsz_accuracy_equivalence_claimed':False,
        'preprocess_PC':'RGB NCHW float32 /255; centered letterbox114, static640',
        'preprocess_RKNN':'RGB NHWC uint8; embedded mean0/std255; same centered letterbox114',
        'outputs':outputs,'score_activation':'cpu_stable_sigmoid_once',
        'classification_output_contains_sigmoid':False,'class_names':native.names,
        'opset':12,'ops':dict(collections.Counter(n.op_type for n in graph.graph.node)),
        'resize_rewrites':changes,'decoder':decoder.relative_to(ROOT).as_posix(),
        'decoder_sha256':sha(decoder),'limits':LIMITS,'comparisons':checks,
        'stable_single_sigmoid_nonempty_NMS_guard_passed':True,
        'board_validation_passed':False,'RKNN_build_or_runtime_performed_here':False,
        'accuracy_verified_by_numeric_checks':False,'no_final_test_or_China_reserved_inference':True,
        'next_required':'Independent isolated RKNN candidate build/runtime with this exact ONNX and fixed thresholds; do not modify stable services.'}
    for p in (OUT/'export_validation.json',ROOT/'reports/trained_logits_export_r1.json'):
        p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('passed','checkpoint_sha256','onnx','onnx_sha256','board_validation_passed')},ensure_ascii=False))


if __name__ == '__main__':
    main()
