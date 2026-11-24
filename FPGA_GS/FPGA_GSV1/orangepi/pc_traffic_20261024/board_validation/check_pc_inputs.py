"""Independent PC regeneration of fixed inputs and ONNX reference tensors."""
import hashlib
import json
import platform
from pathlib import Path
import cv2
import numpy as np
import onnxruntime as ort

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'reports/board_preflight_r1'


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    report=json.loads((EVIDENCE/'numeric_validation.json').read_text())
    options=ort.SessionOptions();options.intra_op_num_threads=2
    sess=ort.InferenceSession(str(ROOT/'artifacts/yolov8n_2class_640_UNTRAINED_raw6_rknn_preflight.onnx'),options,providers=['CPUExecutionProvider'])
    records=[]
    for entry in report['comparisons']:
        name=entry['fixture']
        if name.startswith('SYNTHETIC'):
            y,x=np.mgrid[0:301,0:503]
            image=np.stack(((3*x+y)%256,(7*y+31)%256,(x+11*y+83)%256),2).astype('uint8')
        else:
            source=ROOT.parent/'m406/evidence/exact_source'/Path(entry['source']).name
            assert sha(source.read_bytes())==entry['source_sha256']
            image=cv2.imread(str(source));x1,y1,x2,y2=entry['source_roi_xyxy'];image=image[y1:y2,x1:x2]
        h,w=image.shape[:2];ratio=640/max(h,w)
        dims=(int(round(w*ratio)),int(round(h*ratio)))
        dw,dh=640-dims[0],640-dims[1]
        # Independent implementation: resize BGR then copyMakeBorder, then RGB.
        resized=cv2.resize(image,dims,interpolation=cv2.INTER_LINEAR)
        prepared=cv2.cvtColor(cv2.copyMakeBorder(resized,dh//2,dh-dh//2,dw//2,dw-dw//2,
                                                cv2.BORDER_CONSTANT,value=(114,114,114)),cv2.COLOR_BGR2RGB)
        saved=np.load(EVIDENCE/'fixtures'/f'{name}_rgb_u8.npy')
        assert np.array_equal(prepared,saved),name
        assert sha(prepared.tobytes())==entry['input_rgb_u8_sha256']
        actual=sess.run(None,{'images':np.ascontiguousarray(prepared.transpose(2,0,1)[None],dtype=np.float32)/255})
        reference=np.load(EVIDENCE/'fixtures'/f'{name}_onnx_outputs.npz')
        heads=[{'name':n,'max_abs':float(np.abs(a-reference[n]).max())}
               for n,a in zip([o.name for o in sess.get_outputs()],actual)]
        records.append({'fixture':name,'input_byte_identical':True,'input_sha256':sha(prepared.tobytes()),
                        'pc_vs_board_onnx_heads':heads,'passed':all(h['max_abs']<1e-5 for h in heads)})
    out={'passed':all(r['passed'] for r in records),'python':platform.python_version(),
         'opencv':cv2.__version__,'numpy':np.__version__,'onnxruntime':ort.__version__,
         'scope':'Independent PC input preparation and ORT reference, not trained accuracy',
         'comparisons':records}
    (EVIDENCE/'pc_input_validation.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
