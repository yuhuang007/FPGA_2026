"""Fixed SC development clips, real best.pt inference; no training/export/board I/O."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from ultralytics.utils.ops import non_max_suppression

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/sc_video_eval_r1'
FONT = 'C:/Windows/Fonts/msyh.ttc'
NAMES = ['机动车灯体', '行人灯体']
COLORS = ['#54ef88', '#5ed8ff']


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


class Detector:
    def __init__(self, path, baseline=False):
        self.path = Path(path)
        self.sha256 = sha(path)
        self.baseline = baseline
        ck = torch.load(path, map_location='cpu', weights_only=False)
        self.model = (ck.get('ema') or ck['model']).float().eval().to('cuda:0')
        self.names = self.model.names
        if not baseline:
            assert self.names == {0: 'motor_vehicle_body', 1: 'pedestrian_body'}
        else:
            assert self.names[9] == 'traffic light'
        self.model.fuse(verbose=False)

    @torch.inference_mode()
    def infer(self, image, size=640):
        start = time.perf_counter()
        h, w = image.shape[:2]
        gain = min(size / w, size / h)
        nw, nh = round(w * gain), round(h * gain)
        left, top = (size - nw) // 2, (size - nh) // 2
        a = np.full((size, size, 3), 114, np.uint8)
        a[top:top+nh, left:left+nw] = cv2.resize(image, (nw, nh))
        a = np.ascontiguousarray(a[:, :, ::-1].transpose(2, 0, 1)[None])
        x = torch.from_numpy(a).to('cuda:0', dtype=torch.float32) / 255
        torch.cuda.synchronize()
        prepared = time.perf_counter()
        result = self.model(x)
        torch.cuda.synchronize()
        forwarded = time.perf_counter()
        pred = result[0] if isinstance(result, tuple) else result
        ds = non_max_suppression(pred, conf_thres=.25, iou_thres=.45,
                                 classes=[9] if self.baseline else None,
                                 agnostic=False, max_det=300)[0].detach().cpu().numpy()
        if len(ds):
            ds[:, [0, 2]] = (ds[:, [0, 2]] - left) / gain
            ds[:, [1, 3]] = (ds[:, [1, 3]] - top) / gain
            ds[:, [0, 2]] = ds[:, [0, 2]].clip(0, w)
            ds[:, [1, 3]] = ds[:, [1, 3]].clip(0, h)
        end = time.perf_counter()
        boxes = [{'box': [round(float(v), 3) for v in d[:4]],
                  'confidence': float(d[4]), 'class_id': int(d[5])} for d in ds]
        return boxes, {'preprocess_H2D_ms': (prepared-start)*1000,
                       'forward_ms': (forwarded-prepared)*1000,
                       'NMS_D2H_ms': (end-forwarded)*1000}


def draw(image, boxes, title, source_time, baseline=False, width=1280, input_size=640):
    h, w = image.shape[:2]
    height = round(h * width / w)
    frame = Image.new('RGB', (width, height+88), '#111b2b')
    frame.paste(Image.fromarray(cv2.cvtColor(cv2.resize(image, (width, height)), cv2.COLOR_BGR2RGB)), (0, 88))
    dr = ImageDraw.Draw(frame)
    font = ImageFont.truetype(FONT, 19)
    small = ImageFont.truetype(FONT, 16)
    dr.text((14, 7), f'{title}   源时间 {source_time:07.3f}s   输入{input_size} / conf≥0.25 / IoU0.45', font=font, fill='white')
    dr.text((14, 39), '仅灯体检测；框与颜色不代表灯色、箭头或控制方向。AI开发评估，非正式测试。', font=small, fill='#ffdc8b')
    for i, d in enumerate(boxes):
        b = [v*width/w for v in d['box']]
        b[1] += 88
        b[3] += 88
        color = '#ffc46b' if baseline else COLORS[d['class_id']]
        dr.rectangle(b, outline=color, width=2)
        name = 'COCO灯体候选' if baseline else NAMES[d['class_id']]
        label = f'{i+1} {name} {d["confidence"]:.2f}'
        x, y = b[0], max(88, b[1]-23)
        text_box = dr.textbbox((x, y), label, font=small)
        dr.rectangle(text_box, fill='#101923')
        dr.text((x, y), label, font=small, fill=color)
    return cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)


def stats(values):
    return {k: float(v) for k, v in zip(['mean', 'p50', 'p95'], [np.mean(values), np.median(values), np.percentile(values, 95)])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['frames', 'clips', 'frames960'])
    args = ap.parse_args()
    torch.set_num_threads(4)
    cv2.setNumThreads(2)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    m = read(OUT/'selection_manifest.json')
    assert sha(ROOT/m['weight']) == m['weight_sha256']
    detector = Detector(ROOT/m['weight'])
    baseline_path = ROOT.parent/'m406/research/yolov8s.pt'
    baseline = Detector(baseline_path, True) if args.mode != 'frames960' and baseline_path.exists() else None
    # Warm up on the existing first development image only. No environment test.
    warm = cv2.imread(str(ROOT/m['entries'][0]['sample_frames'][0]['raw']))
    for _ in range(5):
        detector.infer(warm, 960 if args.mode == 'frames960' else 640)
        if baseline:
            baseline.infer(warm)
    if args.mode.startswith('frames'):
        size = 960 if args.mode == 'frames960' else 640
        rows = []
        for entry in m['entries']:
            for sample in entry['sample_frames']:
                p = ROOT/sample['raw']
                im = cv2.imread(str(p))
                boxes, timing = detector.infer(im, size)
                row = {'video': entry['name'], **sample, 'input': size, 'detections': boxes, 'timing': timing}
                if size == 640:
                    view = draw(im, boxes, '首轮最佳权重', sample['decoded_pts_seconds'])
                    vp = OUT/'frames'/p.name.replace('_raw.png', '_best640.jpg')
                    cv2.imwrite(str(vp), view, [cv2.IMWRITE_JPEG_QUALITY, 94])
                    row['rendered'] = vp.relative_to(ROOT).as_posix()
                    if baseline:
                        bs, bt = baseline.infer(im)
                        row['baseline'] = {'detections': bs, 'timing': bt}
                        vp = OUT/'frames'/p.name.replace('_raw.png', '_baseline640.jpg')
                        cv2.imwrite(str(vp), draw(im, bs, 'm406来源COCO权重 / 同全图PC对照', sample['decoded_pts_seconds'], True))
                        row['baseline']['rendered'] = vp.relative_to(ROOT).as_posix()
                rows.append(row)
                print(json.dumps({'frame': p.stem, 'size': size, 'best_boxes': len(boxes),
                                  'baseline_boxes': len(row.get('baseline', {}).get('detections', []))}), flush=True)
        report = {'weight_sha256': detector.sha256, 'model_names': detector.names, 'input': size,
                  'conf': .25, 'iou': .45, 'rows': rows,
                  'score_activation': 'Native PyTorch Detect performs sigmoid once; no second sigmoid',
                  'no_train_no_export_no_holdout': True}
        if baseline:
            report['baseline'] = {'path': str(baseline.path), 'sha256': baseline.sha256,
                                  'scope': 'm406 source COCO weight, class9, same full-frame640 PC. Not m406 alternating half-crop geometry/color/tracker/service.'}
        save(OUT/f'frame_predictions_{size}.json', report)
    else:
        videos = OUT/'videos'
        videos.mkdir(exist_ok=True)
        encoder = read(OUT/'encoder.json')
        rows = []
        for entry in m['entries']:
            for is_base, model in [(False, detector), (True, baseline)]:
                if model is None:
                    continue
                stem = Path(entry['name']).stem
                tag = 'baseline640' if is_base else 'best640'
                path = videos/f'{stem}_{tag}.mp4'
                assert not path.exists(), 'Do not overwrite completed videos'
                cap = cv2.VideoCapture(entry['path'])
                cap.set(cv2.CAP_PROP_POS_MSEC, entry['start_seconds']*1000)
                height = round(entry['height']*1280/entry['width'])
                # H.264 requires even frame dimensions; one neutral bottom row if needed.
                height = (height+88+1)//2*2
                writer = cv2.VideoWriter(str(path), encoder['api'], cv2.VideoWriter_fourcc(*encoder['codec']), 30, (1280, height))
                assert writer.isOpened()
                timings = []
                records = []
                wall_start = time.perf_counter()
                for i in range(300):
                    frame_start = time.perf_counter()
                    target = entry['start_seconds']+i/30
                    while True:
                        ok, image = cap.read()
                        assert ok
                        pts = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
                        if pts >= target-1e-6:
                            break
                    decoded = time.perf_counter()
                    ds, tm = model.infer(image)
                    rendered = draw(image, ds, 'm406来源COCO权重 / PC全图参考' if is_base else '首轮最佳权重 / 机动车灯体·行人灯体', pts, is_base)
                    if rendered.shape[0] < height:
                        rendered = cv2.copyMakeBorder(rendered, 0, height-rendered.shape[0], 0, 0, cv2.BORDER_CONSTANT)
                    drawn = time.perf_counter()
                    writer.write(rendered)
                    written = time.perf_counter()
                    tm.update(decode_ms=(decoded-frame_start)*1000,
                              decode_infer_draw_ms=(drawn-frame_start)*1000,
                              with_encoder_submit_ms=(written-frame_start)*1000)
                    timings.append(tm)
                    records.append({'output_frame': i, 'source_pts': pts, 'detections': ds})
                writer.release()
                cap.release()
                wall = time.perf_counter()-wall_start
                rp = videos/f'{stem}_{tag}_predictions.jsonl'
                with rp.open('w', encoding='utf-8') as f:
                    for r in records:
                        f.write(json.dumps(r, ensure_ascii=False)+'\n')
                row = {'video': entry['name'], 'baseline': is_base, 'file': path.relative_to(ROOT).as_posix(),
                       'sha256': sha(path), 'frames': 300, 'playback_fps': 30, 'duration_seconds': 10,
                       'source_pts_first': records[0]['source_pts'], 'source_pts_last': records[-1]['source_pts'],
                       'resampling': 'Sequential decode; first source frame at/after each30Hz presentation time. No tracking/time rule or frame-dependent thresholds.',
                       'wall_seconds_including_writer_flush': wall,
                       'timing_ms': {key: stats([r[key] for r in timings]) for key in timings[0]},
                       'nonempty_frames': sum(bool(r['detections']) for r in records),
                       'prediction_records': rp.relative_to(ROOT).as_posix()}
                rows.append(row)
                save(OUT/'video_results.json', {'rows': rows, 'device': torch.cuda.get_device_name(0),
                                               'precision': 'FP32, TF32 disabled', 'warmup_excluded': 5,
                                               'timing_scope': 'PC only, synchronized single-image forward; not Orange Pi/NPU or sustained thermal test'})
                print(json.dumps({'completed': path.name, 'nonempty_frames': row['nonempty_frames'], 'forward_p50_ms': row['timing_ms']['forward_ms']['p50']}), flush=True)
    assert sha(ROOT/m['weight']) == m['weight_sha256']


if __name__ == '__main__':
    main()
