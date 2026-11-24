"""Fixed image crop diagnostic, not a real-time throughput claim."""
import importlib.util,json,time,cv2,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
cv2.setNumThreads(2)
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items() if k not in ('thumbnail_jpeg','observation_times')}
 if isinstance(x,list):return [clean(v) for v in x]
 return x
def main():
 mods=[load('original',ROOT.parent/'m406/traffic.py'),load('candidate',ROOT/'traffic.py')]
 models=[m.BodyModel() for m in mods];results=[]
 try:
  for f in sorted((ROOT/'inputs').glob('*')):
   im=cv2.imread(str(f))
   if im is None:continue
   row={'file':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'shape':list(im.shape),'versions':{}}
   for name,m,model in zip(['m406','m406r2'],mods,models):
    model.turn=0;scans=[]
    for i in range(2 if name=='m406' else 5):
     ps,ms,box=model.infer(im)
     scans.append(dict(scan=box,proposals=[m.color_check(im,p)for p in ps],stage_ms=ms))
    g,stats=m.candidates(im);g=[m.color_check(im,p)for p in g if not m.dense_context(im,p['box'])[0]]
    row['versions'][name]=dict(scans=scans,geometry=g,geometry_statistics=stats)
   results.append(clean(row));print(f.name,[(n,sum(len(s['proposals'])for s in row['versions'][n]['scans']),len(row['versions'][n]['geometry']))for n in ['m406','m406r2']],flush=True)
   (ROOT/'evidence/fixed_probe.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 finally:
  for m in models:m.close()
if __name__=='__main__':main()
