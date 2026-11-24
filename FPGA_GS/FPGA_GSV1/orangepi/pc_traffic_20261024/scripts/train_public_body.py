"""First authorized source-supervised fit, with persistent real progress."""
import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
import torch
from ultralytics import YOLO
from ultralytics.nn.tasks import DetectionModel
from source_partial_yolo import SourcePartialTrainer, SourcePartialLoss
from check_public_training_readiness import ROOT, RELEASE, validate, sha

RUN = ROOT/'runs/public_body_r1_yolov8n_960_e60'
PROGRESS = ROOT/'reports/public_training_progress_r1.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def write_state(state):
    state['updated_at'] = now()
    temporary = PROGRESS.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temporary,PROGRESS)


class LoggedTrainer(SourcePartialTrainer):
    def optimizer_step(self):
        super().optimizer_step()
        self.real_optimizer_updates = getattr(self,'real_optimizer_updates',0)+1


def main():
    assert not RUN.exists(), 'Run exists: inspect and resume deliberately; never duplicate/overwrite'
    ready = validate()
    (ROOT/'reports/public_training_readiness_r1.json').write_text(json.dumps(ready,ensure_ascii=False,indent=2),encoding='utf-8')
    RUN.mkdir(parents=True)
    lock = RUN/'launch.json'
    lock.write_text(json.dumps({'pid':os.getpid(),'started_at':now(),'readiness':ready},indent=2),encoding='utf-8')
    state = {'status':'starting','started_at':now(),'pid':os.getpid(),'run':RUN.relative_to(ROOT).as_posix(),
        'release':RELEASE,'release_sha256':sha(RELEASE),'optimizer_updates':0,'completed_epochs':0,
        'model_task':'two-class motor/pedestrian signal body detection; no color/arrow state truth',
        'production_train_val_save_verified':False,'final_test_used':False,'deployment_updated':False,
        'limits':ready['coverage_limits']}
    write_state(state)
    model = YOLO(str(ROOT/'artifacts/yolov8n_coco_official.pt'))
    LoggedTrainer.release_path = ROOT/RELEASE
    last_write = [0.]

    def progress(t):
        if time.monotonic()-last_write[0] < 20:
            return
        last_write[0] = time.monotonic()
        state.update(status='training',current_epoch=t.epoch+1,optimizer_updates=getattr(t,'real_optimizer_updates',0),
            train_loss_parts=[float(x) for x in t.tloss.detach().cpu()] if t.tloss is not None else None,
            gpu_allocated_bytes=torch.cuda.memory_allocated())
        write_state(state)

    def saved(t):
        assert type(t.ema.ema) is DetectionModel
        assert not isinstance(getattr(t.ema.ema,'criterion',None),SourcePartialLoss)
        assert isinstance(t.model.criterion,SourcePartialLoss)
        assert t.last.exists()
        if not state['production_train_val_save_verified']:
            checkpoint = torch.load(t.last,map_location='cpu',weights_only=False)
            assert type(checkpoint['ema']) is DetectionModel
            assert not isinstance(getattr(checkpoint['ema'],'criterion',None),SourcePartialLoss)
            del checkpoint
        state.update(status='training',completed_epochs=t.epoch+1,
            optimizer_updates=getattr(t,'real_optimizer_updates',0),production_train_val_save_verified=True,
            latest_checkpoint=t.last.relative_to(ROOT).as_posix(),
            val_metrics={str(k):float(v) for k,v in t.metrics.items()},
            latest_classification_mask_stats=t.model.criterion.bce.last_stats)
        write_state(state)

    model.add_callback('on_train_batch_end',progress)
    model.add_callback('on_model_save',saved)
    try:
        manifest = json.loads((ROOT/RELEASE).read_text(encoding='utf-8'))
        model.train(trainer=LoggedTrainer,data=str(ROOT/manifest['yaml']),
            project=str(RUN.parent),name=RUN.name,exist_ok=True,
            epochs=60,patience=0,imgsz=960,batch=4,nbs=16,device=0,workers=0,
            amp=False,optimizer='AdamW',lr0=.001,lrf=.01,weight_decay=.0005,
            warmup_epochs=3.,warmup_bias_lr=.001,cos_lr=True,seed=20261025,
            save=True,save_period=10,cache=False,plots=False,val=True,
            close_mosaic=0,**manifest['augmentation'])
        state.update(status='completed',completed_at=now(),
            best_checkpoint=(RUN/'weights/best.pt').relative_to(ROOT).as_posix(),
            next_required='Inspect held-out validation errors; export new classification logits and validate new weights on board candidate only.')
        write_state(state)
    except BaseException as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
        write_state(state)
        raise


if __name__ == '__main__':
    main()
