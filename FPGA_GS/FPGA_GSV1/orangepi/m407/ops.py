"""Scoped lifecycle for M407; no network configuration or system changes."""
import argparse,fcntl,ipaddress,json,os,signal,subprocess,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent;sys.path.insert(0,str(BASE/'operator_v1'))
from ops_manager import proc,identity,matches
PORT=8084
def http():
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/status.json',timeout=2) as r:return json.load(r)
    except Exception:return None
def expected(c,mode):
    return ['.venv404/bin/python','m407/app.py','--mode',mode,'--port',str(PORT),'--preview-width','640','--front-fps',str(c['front_fps']),
            '--bind',c['business_cidr'].split('/')[0],'--peer',c['fpga_ip'],'--udp-port',str(c['udp_port']),'--peer-port',str(c['peer_port'])]
def own(p,c):return bool(p and p['uid']==os.getuid() and p['cwd']==str(BASE) and any(p['argv']==expected(c,m) for m in ['LIVE_FRONT','FILE_TEST']))
def stop_saved(record,c):
    saved=record.get('identity') if record else None;p=proc(saved['pid']) if saved else None
    if not p:return dict(ok=True,message='M407已经停止')
    if not identity(saved,p) or not own(p,c):return dict(ok=False,message='M407 PID身份/参数不符，未结束任何进程')
    os.kill(p['pid'],signal.SIGINT);end=time.monotonic()+22
    while time.monotonic()<end:
        if not identity(saved,proc(saved['pid'])):return dict(ok=True,message='M407已正常停止，UDP和预览端口已释放')
        time.sleep(.1)
    return dict(ok=False,message='M407正常退出超时；未强杀')
def read(p):
    try:return json.loads(p.read_text())
    except (OSError,ValueError):return None
def start(c,state,record,mode):
    p=proc(record['identity']['pid']) if record else None
    if p and identity(record['identity'],p) and own(p,c):
        if p['argv']==expected(c,mode):
            s=http()
            if not s or s['instance']!=record.get('instance'):return dict(ok=False,message='M407进程在运行但HTTP身份未确认，拒绝重复启动')
            return dict(ok=True,message='复用已有M407，无重复UDP客户端',process=p,status=s)
        r=stop_saved(record,c)
        if not r['ok']:return r
        time.sleep(3) # FPGA frozen old-session 2s timeout; not a readiness check.
    if mode=='LIVE_FRONT':
        a=json.loads(subprocess.check_output(['ip','-j','-4','addr','show','dev',c['interface']],text=True))
        addr=[f"{x['local']}/{x['prefixlen']}" for i in a for x in i.get('addr_info',[])]
        if c['business_cidr'] not in addr:return dict(ok=False,message='业务地址缺失；本轮不自动改网络',addresses=addr)
        route=json.loads(subprocess.check_output(['ip','-j','route','get',c['fpga_ip']],text=True))
        if not route or route[0].get('dev')!=c['interface'] or route[0].get('prefsrc')!=c['business_cidr'].split('/')[0]:return dict(ok=False,message='业务路由/源地址不符，未修改网络',route=route)
        if int(Path('/proc/sys/net/core/rmem_max').read_text())<8388608:return dict(ok=False,message='rmem_max低于8MiB；需现有临时sudo缓冲流程，本入口不修改系统参数')
    switched=[]
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():continue
        p=proc(int(d.name))
        if not p or p['uid']!=os.getuid() or p['cwd']!=str(BASE):continue
        args=p['argv']
        confirmed=matches(p,c) or args in [
            ['.venv404/bin/python','m406r2/demo.py','--port','8082','--preview-width','640'],
            ['.venv404/bin/python','m406/demo.py','--port','8080','--preview-width','640']]
        if confirmed:
            switched.append(p);os.kill(p['pid'],signal.SIGINT)
            end=time.monotonic()+22
            while identity(p,proc(p['pid'])) and time.monotonic()<end:time.sleep(.1)
            if identity(p,proc(p['pid'])):return dict(ok=False,message='原项目实例正常退出超时，未强杀',process=p)
        elif len(args)>1 and args[1] in ['main.py','m407/app.py','m406/demo.py','m406r2/demo.py','m405r2/demo.py']:
            return dict(ok=False,message='发现参数不匹配项目进程，未擅自停止或重复启动',process=p)
    if switched:
        (state/'switched_previous.json').write_text(json.dumps(switched,indent=2));time.sleep(3)
    sockets=subprocess.check_output(['ss','-lntup'],text=True)
    conflicts=[l for l in sockets.splitlines() if f':{PORT} ' in l or (mode=='LIVE_FRONT' and f":{c['udp_port']} " in l)]
    if conflicts:return dict(ok=False,message='端口被未确认实例占用，未按端口杀进程',conflicts=conflicts)
    for n in ['.venv404/bin/python','m404/yolov8n.rknn','m405/yolop320_fp16.rknn','m406r2/yolov8s640_fp16.rknn','m407/index.html']:
        if not (BASE/n).exists():return dict(ok=False,message='缺少已有材料：'+n)
    with (state/'service.console.log').open('ab') as f:
        child=subprocess.Popen(expected(c,mode),cwd=BASE,stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
    end=time.monotonic()+60
    while time.monotonic()<end:
        if child.poll() is not None:return dict(ok=False,message='M407启动后退出，查看m407/state/service.console.log')
        p=proc(child.pid);s=http()
        if own(p,c):(state/'service.json').write_text(json.dumps(dict(identity=p,instance=(s or {}).get('instance'))))
        if s and s.get('release') in ('M4-07-r1-candidate','M4-07-r1-netrx-ready') and (mode=='FILE_TEST' or s.get('link',{}).get('socket_receive_buffer_bytes')):
            if s.get('error'):return dict(ok=False,message='M407模块错误，未声明识别可用',status=s)
            if mode=='LIVE_FRONT' and s['link']['socket_receive_buffer_bytes']<8388608:return dict(ok=False,message='实际SO_RCVBUF不足8MiB',status=s)
            return dict(ok=True,message='M407服务及独立预览已启动；FPGA通信/目标识别状态请看实时页面',process=p,status=s,switched=switched)
        time.sleep(.2)
    return dict(ok=False,message='M407就绪超时，已记录PID可用停止入口')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','stop']);p.add_argument('--mode',choices=['LIVE_FRONT','FILE_TEST'],default='LIVE_FRONT');a=p.parse_args()
    c=json.loads((ROOT/'ops_config.json').read_text());state=ROOT/'state';state.mkdir(exist_ok=True)
    with (state/'operation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);record=read(state/'service.json')
        r=start(c,state,record,a.mode) if a.action=='start' else stop_saved(record,c)
    print(json.dumps(r,ensure_ascii=False))
