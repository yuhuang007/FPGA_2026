"""Scoped temporary original-code benchmark lifecycle, independent TCP8083."""
import os,sys,json,time,subprocess,signal,urllib.request
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(BASE/'operator_v1'))
from ops_manager import proc,identity
record=BASE/'m406r2/state/baseline_benchmark.json'
argv=['.venv404/bin/python','m406r2/baseline_benchmark.py','--port','8083','--preview-width','640']
if sys.argv[1]=='stop':
 p=json.loads(record.read_text());current=proc(p['pid'])
 if current:
  assert identity(p,current) and current['argv']==argv and current['cwd']==str(BASE) and current['uid']==os.getuid()
  os.kill(p['pid'],signal.SIGINT)
  for _ in range(150):
   if not identity(p,proc(p['pid'])):break
   time.sleep(.1)
  else:raise RuntimeError('benchmark stop timeout; no force kill')
 print(json.dumps({'stopped':True,'pid':p['pid']}))
else:
 assert not any(':8083 'in x for x in subprocess.check_output(['ss','-lntp'],text=True).splitlines())
 if record.exists():
  previous=json.loads(record.read_text());assert not identity(previous,proc(previous['pid']))
 with (BASE/'m406r2/state/baseline_benchmark.log').open('ab')as log:
  child=subprocess.Popen(argv,cwd=BASE,stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),start_new_session=True)
 for _ in range(200):
  p=proc(child.pid)
  if p:record.write_text(json.dumps(p))
  try:
   with urllib.request.urlopen('http://127.0.0.1:8083/status.json',timeout=1)as response:s=json.load(response)
   if s['traffic']['completed']>0 and s['road']['completed']>0:
    print(json.dumps({'pid':child.pid,'release':s['release'],'ready':True}));break
  except Exception:pass
  if child.poll()is not None:raise RuntimeError('benchmark exited')
  time.sleep(.2)
 else:raise RuntimeError('benchmark readiness timeout')
