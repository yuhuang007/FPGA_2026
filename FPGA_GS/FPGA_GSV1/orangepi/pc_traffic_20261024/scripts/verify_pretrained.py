"""Verify locally downloaded official pretrained checkpoint; never starts training."""
from pathlib import Path
import hashlib,json,time,torch
from ultralytics import YOLO
R=Path(__file__).resolve().parents[1]; p=R/'artifacts/yolov8n_coco_official.pt'
m=YOLO(str(p)); ckpt=m.ckpt
r={'status':'downloaded_and_loaded_not_finetuned','download_url':
 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt',
 'local_path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,
 'verified_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'origin':'official ultralytics/assets GitHub release v8.3.0',
 'upstream_signature_verified':False,'scope':'traceable official URL plus local digest; no upstream signing assertion',
 'torch_version':torch.__version__,'model_type':type(m.model).__name__,'task':m.task,
 'classes':m.names,'class_count':len(m.names),'parameters':sum(x.numel() for x in m.model.parameters()),
 'checkpoint_version':ckpt.get('version'),'checkpoint_date':ckpt.get('date'),
 'checkpoint_train_args':ckpt.get('train_args'),
 'not_the_UNTRAINED_preflight':True,'target_class_order':['motor_vehicle_body','pedestrian_body'],
 'target_head_policy':'new nc=2 head; pretrained compatible backbone/neck transferred by Ultralytics train',
 'fine_tuning_started':False}
assert r['class_count']==80 and m.names[9]=='traffic light' and r['task']=='detect'
(R/'reports/pretrained_provenance.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps({k:v for k,v in r.items() if k not in ('classes','checkpoint_train_args')},ensure_ascii=False,indent=2))
