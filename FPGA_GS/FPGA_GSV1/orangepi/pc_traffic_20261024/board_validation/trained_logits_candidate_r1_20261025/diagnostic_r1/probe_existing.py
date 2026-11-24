"""One existing-model layer-analysis attempt; never builds a replacement."""
import datetime
import hashlib
import importlib.metadata as md
import inspect
import json
from pathlib import Path
import subprocess
import sys
import traceback

from rknn.api import RKNN

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent
MODEL = CANDIDATE/'trained_raw6_logits_fp16.rknn'
INPUT = CANDIDATE/'inputs/fixtures/s2tld720_000000_rgb_u8.npy'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ps = subprocess.run(['ps','-eo','pid,args'], capture_output=True, text=True).stdout
    conflicts = [s for s in ps.splitlines() if 'python' in s and
                 any(x in s for x in ('m406/demo','m405r2/demo','--mode LIVE_FRONT','--mode FILE_TEST'))]
    if conflicts:
        raise RuntimeError('Existing demo left untouched; diagnostic declined: '+str(conflicts))
    assert sha(MODEL)=='fbf48333ee9d15a33078b83580013c72e313ae6f877e195500052479e7b81fc8'
    assert sha(INPUT)=='84abceda7cf31828c9acfc5ad088c0af7895bbd0bb63424b625e37d1293b5778'
    api = {}
    for name in ('load_rknn','accuracy_analysis','config','build','init_runtime',
                 'hybrid_quantization_step1','hybrid_quantization_step2'):
        m = getattr(RKNN,name)
        api[name] = dict(signature=str(inspect.signature(m)),doc=inspect.getdoc(m),source=inspect.getsource(m))
    wrapper = Path(inspect.getfile(RKNN))
    (HERE/'installed_api.json').write_text(json.dumps(dict(
        toolkit=md.version('rknn-toolkit2'),wrapper_path=str(wrapper),wrapper_sha256=sha(wrapper),API=api),indent=2)+'\n')
    before = {str(p.relative_to(CANDIDATE)):sha(p) for p in CANDIDATE.rglob('*')
              if p.is_file() and HERE not in p.parents}
    result = dict(recorded_at=datetime.datetime.now().astimezone().isoformat(),
                  selected_fixture='s2tld720_000000',rknn_sha256=sha(MODEL),input_sha256=sha(INPUT),
                  accuracy_analysis_arguments=dict(inputs=[str(INPUT)],output_dir=str(HERE/'snapshot'),target='rk3588'),
                  build_called=False,config_called=False,load_onnx_called=False,model_reexported=False,
                  new_inputs_used=False,original_candidate_unchanged=None)
    model = RKNN(verbose=True)
    try:
        result['load_rknn_returncode'] = model.load_rknn(str(MODEL))
        assert result['load_rknn_returncode']==0
        result['accuracy_analysis_returncode'] = model.accuracy_analysis(
            inputs=[str(INPUT)],output_dir=str(HERE/'snapshot'),target='rk3588')
    except Exception:
        result['exception'] = traceback.format_exc()
    finally:
        model.release()
        after = {str(p.relative_to(CANDIDATE)):sha(p) for p in CANDIDATE.rglob('*')
                 if p.is_file() and HERE not in p.parents}
        result['original_candidate_unchanged'] = before==after
        result['candidate_protected_file_count'] = len(before)
        result['snapshot_files'] = [str(p.relative_to(HERE)) for p in (HERE/'snapshot').rglob('*') if p.is_file()]
        (HERE/'attempt_result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
