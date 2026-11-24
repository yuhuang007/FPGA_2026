"""Real two-class detector GPU optimizer smoke; synthetic data is NOT training evidence."""
import json, time, traceback, platform, subprocess, statistics
from pathlib import Path
from types import SimpleNamespace

R = Path(__file__).resolve().parents[1]

def main():
    report = {'passed': False, 'purpose': 'synthetic environment validation only',
              'recognition_training': False, 'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
              'steps': [], 'class_order': ['motor_vehicle_body', 'pedestrian_body']}
    try:
        import torch, torchvision, ultralytics
        from ultralytics.nn.tasks import DetectionModel
        from ultralytics.cfg import DEFAULT_CFG_DICT
        assert torch.cuda.is_available(), 'CUDA unavailable'
        torch.manual_seed(20261024)
        torch.set_num_threads(4)
        report['versions'] = {'python': platform.python_version(), 'torch': torch.__version__,
            'torchvision': torchvision.__version__, 'ultralytics': ultralytics.__version__,
            'cuda_runtime': torch.version.cuda, 'cudnn': torch.backends.cudnn.version(),
            'driver_query': subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'], text=True).strip()}
        report['gpu'] = torch.cuda.get_device_name(0)
        report['compute_capability'] = list(torch.cuda.get_device_capability(0))
        model = DetectionModel('yolov8n.yaml', ch=3, nc=2, verbose=False).cuda().train()
        model.args = SimpleNamespace(**DEFAULT_CFG_DICT)
        optimizer = torch.optim.SGD(model.parameters(), lr=0.001, momentum=0.9)
        scaler = torch.amp.GradScaler('cuda', init_scale=128.0)
        initial = next(model.parameters()).detach().clone()
        report.update({'model': 'YOLOv8n nc=2 random initialization (smoke only)', 'input_hw': [640,640], 'batch':4,
            'amp_requested': True, 'amp_enabled': scaler.is_enabled(), 'optimizer': 'SGD lr=.001 momentum=.9',
            'synthetic_gt_classes': [0,1], 'weights_saved': False})
        torch.cuda.reset_peak_memory_stats()
        attempts=0
        while len([s for s in report['steps'] if s['optimizer_step_applied']]) < 12 and attempts < 24:
            attempts += 1
            batch={'img':torch.rand(4,3,640,640,device='cuda'),
                'batch_idx':torch.arange(4,device='cuda').repeat_interleave(2),
                'cls':torch.tensor([[0],[1]]*4,device='cuda',dtype=torch.float32),
                'bboxes':torch.tensor([[.3,.35,.1,.15],[.7,.4,.06,.12]]*4,device='cuda')}
            optimizer.zero_grad(set_to_none=True)
            torch.cuda.synchronize(); start=time.perf_counter()
            with torch.autocast('cuda', dtype=torch.float16):
                preds=model(batch['img'])
                pred_dtype=str(preds[0].dtype)
                loss, parts=model.loss(batch,preds)
            assert torch.isfinite(loss).all(), 'nonfinite loss'
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            finite=all(torch.isfinite(p.grad).all().item() for p in model.parameters() if p.grad is not None)
            assert finite, 'nonfinite gradients'
            torch.nn.utils.clip_grad_norm_(model.parameters(),10.0)
            before=next(model.parameters()).detach().clone()
            old_scale=scaler.get_scale()
            scaler.step(optimizer); scaler.update()
            torch.cuda.synchronize(); elapsed=time.perf_counter()-start
            changed=not torch.equal(before,next(model.parameters()).detach())
            rec={'attempt':attempts,'loss':float(loss.detach()),'loss_parts_box_cls_dfl':[float(x) for x in parts],
                'elapsed_s':elapsed,'forward_dtype':pred_dtype,'finite_gradients':finite,
                'scale_before':old_scale,'scale_after':scaler.get_scale(),
                'optimizer_step_applied':changed and scaler.get_scale()>=old_scale}
            report['steps'].append(rec)
            print(json.dumps(rec),flush=True)
        report['completed_optimizer_steps']=sum(s['optimizer_step_applied'] for s in report['steps'])
        report['parameter_update_l1']=float((next(model.parameters()).detach()-initial).abs().sum())
        report['peak_allocated_mib']=torch.cuda.max_memory_allocated()/2**20
        report['peak_reserved_mib']=torch.cuda.max_memory_reserved()/2**20
        times=[s['elapsed_s'] for s in report['steps']]
        report['step_time_s']={'first':times[0], 'median_excluding_first2':statistics.median(times[2:]), 'min':min(times),'max':max(times)}
        report['passed']=(report['completed_optimizer_steps']>=10 and report['amp_enabled'] and
                          all(s['forward_dtype']=='torch.float16' for s in report['steps']) and report['parameter_update_l1']>0)
    except Exception:
        report['error']=traceback.format_exc(); print(report['error'],flush=True)
    finally:
        report['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S%z')
        (R/'reports/pytorch_cuda_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='steps'},indent=2),flush=True)
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())
