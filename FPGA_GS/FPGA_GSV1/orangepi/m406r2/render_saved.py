"""Render saved predictions only; no models, inference, or decisions rerun."""
import json,bisect,subprocess,types
from pathlib import Path
import cv2,numpy as np
from compare_offline import ROOT,BASE,panel
def fresh(r,now,epoch):
 return dict(r,lights=[b for b in r.get('lights',[])if now-b['decoded_monotonic']<=.6])if r and now-r['decoded_monotonic']<=.6 else dict(lights=[])
mod=types.SimpleNamespace(fresh=fresh,CN={'RED':'红','GREEN':'绿','YELLOW':'黄','UNKNOWN':'不可判'})
ev=ROOT/'evidence/offline';m=json.loads((ROOT/'fixed_manifest.json').read_text())
for v in m['entries']:
 name=v['name'];start=v['start_seconds'];end=v['end_seconds'];pts=json.loads((BASE/'m403'/f'{name}.pts.json').read_text());rows=[json.loads(x)for x in (ev/(Path(name).stem+'_predictions.jsonl')).read_text().splitlines()];byframe={x['source_frame_id']:x for x in rows}
 first=bisect.bisect_left(pts,start);cap=cv2.VideoCapture(str(BASE/'media'/name));cap.set(cv2.CAP_PROP_POS_FRAMES,first);cursor=first;images={};results=[None,None];last_im=None
 output=ev/(Path(name).stem+'_source_exact.mp4')
 enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','1280x600','-r','15','-i','-','-an','-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],stdin=subprocess.PIPE)
 for sec in np.arange(start,end,1/15):
  target=bisect.bisect_right(pts,float(sec))-1
  while cursor<=target:
   ok,im=cap.read()
   if not ok:raise RuntimeError(name)
   last_im=im
   if cursor in byframe:
    images[cursor]=im.copy();r=byframe[cursor];results=[r['versions'][n]for n in ['m406','m406r2']]
   cursor+=1
  canvas=np.hstack([panel(last_im,result,1000.+pts[cursor-1],title,pts[cursor-1],mod,images)for result,title in zip(results,['原版 m406 完整交通灯支路','候选 m406r2 同权重'])])
  enc.stdin.write(canvas.tobytes())
 enc.stdin.close();assert enc.wait()==0;cap.release();print(name,'source exact rendering saved',flush=True)
