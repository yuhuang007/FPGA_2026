"""Measure the fixed deployment resolution on the existing complete val only."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import torch
from ultralytics import YOLO

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    progress=json.loads((ROOT/'reports/public_training_progress_r1.json').read_text('utf-8'))
    assert progress['status']=='completed'
    checkpoint=ROOT/progress['best_checkpoint'];before=sha(checkpoint)
    export=json.loads((ROOT/'reports/trained_logits_export_r1.json').read_text('utf-8'))
    assert before==export['checkpoint_sha256']
    release=ROOT/progress['release'];assert sha(release)==progress['release_sha256']
    m=json.loads(release.read_text('utf-8'))
    val=[e for e in m['entries'] if e['split']=='val']
    assert len(val)==5 and all(e['supervision']=='complete' for e in val)
    assert not (ROOT/'runs/public_body_r1_best_val640_r1').exists()
    model=YOLO(str(checkpoint))
    metrics=model.val(data=str(ROOT/m['yaml']),imgsz=640,device=0,batch=4,workers=0,
        plots=False,save_txt=True,save_conf=True,project=str(ROOT/'runs'),
        name='public_body_r1_best_val640_r1',exist_ok=False,verbose=True)
    rows=list(csv.DictReader((ROOT/progress['run']/'results.csv').open()))
    best=max(rows,key=lambda r:.1*float(r['metrics/mAP50(B)'])+.9*float(r['metrics/mAP50-95(B)']))
    original=torch.load(checkpoint,map_location='cpu',weights_only=False)['train_metrics']
    per_class=[]
    for i,cls in enumerate(metrics.box.ap_class_index):
        per_class.append({'class_id':int(cls),'name':model.names[int(cls)],
            'precision':float(metrics.box.p[i]),'recall':float(metrics.box.r[i]),
            'mAP50':float(metrics.box.ap50[i]),'mAP50_95':float(metrics.box.ap[i])})
    assert sha(checkpoint)==before
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'training_completed':True,
        'epochs':60,'optimizer_updates':progress['optimizer_updates'],'best_epoch_by_predefined_fitness':int(best['epoch']),
        'best_checkpoint':progress['best_checkpoint'],'best_checkpoint_sha256':before,
        'checkpoint_not_modified':True,'best_validation_960':original,
        'deployment_resolution_validation_640':{str(k):float(v) for k,v in metrics.results_dict.items()},
        'deployment_resolution_per_class':per_class,'val_originals':5,'val_bodies':8,
        'val_motor_bodies':7,'val_pedestrian_bodies':1,'holdout_used':False,
        'China_reserved_candidates_used':False,'independent_test_adequate':False,
        'operating_threshold_selected_by_this_script':False,
        'recognition_ready_for_production':False,
        'limits':['Five highly selected clean crops and one pedestrian body are insufficient for precision/generalization claims.',
            'Best fitness occurs early; last60epoch checkpoint has lower validation performance despite lower training loss.',
            'Training960 and deployment640 accuracy are measured separately; numeric ONNX agreement does not imply equal recall.',
            'Broader independent China/road-view validation and representative final test remain required.']}
    (ROOT/'reports/public_training_result_r1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'best_epoch':report['best_epoch_by_predefined_fitness'],
        'val640':report['deployment_resolution_validation_640'],'production_ready':False},ensure_ascii=False))


if __name__=='__main__':main()
