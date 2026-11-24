"""Own this candidate only. Never stop or switch the default m406/LIVE service."""
import sys,os,json,time,signal,subprocess,argparse,fcntl,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent
sys.path.insert(0,str(BASE/'operator_v1'))
from ops_manager import proc,identity
PORT=8082
ARGV=['.venv404/bin/python','m406r2/demo.py','--port',str(PORT),'--preview-width','640']
def matches(p):return bool(p and p['uid']==os.getuid()and p['cwd']==str(BASE)and p['argv']==ARGV)
def status():
 try:
  with urllib.request.urlopen('http://127.0.0.1:%d/status.json'%PORT,timeout=2)as r:return json.load(r)
 except Exception:return None
def stop(record):
 p=proc(record['identity']['pid'])if record else None
 if not p:return dict(ok=True,message='候选已经停止')
 if not identity(record['identity'],p)or not matches(p):return dict(ok=False,message='PID身份或启动参数不符，未停止任何进程',process=p)
 os.kill(p['pid'],signal.SIGINT);end=time.monotonic()+15
 while time.monotonic()<end:
  if not identity(p,proc(p['pid'])):return dict(ok=True,message='候选已正常停止；原m406及其他进程未操作')
  time.sleep(.1)
 return dict(ok=False,message='候选停止超时，未强制终止',process=p)
def start(record,state):
 p=proc(record['identity']['pid'])if record else None
 if p:
  s=status()
  if not identity(record['identity'],p)or not matches(p)or not s or s.get('instance')!=record.get('instance'):return dict(ok=False,message='已有PID/HTTP身份不符，拒绝接管',process=p)
  return dict(ok=True,message='复用已有独立候选',process=p,status=s)
 other=[x for x in subprocess.check_output(['ps','-eo','args'],text=True).splitlines()if x.startswith('.venv404/bin/python m406r2/demo.py')]
 if other:return dict(ok=False,message='发现无记录候选进程，未重复启动',conflicts=other)
 # Check only this candidate TCP port; do not bind or probe business UDP.
 sockets=subprocess.check_output(['ss','-lntp'],text=True)
 conflicts=[x for x in sockets.splitlines()if ':%d '%PORT in x]
 if conflicts:return dict(ok=False,message='候选8082端口已有占用，未停止它',conflicts=conflicts)
 for pth in [BASE/'.venv404/bin/python',ROOT/'demo.py',ROOT/'yolov8s640_fp16.rknn']:
  if not pth.exists():return dict(ok=False,message='候选材料缺失：'+str(pth))
 # Avoid competing with a currently running full demo. User can stop it using
 # its own existing entry, then launch this candidate explicitly.
 demos=[x for x in subprocess.check_output(['ps','-eo','args'],text=True).splitlines()if '.venv404/bin/python m406/demo.py' in x or '.venv404/bin/python m405r2/demo.py' in x]
 if demos:return dict(ok=False,message='原演示正在运行；未启停它。请先用原停止入口停止，再启动候选，避免NPU资源竞争。',conflicts=demos)
 with (state/'demo.console.log').open('ab')as log:
  child=subprocess.Popen(ARGV,cwd=BASE,stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),start_new_session=True,close_fds=True)
 end=time.monotonic()+50
 while time.monotonic()<end:
  if child.poll()is not None:return dict(ok=False,message='候选启动后退出，查看m406r2/state/demo.console.log')
  p=proc(child.pid);s=status()
  if matches(p):(state/'service.json').write_text(json.dumps(dict(identity=p,instance=(s or {}).get('instance'))))
  if s and s.get('release')=='M4-06-r2-candidate'and s.get('traffic',{}).get('completed',0)>0 and s.get('road',{}).get('completed',0)>0 and s.get('detection',{}).get('detection_runs',0)>0:
   (state/'service.json').write_text(json.dumps(dict(identity=p,instance=s['instance'])))
   return dict(ok=True,message='独立录像候选已就绪；无UDP、不使用FPGA，默认入口未改变',process=p,status=s)
  time.sleep(.2)
 return dict(ok=False,message='候选HTTP/模型就绪超时，PID已记录，可用候选停止入口',process=p)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','stop']);a=parser.parse_args();state=ROOT/'state';state.mkdir(exist_ok=True)
 with (state/'operation.lock').open('a')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  try:record=json.loads((state/'service.json').read_text())
  except (OSError,ValueError):record=None
  result=start(record,state)if a.action=='start'else stop(record)
 print(json.dumps(result,ensure_ascii=False))
