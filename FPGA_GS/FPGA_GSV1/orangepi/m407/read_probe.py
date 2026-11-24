"""One read-only, PID-owned socket/NIC/status sample. No business socket."""
import json,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent;sys.path.insert(0,str(BASE/'operator_v1'))
from collect_freeze import socket_rows,udp_global,hardware
record=json.loads((ROOT/'state/service.json').read_text());pid=record['identity']['pid']
s=json.load(urllib.request.urlopen('http://127.0.0.1:8084/status.json',timeout=3));s.pop('control_token',None)
pid=s.get('link',{}).get('receiver_process_pid',pid)
nic={p.name:int(p.read_text()) for p in Path('/sys/class/net/eth0/statistics').iterdir()}
r=dict(monotonic=time.monotonic(),pid=pid,socket=socket_rows([pid],50000),udp_global=udp_global(),nic=nic,
       hardware=hardware('eth0'),status=s)
if len(sys.argv)>1:(ROOT/'evidence').mkdir(exist_ok=True);(ROOT/'evidence'/sys.argv[1]).write_text(json.dumps(r,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in r.items() if k!='status'},ensure_ascii=False))
