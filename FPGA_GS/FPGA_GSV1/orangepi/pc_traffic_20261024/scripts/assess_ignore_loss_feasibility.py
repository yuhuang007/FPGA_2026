"""Bounded CPU loss-semantics assessment, not a second training pipeline."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,csv,statistics
import torch

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    capacity=R/'reports/clean_crop_capacity_original400.json';cap=read(capacity)
    rows=list(csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig')))
    byid={e['candidate_id']:e for e in cap['entries']};total={};retained={};stale=[]
    for row in rows:
        p=R/row['annotation_file'];a=read(p);e=byid[row['sample_id']]
        if sha(p)!=e['annotation_sha256']:stale.append(row['sample_id'])
        selected=set(e['retained_declared_body_ids'])
        for o in a['objects']:
            if o['type']!='body':continue
            k=o['kind'];total[k]=total.get(k,0)+1
            if o['id'] in selected:retained[k]=retained.get(k,0)+1
    # This proves only the stated gradient rule, not loader/augmentation/model
    # or validation support. No optimizer, CUDA run or training is performed.
    scores=torch.zeros((1,4,2),requires_grad=True)
    target=torch.zeros_like(scores);target[0,1,0]=1
    fg=torch.tensor([[False,True,False,False]])
    inside=torch.tensor([[True,True,False,False]])
    valid=fg|~inside
    bce=torch.nn.functional.binary_cross_entropy_with_logits(scores,target,reduction='none')
    loss=(bce*valid.unsqueeze(-1)).sum()/target.sum().clamp_min(1)
    loss.backward();g=scores.grad
    probe={'ignored_background_zero_all_class_gradients':bool((g[0,0]==0).all()),
        'positive_inside_ignore_preserved':bool(g[0,1,0]<0 and g[0,1,1]>0),
        'outside_ignore_background_preserved':bool((g[0,2:]>0).all()),
        'finite_loss_and_gradients':bool(torch.isfinite(loss) and torch.isfinite(g).all()),
        'optimizer_updates':0,'device':'CPU','training_pipeline_validated':False}
    assert all(probe[k] for k in list(probe)[:4])
    lib=R/'.venv-train/Lib/site-packages/ultralytics'
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),
        'assessment_scope':'Installed Ultralytics8.3.40 source inspection and isolated CPU BCE gradient semantics; NOT installed custom ignore support or a second runnable training route.',
        'capacity_evidence':{'path':capacity.relative_to(R).as_posix(),'sha256':sha(capacity),
            'source_snapshot_is_current':not stale,'labels_changed_since_geometry_scan':stale},
        'draft_geometry_capacity':{k:cap[k] for k in ['originals_scanned','declared_body_positive_originals','proposed_originals','proposed_body_count','declared_body_count','current_pipeline_original_proposal_shortfall_to_300','proposed_area_retained']},
        'draft_class_bias':{k:{'declared':v,'retained_by_snapshot_proposal':retained.get(k,0),
            'lost_fraction':1-retained.get(k,0)/v} for k,v in total.items()},
        'large_loss_condition_triggered':True,
        'source_inspection':[{'path':(lib/p).relative_to(R).as_posix(),'sha256':sha(lib/p),'observation':note}
            for p,note in [('utils/loss.py','v8DetectionLoss assigns positives with TAL then applies BCE over every anchor/class, no ignore mask. Deleting ignore labels trains unknown targets as negatives.'),
                ('data/augment.py','Format consumes cls and Instances; native arbitrary ignore coordinates are not propagated by a sidecar file through letterbox, flip, affine, mosaic and collate.'),
                ('models/yolo/detect/val.py','Detector validator matches known GT then includes all remaining predictions in precision/confusion matrices; no uncertain-region neutralization.')]],
        'isolated_gradient_probe':probe,
        'requirements_if_ever_switching':{
            'positive_priority':'Run ordinary TAL assignment on confirmed bodies; never feed ignore boxes as a class/positive. valid_anchor = fg_mask OR NOT in_transformed_ignore. Keep every assigned positive and its original all-class BCE, bbox and DFL even when overlapping ignore.',
            'background_policy':'Suppress all class BCE only for unassigned anchor centers inside padded source-ignore regions, source-truncated/unsupported bodies and unparented uncertain emitters. Center policy does not promise suppression for centers outside the region and requires real leak/false-negative analysis.',
            'normalization':'Retain normal max(target_scores.sum(),1) positive normalization; zero retained background must be finite. Do not scale down true positives based on ignore area.',
            'augmentation_coordinates':'Carry pixel xyxy regions with per-image IDs through exact same resize, letterbox padding, horizontal flip and batch collate as pixels. Disable mosaic/mixup/copy_paste/affine/perspective initially. Any future geometry needs joint clipping plus explicit treatment of newly truncated known bodies; silent box filtering would make false background.',
            'validation_rules':'Match predictions to known GT first at every evaluated IoU threshold; any matched known positive stays TP. For remaining unmatched predictions, a preregistered ignore-overlap rule (e.g. intersection/predicted_area >=0.5) makes them neutral, never TP. Known GT denominator remains unchanged. Apply same rule to AP, precision/recall and confusion matrices, and report neutralized detections/area separately. Threshold sensitivity and unmatched duplicate predictions require audit.',
            'required_evidence':'End-to-end actual-source dataset/augmentation/batch coordinate tests; gradient tests with actual TAL positives; actual forward/backward; exact no-ignore equivalence; positive-over-ignore priority; transformed-edge and mixed-batch cases; ignore metric TP/FP/FN tests; independent real-image QA. An export-file change or this algebra probe is insufficient.'},
        'decision':'Keep the actually validated context-preserving clean-crop standard-YOLO route for this first round. Do not enable or maintain a custom-loss training entry on the strength of a small algebra probe. Address the measured original-count and pedestrian/context shortfall by separately reviewed clean originals; re-evaluate feasibility if those cannot supply a credible dataset.',
        'selected_route':'context_preserving_clean_crops_standard_YOLO','custom_ignore_pipeline_implemented':False,
        'full_image_ignore_supported':False,'cropped_metrics_are_not_full_frame_metrics':True,
        'model_reliability_or_training_success_claimed':False,'training_started':False}
    out=R/'reports/ignore_loss_feasibility_r1.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'large_loss_assessed':True,'classes':report['draft_class_bias'],'isolated_gradient_probe':probe,'custom_training_pipeline_created':False,'selected_route':report['selected_route']}))

if __name__=='__main__':main()
