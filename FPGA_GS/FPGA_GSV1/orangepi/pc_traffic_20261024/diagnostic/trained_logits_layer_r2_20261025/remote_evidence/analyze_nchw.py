"""Corrected single-fixture same-config layer diagnostic; no deployment."""
import datetime
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import time
import traceback

import numpy as np
from rknn.api import RKNN
from rknn.api.rknn_utils import get_input_img

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ONNX = BASE/'inputs/yolov8n_body2_640_trained_raw6_logits.onnx'
RGB = BASE/'inputs/fixtures/s2tld720_000000_rgb_u8.npy'
CONFIG = dict(mean_values=[[0,0,0]],std_values=[[255,255,255]],
              target_platform='rk3588',optimization_level=3)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(name, obj):
    (HERE/name).write_text(json.dumps(obj,indent=2)+'\n')


def idle():
    ps=subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout
    active=[s for s in ps.splitlines() if 'python' in s and
            any(t in s for t in ('m406/demo','m405r2/demo','--mode LIVE_FRONT','--mode FILE_TEST'))]
    if active:
        raise RuntimeError('Existing demo left untouched; contention declined: '+str(active))
    return ps


def protected():
    return {str(p.relative_to(BASE)):sha(p) for p in BASE.rglob('*')
            if p.is_file() and HERE not in p.parents}


def main():
    assert sha(ONNX)=='ed944ebfeab6574b17577a57306e0017d751d992b5ad865723b1d5986c67ece2'
    assert sha(RGB)=='84abceda7cf31828c9acfc5ad088c0af7895bbd0bb63424b625e37d1293b5778'
    assert sha(BASE/'trained_raw6_logits_fp16.rknn')=='fbf48333ee9d15a33078b83580013c72e313ae6f877e195500052479e7b81fc8'
    before=protected()
    rgb=np.load(RGB,allow_pickle=False)
    x=np.ascontiguousarray(rgb.transpose(2,0,1)[None])
    assert rgb.shape==(640,640,3) and x.shape==(1,3,640,640) and x.dtype==np.uint8
    assert np.array_equal(x[0].transpose(1,2,0),rgb)
    inp=HERE/'same_fixture_RGB_NCHW_u8.npy'
    assert not inp.exists();np.save(inp,x,allow_pickle=False)
    loaded=get_input_img(str(inp),'nchw',[1,3,640,640],'nchw',False)
    assert np.array_equal(loaded,x) and loaded.dtype==np.uint8
    dump('input_contract.json',dict(source=str(RGB),source_sha256=sha(RGB),source_shape=list(rgb.shape),
        analysis_input=str(inp),analysis_input_sha256=sha(inp),shape=list(x.shape),dtype=str(x.dtype),
        RGB_pixels_roundtrip_exact=True,
        canonical_HWC_RGB_pixel_sha256=hashlib.sha256(np.ascontiguousarray(x[0].transpose(1,2,0)).tobytes()).hexdigest(),
        original_HWC_RGB_pixel_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),
        toolkit_get_input_img_signature=str(inspect.signature(get_input_img)),
        toolkit_loader_returns_identical_u8=True,application_divide_by_255=False,
        mean_values=CONFIG['mean_values'],std_values=CONFIG['std_values'],
        normalization_contract='Raw RGB uint8 values retained by application and Toolkit get_input_img; configure mean0/std255 once. Expected model input is raw/255. No pre-normalized npy is supplied.',
        normalization_execution_check='If snapshots become available, compare FP32 outputs/input evidence against the original supplied ONNX normalized reference; caller contract alone is not claimed as proof of internal SDK dump normalization.'))
    dump('installed_api.json',{n:dict(signature=str(inspect.signature(getattr(RKNN,n))),doc=inspect.getdoc(getattr(RKNN,n)),source=inspect.getsource(getattr(RKNN,n)))
         for n in ('accuracy_analysis','config','build','init_runtime','list_devices')})
    result=dict(recorded_at=datetime.datetime.now().astimezone().isoformat(),diagnostic_only=True,
        original_onnx_sha256=sha(ONNX),original_rknn_sha256=sha(BASE/'trained_raw6_logits_fp16.rknn'),
        selected_fixture='s2tld720_000000',config_arguments=CONFIG,build_arguments={'do_quantization':False},
        analysis_arguments={'inputs':[str(inp)],'output_dir':str(HERE/'snapshot'),'target':'rk3588'},
        number_of_build_calls=0,number_of_analysis_calls=0,new_model_exported=False,
        deployment_passed=False,processes_before=idle())
    model=RKNN(verbose=True)
    try:
        result['config_returncode']=model.config(**CONFIG);assert result['config_returncode']==0
        result['load_onnx_returncode']=model.load_onnx(model=str(ONNX));assert result['load_onnx_returncode']==0
        t=time.perf_counter();result['number_of_build_calls']+=1
        result['build_returncode']=model.build(do_quantization=False)
        result['build_seconds']=time.perf_counter()-t
        assert result['build_returncode']==0
        idle()
        # Keep this exact object and original build state until analysis finishes.
        t=time.perf_counter();result['number_of_analysis_calls']+=1
        result['accuracy_analysis_returncode']=model.accuracy_analysis(
            inputs=[str(inp)],output_dir=str(HERE/'snapshot'),target='rk3588')
        result['analysis_seconds']=time.perf_counter()-t
    except Exception:
        result['exception']=traceback.format_exc()
    finally:
        model.release()
        after=protected();result['original_candidate_unchanged']=before==after
        result['protected_file_count']=len(before)
        result['snapshot_files']=[dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p))
                                  for p in (HERE/'snapshot').rglob('*') if p.is_file()]
        dump('analysis_attempt.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('processes_before','snapshot_files')}),flush=True)
    print(json.dumps({'snapshot_files':result['snapshot_files']}),flush=True)


if __name__=='__main__':
    main()
