"""Same RGB/PTS replay through both COMPLETE traffic branches.

Offline evidence only. Output video follows source PTS, not inference throughput.
Both receive the same unchanged YOLOv8n object exclusions. No road changes.
"""
import sys,json,time,cv2,numpy as np,importlib.util,subprocess,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from functools import lru_cache
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent
sys.path.append(str(BASE/'m404'))
from detector import Detector
cv2.setNumThreads(2)
class Clock:
 def __init__(self):self.now=1000.
 def monotonic(self):return self.now
 perf_counter=staticmethod(time.perf_counter)
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.time=Clock();return m
def compact(v):
 if isinstance(v,dict):return {k:compact(x)for k,x in v.items()if k not in ('thumbnail_jpeg','observation_times')}
 if isinstance(v,(list,tuple)):return [compact(x)for x in v]
 if isinstance(v,np.generic):return v.item()
 return v
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
@lru_cache(maxsize=256)
def tile(s,size,color):
 f=ImageFont.truetype(FONT,size);bb=f.getbbox(s);a=Image.new('RGB',(bb[2]+5,size+10),(14,21,31));ImageDraw.Draw(a).text((1,0),s,font=f,fill=color);return cv2.cvtColor(np.asarray(a),cv2.COLOR_RGB2BGR)
def text(im,s,x,y,size=16,color=(235,235,235)):
 a=tile(s,size,color);h,w=a.shape[:2];w=min(w,im.shape[1]-x);h=min(h,im.shape[0]-y)
 if w>0 and h>0:im[y:y+h,x:x+w]=a[:h,:w]
COLORS={'RED':(80,80,255),'GREEN':(80,255,100),'YELLOW':(40,220,255),'UNKNOWN':(190,190,190)}
def panel(im,result,now,title,sec,mod,source_images=None):
 out=np.full((600,640,3),(14,21,31),np.uint8);h,w=im.shape[:2];out[36:396]=cv2.resize(im,(640,360));text(out,title,8,4,20)
 lights=mod.fresh(result,now,1).get('lights',[])if result else []
 for b in lights:
  x0,y0,x1,y1=np.round(np.array(b['box'])*[640/w,360/h,640/w,360/h]).astype(int);co=COLORS[b['color']]
  cv2.rectangle(out,(x0-2,y0+34),(x1+2,y1+38),co,2);cv2.putText(out,'#%s %s'%(b['id'],b['color']),(x0,max(48,y0+30)),0,.38,co,1,cv2.LINE_AA)
 # Visible source-derived body crops, with source frame, age and origin label.
 lights=sorted(lights,key=lambda b:(b['color']=='UNKNOWN',b.get('confidence')is not None))
 for i,b in enumerate(lights[:3]):
  source=(source_images or {}).get(b['source_frame_id'])
  x0,y0,x1,y1=map(int,b['box']);p=source[max(0,y0-3):min(h,y1+3),max(0,x0-3):min(w,x1+3)] if source is not None else np.empty((0,0,3),np.uint8)
  if p.size:out[408:478,8+i*210:208+i*210]=cv2.resize(p,(200,70),interpolation=cv2.INTER_NEAREST)
  state={'DIRECT_IMAGE':'检测','IMAGE_BODY_TRACK':'图像跟踪','TEMPORAL_HOLD':'旧证据暂存'}.get(b.get('source'),'检测')
  text(out,'#%s %s · %s'%(b['id'],mod.CN[b['color']],state),8+i*210,480,14)
  cv2.putText(out,'f%s %.0fms'%(b['source_frame_id'],(now-b['decoded_monotonic'])*1000),(8+i*210,520),0,.43,(220,220,220),1)
 text(out,'来源时间 %.3fs · 控制关系未知 · 不自动放行'%sec,8,540,16)
 text(out,'无可靠候选' if not lights else next((b.get('reason','')for b in lights if b['color']=='UNKNOWN'),'当前图像灯色已确认'),8,567,14)
 return out
def main():
 mods=[load('m406_orig',BASE/'m406/traffic.py'),load('m406r2_candidate',ROOT/'traffic.py')]
 models=[m.Lights()for m in mods];detector=Detector();ev=ROOT/'evidence/offline';ev.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((ROOT/'fixed_manifest.json').read_text());allrows=[];summary=[]
 try:
  # Fixed twelve static inputs: original per-region proposals are already saved
  # in fixed_probe. Reuse their EXACT NPU output, re-evaluate CPU checks only.
  static=json.loads((ROOT/'evidence/fixed_probe.json').read_text());fixed=[]
  for row in static:
   im=cv2.imread(str(ROOT/'inputs'/row['file']));record=dict(file=row['file'],sha256=row['sha256'],versions={})
   for name,mod in zip(['m406','m406r2'],mods):
    g,st=mod.candidates(im);items=[mod.color_check(im,p)for p in g if not mod.dense_context(im,p['box'])[0]]
    for scan in row['versions'][name]['scans']:
     for p in scan['proposals']:
      b=mod.color_check(im,p)
      if name=='m406r2'and mod.dense_context(im,b['box'])[0]:continue
      if not any(mod.overlap(b['box'],x['box'])>.25 for x in items):items.append(b)
    record['versions'][name]=dict(lights=items,statistics=st,scope='static crop-cycle coverage; observed RGB color only, no simulated temporal confirmation')
   fixed.append(compact(record))
  (ev/'fixed_results.json').write_text(json.dumps(fixed,ensure_ascii=False,indent=2))
  for v in manifest['entries']:
   name=v['name'];start=v['start_seconds'];end=v['end_seconds'];pts=json.loads((BASE/'m403'/f'{name}.pts.json').read_text())
   import bisect
   first=bisect.bisect_left(pts,start);last=bisect.bisect_left(pts,end)
   cap=cv2.VideoCapture(str(BASE/'media'/name));cap.set(cv2.CAP_PROP_POS_FRAMES,first);cursor=first
   for model,mod in zip(models,mods):model.reset();mod.time.now=1000.+start
   detector.reset();results=[None,None];rows=[];next_observation=start
   video=ev/(Path(name).stem+'_m406_vs_m406r2.mp4')
   encoder=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','1280x600','-r','15','-i','-','-an','-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE)
   last_im=None;wall=time.perf_counter()
   for output_sec in np.arange(start,end,1/15):
    target=min(last-1,bisect.bisect_right(pts,float(output_sec))-1)
    while cursor<=target:
     ok,im=cap.read();cursor+=1
     if not ok:raise RuntimeError('source decode failed '+name)
     last_im=im
    source_sec=pts[cursor-1];frame=cursor-1
    if source_sec+1e-5>=next_observation:
     objects=detector.detect(last_im,1,frame)['objects'];record=dict(video=name,source_frame_id=frame,source_pts=source_sec,versions={})
     for j,(model,mod)in enumerate(zip(models,mods)):
      mod.time.now=1000.+source_sec
      results[j]=model.analyze(last_im,1,frame,mod.time.now,objects)
      record['versions'][['m406','m406r2'][j]]=compact(results[j])
     rows.append(record);next_observation=source_sec+.25
    now=1000.+source_sec
    panels=[panel(last_im,result,now,title,source_sec,mod)for result,title,mod in zip(results,['原版 m406 完整交通灯支路','候选 m406r2 同权重'],mods)]
    canvas=np.hstack(panels);encoder.stdin.write(canvas.tobytes())
   encoder.stdin.close();assert encoder.wait()==0;cap.release()
   (ev/(Path(name).stem+'_predictions.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in rows))
   allrows+=rows;summary.append(dict(video=name,start=start,end=end,observations=len(rows),output_frames=round((end-start)*15),offline_wall_seconds=time.perf_counter()-wall,real_time_performance_claimed=False))
   print(name,'saved',len(rows),'observations',flush=True)
   (ev/'summary.json').write_text(json.dumps(summary,indent=2))
  # Original LED failure frame: static, no fake consecutive image confirmation.
  print('complete',flush=True)
 finally:
  detector.close()
  for model in models:model.close()
if __name__=='__main__':main()
