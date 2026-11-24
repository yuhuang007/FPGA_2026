"""One YOLO pipeline: sparse source images supply positives, not background truth.

Unknown areas cover the entire sparse image. Assigned positive class targets take
priority; other classification terms are zero. Standard TAL, box/DFL regression,
fully supervised images and inference stay unchanged. No spatial pseudo-labels.
"""
import json
from pathlib import Path
import torch
from torch import nn
from ultralytics.utils.loss import v8DetectionLoss
from ultralytics.models.yolo.detect.train import DetectionTrainer


def canonical(path):
    return str(Path(path).resolve()).replace('\\','/').casefold()


class SourceBCE(nn.Module):
    def __init__(self):
        super().__init__()
        self.sparse_rows=None
        self.last_stats={}

    def forward(self, logits, targets):
        assert self.sparse_rows is not None
        assert logits.shape==targets.shape and logits.ndim==3
        assert len(self.sparse_rows)==len(logits)
        sparse=torch.as_tensor(self.sparse_rows,device=logits.device,dtype=torch.bool)[:,None,None]
        # Whole sparse image is unknown, with reviewed/source positives first.
        keep=(~sparse)|(targets>0)
        loss=nn.functional.binary_cross_entropy_with_logits(logits,targets,reduction='none')
        self.last_stats={'sparse_images':int(sparse.sum()),'positive_terms_retained':int(((targets>0)&keep).sum()),
            'sparse_unknown_negative_terms_masked':int((sparse&(targets==0)).sum()),
            'complete_negative_terms_retained':int(((~sparse)&(targets==0)).sum())}
        return loss*keep.to(loss.dtype)


class SourcePartialLoss(v8DetectionLoss):
    def __init__(self,model,policies):
        super().__init__(model)
        self.policies={canonical(p):v for p,v in policies.items()}
        assert set(self.policies.values())<={'positive_only','complete'}
        self.bce=SourceBCE()

    def __call__(self,preds,batch):
        paths=batch.get('im_file')
        assert paths is not None and len(paths)==len(batch['img']), 'Source policy lost from batch'
        assert all(canonical(p) in self.policies for p in paths), 'Unbound source image'
        self.bce.sparse_rows=[self.policies[canonical(p)]=='positive_only' for p in paths]
        return super().__call__(preds,batch)


def assert_safe_augmentation(args):
    # No mixed-image transform may silently combine supervision policies. With
    # these settings flip/HSV/letterbox inherit the whole-image unknown mask.
    for key in ('mosaic','mixup','copy_paste','degrees','translate','scale','shear','perspective','flipud'):
        assert float(getattr(args,key,0))==0, 'Unsupported source-policy transform: '+key
    assert not getattr(args,'multi_scale',False)
    assert not getattr(args,'rect',False), 'Training must shuffle complete and sparse sources'


class SourcePartialTrainer(DetectionTrainer):
    release_path=None

    def __init__(self,*args,**kwargs):
        assert self.release_path is not None
        self.release=json.loads(Path(self.release_path).read_text(encoding='utf-8'))
        self.source_policies={canonical(e['image_absolute']):e['supervision'] for e in self.release['entries']}
        self.split_by_file={canonical(e['image_absolute']):e['split'] for e in self.release['entries']}
        super().__init__(*args,**kwargs)
        assert_safe_augmentation(self.args)
        assert self.args.device not in ('cpu',)  # production fine-tuning uses the already verified GPU
        self.add_callback('on_train_start',self.install_source_loss)

    def build_dataset(self,img_path,mode='train',batch=None):
        dataset=super().build_dataset(img_path,mode,batch)
        for p in dataset.im_files:
            key=canonical(p)
            assert key in self.source_policies, 'Image absent from frozen source release'
            assert self.split_by_file[key]==mode
            if mode!='train':assert self.source_policies[key]=='complete', 'Sparse source cannot yield ordinary val mAP'
        return dataset

    def install_source_loss(self,trainer):
        assert trainer is self and self.ema is not None
        assert not hasattr(self.ema.ema,'criterion'), 'EMA must precede training-only criterion'
        self.model.criterion=SourcePartialLoss(self.model,self.source_policies)
        # EMA/checkpoint stays an ordinary DetectionModel. A validator-created
        # standard criterion is safe because every val image is complete.


def validate_release_entries(entries):
    assert entries and {e['split'] for e in entries}>={'train','val'}
    for field in ('candidate_id','canonical_original_id','image_sha256','image_absolute'):
        vals=[e[field] for e in entries]
        assert len(vals)==len(set(vals)), 'Duplicate original or image: '+field
    groups={}
    for e in entries:
        assert e['supervision'] in ('positive_only','complete')
        assert e['split'] in ('train','val','holdout')
        assert e['split']=='train' or e['supervision']=='complete'
        groups.setdefault(e['leakage_group'],set()).add(e['split'])
    assert all(len(v)==1 for v in groups.values()), 'Cross-split leakage group'
    assert sum(e['split'] in ('train','val') for e in entries)>=300
