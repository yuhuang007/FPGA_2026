"""One authorized same-config diagnostic build, one fixed fixture analysis."""
import datetime
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import time
import traceback

from rknn.api import RKNN

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ONNX = BASE/'inputs/yolov8n_body2_640_trained_raw6_logits.onnx'
INPUT = BASE/'inputs/fixtures/s2tld720_000000_rgb_u8.npy'
CONFIG = dict(mean_values=[[0,0,0]], std_values=[[255,255,255]],
              target_platform='rk3588', optimization_level=3)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def idle():
    ps = subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True).stdout
    found = [s for s in ps.splitlines() if 'python' in s and
             any(t in s for t in ('m406/demo','m405r2/demo','--mode LIVE_FRONT','--mode FILE_TEST'))]
    if found:
        raise RuntimeError('Demo left untouched; refusing contention: '+str(found))
    return ps


def protected():
    return {str(p.relative_to(BASE)):sha(p) for p in BASE.rglob('*')
            if p.is_file() and HERE not in p.parents}


def main():
    assert sha(ONNX)=='ed944ebfeab6574b17577a57306e0017d751d992b5ad865723b1d5986c67ece2'
    assert sha(INPUT)=='84abceda7cf31828c9acfc5ad088c0af7895bbd0bb63424b625e37d1293b5778'
    assert sha(BASE/'trained_raw6_logits_fp16.rknn')=='fbf48333ee9d15a33078b83580013c72e313ae6f877e195500052479e7b81fc8'
    before = protected()
    result = dict(recorded_at=datetime.datetime.now().astimezone().isoformat(),
        diagnostic_only=True,passed_as_deployment=False,onnx_sha256=sha(ONNX),
        original_rknn_sha256=sha(BASE/'trained_raw6_logits_fp16.rknn'),
        fixture='s2tld720_000000',fixture_sha256=sha(INPUT),
        config_arguments=CONFIG,build_arguments={'do_quantization':False},
        same_config_as_r1=True,config_unspecified_defaults_unchanged=True,
        analysis_arguments={'inputs':[str(INPUT)],'output_dir':str(HERE/'snapshot'),'target':'rk3588'},
        process_state_before=idle(),model_exported=False,number_of_build_calls=0,
        number_of_analysis_calls=0,original_candidate_unchanged=None)
    result['installed_accuracy_analysis_signature'] = str(inspect.signature(RKNN.accuracy_analysis))
    model = RKNN(verbose=True)
    try:
        result['config_returncode'] = model.config(**CONFIG)
        assert result['config_returncode']==0
        result['load_onnx_returncode'] = model.load_onnx(model=str(ONNX))
        assert result['load_onnx_returncode']==0
        t=time.perf_counter();result['number_of_build_calls']+=1
        result['build_returncode'] = model.build(do_quantization=False)
        result['build_seconds'] = time.perf_counter()-t
        assert result['build_returncode']==0
        idle()
        # Keep the original FP32/build state alive for the single analysis call.
        t=time.perf_counter();result['number_of_analysis_calls']+=1
        result['accuracy_analysis_returncode'] = model.accuracy_analysis(
            inputs=[str(INPUT)],output_dir=str(HERE/'snapshot'),target='rk3588')
        result['analysis_seconds'] = time.perf_counter()-t
    except Exception:
        result['exception'] = traceback.format_exc()
    finally:
        model.release()
        after=protected();result['original_candidate_unchanged'] = before==after
        result['protected_file_count']=len(before)
        result['snapshot_files']=[{'path':str(p.relative_to(HERE)), 'bytes':p.stat().st_size,'sha256':sha(p)}
                                  for p in (HERE/'snapshot').rglob('*') if p.is_file()]
        (HERE/'analysis_attempt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='process_state_before'}),flush=True)


if __name__=='__main__':
    main()
