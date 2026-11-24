"""Prepare independent original/crop views; bind manually authored image findings."""
import collections,datetime,hashlib,json,sys
from pathlib import Path
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1];O=R/'review_stage2/independent_codex_board_r2';Q=R/'review_stage2/remaining_independent_queue/queue_index.json'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def entries(batch):
 b=next(x for x in read(Q)['batches'] if x['batch_id']==batch);out=[]
 templates={r['candidate_id']:r for r in map(json.loads,(R/b['fillback_template']).read_text(encoding='utf-8').splitlines())}
 for t in b['tasks']:
  mp=R/t['current_manifest'];assert sha(mp)==t['manifest_sha256'];m=read(mp);e=next(e for e in m['entries'] if e['candidate_id']==t['candidate_id']);ap=R/t['annotation_file'];a=read(ap);ip=mp.parent/e['image'];assert sha(ap)==e['annotation_sha256']==t['annotation_sha256'];assert sha(ip)==e['image_sha256']==t['image_sha256'];assert a['label_version']==e['label_version']==t['label_version'];out.append((t,e,a,ip,templates[t['candidate_id']]))
 return out
def prepare(batch):
 es=entries(batch);v=O/'remaining_views'/batch;v.mkdir(parents=True,exist_ok=True)
 for t,e,a,ip,tmp in es:
  im=Image.open(ip).convert('RGB');cid=t['candidate_id'];im.resize((960,540),Image.Resampling.LANCZOS).save(v/(cid+'_full.jpg'),quality=93)
  n=len(a['objects']);canvas=Image.new('RGB',(960,max(1,(n+3)//4)*210),'#eeeeee');d=ImageDraw.Draw(canvas)
  for i,obj in enumerate(a['objects']):
   b=obj['bbox_xyxy'];rect=(max(0,b[0]-10),max(0,b[1]-10),min(im.width,b[2]+10),min(im.height,b[3]+10));c=im.crop(rect);s=min(4,230/c.width,170/c.height);x=i%4*240;y=i//4*210;canvas.paste(c.resize((round(c.width*s),round(c.height*s)),Image.Resampling.NEAREST),(x,y+35));d.text((x,y),obj['id']+' '+obj['type'],fill='black');d.text((x,y+17),str(b),fill='black');d.rectangle((x+(b[0]-rect[0])*s,y+35+(b[1]-rect[1])*s,x+(b[2]-rect[0])*s,y+35+(b[3]-rect[1])*s),outline='magenta',width=1)
  canvas.save(v/(cid+'_detail.jpg'),quality=95)
 for start in (0,4):
  out=Image.new('RGB',(1600,940),'white');d=ImageDraw.Draw(out)
  for i,(t,e,a,ip,tmp) in enumerate(es[start:start+4]):
   x=i%2*800;y=i//2*470;out.paste(Image.open(ip).resize((800,450),Image.Resampling.LANCZOS),(x,y+20));d.text((x+4,y+3),t['candidate_id'],fill='black')
  out.save(v/f'originals_{start//4+1}.jpg',quality=94)
 protected={str(R/t['annotation_file']):sha(R/t['annotation_file']) for t,e,a,ip,tmp in es};protected.update({str(R/t['current_manifest']):sha(R/t['current_manifest']) for t,e,a,ip,tmp in es})
 p=v/'integrity.json'
 if p.exists():assert read(p)['protected']==protected
 else:p.write_text(json.dumps({'protected':protected,'prepared_at':now()},indent=2),encoding='utf-8')
 print(json.dumps({'batch':batch,'ids':[t['candidate_id'] for t,e,a,ip,tmp in es]}))
def labels(batch):
 for t,e,a,ip,tmp in entries(batch):print(json.dumps({'id':t['candidate_id'],'objects':a['objects']},ensure_ascii=True))
def save(path):
 data=read(Path(path));batch=data['batch'];es=entries(batch);assert len(data['reviews'])==8;obs={r['candidate_id']:r for r in data['reviews']};assert set(obs)=={t['candidate_id'] for t,e,a,ip,tmp in es};v=O/'remaining_views'/batch
 p=O/(batch+'_remaining_review.jsonl');assert not p.exists();records=[]
 for t,e,a,ip,tmp in es:
  ob=obs[t['candidate_id']];assert ob['decision'] in ['accept','needs_modify','uncertain'];r=dict(tmp);r.update({'manifest_sha256':t['manifest_sha256'],'revision_manifest':t['current_manifest'],'label_version':t['label_version'],'reviewer_id':'Codex_board_independent_AI_remaining_20261025','reviewer_type':'AI','independent_from_first_pass':True,'reviewed_at':now(),'actual_method':['Independent whole-frame omission search on unmarked original displayed in 4-image panels, each 800x450; then contextual original-pixel crops nearest-neighbor up to 4x, and current JSON object review.','Small/unresolved bodies remain uncertain; no claim all subpixel/tiny lamps exhausted. Grouping based on visible landmarks, not candidate numbering.'], 'old_precheck_reused_as_formal_review':False,'full_original_checked':True,'omission_search_completed':True,'bounds_checked':True,'kind_checked':True,'attributes_checked':True,'decision':ob['decision'],'findings':ob['findings'],'grouping_review':ob['grouping_review'],'PC_arbitration_required':ob.get('PC_arbitration_required',[]),'corrected_annotation_file':None,'human_signoff':False,'training_approval':False,'decision_scope':'Independent AI draft review, not human certification/training release; unresolved ignores must not become ordinary background.','original_image_evidence':{'path':str(ip.relative_to(R)),'sha256':sha(ip)},'viewed_evidence':[{'path':str(fp.relative_to(R)),'sha256':sha(fp)} for fp in [v/f'originals_{1 if es.index((t,e,a,ip,tmp))<4 else 2}.jpg',v/(t['candidate_id']+'_detail.jpg')]]});assert r['image_sha256']==t['image_sha256'] and r['reviewed_annotation_sha256']==t['annotation_sha256'];records.append(r)
 assert all(sha(Path(f))==h for f,h in read(v/'integrity.json')['protected'].items())
 p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
 allr=[json.loads(l) for f in O.glob('batch_*_remaining_review.jsonl') for l in f.read_text(encoding='utf-8').splitlines()];assert len(allr)==len({r['candidate_id'] for r in allr});summary={'updated_at':now(),'completed_remaining':len(allr),'total_remaining':352,'decisions':dict(collections.Counter(r['decision'] for r in allr)),'files':[str(f.relative_to(R)) for f in sorted(O.glob('batch_*_remaining_review.jsonl'))],'human_signoff':False,'training_approval':False};(O/'remaining_progress.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'saved':str(p),'summary':summary},ensure_ascii=True))
if __name__=='__main__':{'prepare':prepare,'labels':labels,'save':save}[sys.argv[1]](sys.argv[2])
