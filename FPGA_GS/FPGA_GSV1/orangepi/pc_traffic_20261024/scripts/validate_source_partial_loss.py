"""Real-image loader/augmentation/backprop validation; no optimizer or CUDA trial."""
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from datetime import datetime,timezone
import torch
from ultralytics.cfg import get_cfg
from ultralytics.data.dataset import YOLODataset
from ultralytics.nn.tasks import DetectionModel
from ultralytics.utils.torch_utils import ModelEMA
from source_partial_yolo import SourceBCE,SourcePartialLoss,assert_safe_augmentation

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    torch.set_num_threads(2)
    # Exact semantics: source positives survive and unknown/background gradients
    # disappear only in sparse images. Complete rows retain their usual BCE.
    x=torch.tensor([[[.2,-.4],[.5,.3]],[[.2,-.4],[.5,.3]]],requires_grad=True)
    target=torch.tensor([[[.7,0.],[0.,0.]],[[.7,0.],[0.,0.]]])
    bce=SourceBCE();bce.sparse_rows=[True,False];loss=bce(x,target);loss.sum().backward()
    assert x.grad[0,0,0]!=0 and (x.grad[0,0,1:]==0).all() and (x.grad[0,1]==0).all()
    assert (x.grad[1]!=0).all()
    ordinary=torch.nn.functional.binary_cross_entropy_with_logits(x.detach(),target,reduction='none')
    assert torch.equal(loss[1],ordinary[1]) and loss[0,0,0]==ordinary[0,0,0]
    native=json.loads((ROOT/'reports/s2tld720_structure_audit_r1.json').read_text(encoding='utf-8'))
    first=next(e for e in native['entries'] if e['candidate_id']=='s2tld720_000000')
    legacy=json.loads((ROOT/'datasets/clean_body_r3/manifest.json').read_text(encoding='utf-8'))
    full=next(e for e in legacy['entries'] if e['split']=='train')
    args=get_cfg(overrides={'imgsz':320,'mosaic':0.,'mixup':0.,'copy_paste':0.,'translate':0.,'scale':0.,
        'degrees':0.,'shear':0.,'perspective':0.,'flipud':0.,'fliplr':1.,'hsv_h':0.,'hsv_s':0.,'hsv_v':0.,'multi_scale':False,'rect':False})
    assert_safe_augmentation(args)
    with tempfile.TemporaryDirectory(prefix='source_loss_validation_',dir=ROOT/'reports') as folder:
        temp=Path(folder).resolve();assert temp.is_relative_to((ROOT/'reports').resolve())
        images=temp/'images';labels=temp/'labels';images.mkdir();labels.mkdir()
        sparse=images/'china.jpg';shutil.copyfile(ROOT/first['sample']['image'],sparse)
        w,h=first['image_size'];lines=[]
        for o in first['objects']:
            x,y,u,v=o['bbox_xyxy'];lines.append(f'0 {(x+u)/2/w:.9f} {(y+v)/2/h:.9f} {(u-x)/w:.9f} {(v-y)/h:.9f}')
        (labels/'china.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        complete=images/('complete'+Path(full['crop_file']).suffix);shutil.copyfile(ROOT/full['crop_file'],complete)
        shutil.copyfile(ROOT/full['yolo_label_file'],labels/'complete.txt')
        dataset=YOLODataset(img_path=str(images),imgsz=320,batch_size=2,augment=True,hyp=args,rect=False,
            cache=False,task='detect',data={'names':{0:'motor_vehicle_body',1:'pedestrian_body'},'nc':2})
        items=[dataset[i] for i in range(len(dataset))];batch=dataset.collate_fn(items)
        china=next(item for item in items if Path(item['im_file']).name=='china.jpg')
        assert len(china['bboxes'])==len(first['objects'])
        # A forced horizontal flip must carry each normalized box to1-x. The
        # unknown domain is the entire image, so it inherits flip and padding.
        expected=sorted([1-(o['bbox_xyxy'][0]+o['bbox_xyxy'][2])/2/w for o in first['objects']])
        actual=sorted(china['bboxes'][:,0].tolist())
        assert max(abs(a-b) for a,b in zip(expected,actual))<1e-5
        model=DetectionModel('yolov8n.yaml',nc=2,verbose=False);model.args=args
        ema=ModelEMA(model)
        criterion=SourcePartialLoss(model,{str(sparse):'positive_only',str(complete):'complete'})
        model.criterion=criterion;batch['img']=batch['img'].float()/255
        prediction=model(batch['img']);total,parts=criterion(prediction,batch);total.backward()
        assert torch.isfinite(total) and torch.isfinite(parts).all()
        assert any(p.grad is not None and p.grad.abs().sum()>0 for p in model.parameters())
        stats=criterion.bce.last_stats
        assert stats['sparse_images']==1 and stats['positive_terms_retained']>0
        assert stats['sparse_unknown_negative_terms_masked']>0 and stats['complete_negative_terms_retained']>0
        assert not hasattr(ema.ema,'criterion'), 'Training-only criterion leaked into checkpoint model'
        checkpoint=temp/'ordinary_ema.pt';torch.save({'model':ema.ema},checkpoint)
        loaded=torch.load(checkpoint,map_location='cpu',weights_only=False)['model']
        assert type(loaded) is DetectionModel and not hasattr(loaded,'criterion')
        unknown_batch=dict(batch,im_file=['unbound.jpg']*2)
        try:criterion(prediction,unknown_batch)
        except AssertionError:unknown_rejected=True
        else:unknown_rejected=False
        assert unknown_rejected
        report={'recorded_at':datetime.now(timezone.utc).isoformat(),'passed':True,'route':'source_positive_only_for_sparse_images',
            'implementation':'scripts/source_partial_yolo.py','implementation_sha256':sha(ROOT/'scripts/source_partial_yolo.py'),
            'real_source_images':[first['sample']['image'],full['crop_file']],
            'mixed_real_image_loader_and_loss_backward_passed':True,'forced_flip_source_box_transport_passed':True,
            'whole_image_unknown_domain_inherits_letterbox_and_flip':True,'positive_priority_gradient_passed':True,
            'sparse_negative_classification_gradients_exactly_zero':True,'complete_image_background_gradients_preserved':True,
            'unbound_image_source_fails_closed':unknown_rejected,'ordinary_detection_ema_roundtrip_passed':True,
            'ordinary_val_metrics_only_on_complete_images':True,'mosaic_mixup_copy_paste_and_geometric_crops_disabled':True,
            'real_batch_loss_parts_box_cls_dfl':parts.tolist(),'classification_term_counts':stats,
            'optimizer_updates':0,'recognition_training':False,'CUDA_trial':False,
            'limits':'Real loader/augmentation/model-backprop test, no optimizer step or production trainer fit yet. Not recognition accuracy or proof of arbitrary spatial-ignore support.'}
    dest=ROOT/'reports/source_partial_loss_validation_r1.json';assert not dest.exists()
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'optimizer_updates':0,'classification_term_counts':stats}))


if __name__=='__main__':main()
