"""Render local video/image deliverables from already-computed fixed predictions."""
import html
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from evaluate_sc_recordings import draw, sha

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'artifacts/sc_video_eval_r1'
FONT = 'C:/Windows/Fonts/msyh.ttc'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, x):
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')


def rel(p):
    return Path(p).resolve().relative_to(OUT.resolve()).as_posix()


def main():
    manifest = read(OUT/'selection_manifest.json')
    predictions = read(OUT/'frame_predictions_640.json')
    large = read(OUT/'frame_predictions_960.json')
    videos = read(OUT/'video_results.json')
    reviews = []
    description = {
        'SC_BT_049': (4, 0, '中央横杆4个较远的竖向机动车灯体均未检出。',
                      '左右侧向、背向及更远处细小结构类别/存在性未完全确定，单列unknown。',
                      'COCO基线1框落在路侧装饰/立杆，不算正确检出。'),
        'SC_BT_053': (4, 0, '中央4个竖向机动车灯体均未检出；路口车辆、行人增加。',
                      '侧向及更远小结构保持unknown；不能因无框就视作背景。', 'COCO基线也未输出框。'),
        'SC_BT_057': (4, 0, '中央4个竖向机动车灯体仍未检出；可辨外壳，灯色不作结论。',
                      '其他远/侧向壳体未可靠归类；近处行人和车辆不是灯体。', 'COCO基线也未输出框。'),
        'SC_BT2_018': (0, 3, '3个车道通行信号壳体可见，全部未检出；其是否纳入现有灯体任务单列讨论。',
                       '路侧/背向暗面与更远细点不强行赋予机动车或行人类别。',
                       '新模型0.294行人灯体框覆盖右上楼宇/天空：明显误检；COCO无框。'),
        'SC_BT2_022': (0, 3, '3个绿色箭头车道信号具有清楚独立壳体，新模型全部未检出。',
                       '右侧成对黑色背板可见，但仅背面不能确认具体灯体类别；不当背景。',
                       'COCO基线正确框住3个车道信号（0.781/0.699/0.590）；只是候选定位成功。'),
        'SC_BT2_026': (0, 0, '近处信号已通过画面；本帧无可确认的常规机动车/行人灯体，无模型框。',
                       '远处细点仍unknown；本帧不据此成为完整标注背景。',
                       '楼宇、路灯、车辆与尾灯在640均未被新模型误框，属于本帧局部正确抑制。'),
        'SC_YJ_099': (2, 0, '2个完整横排机动车灯体清楚可见，均漏检；过曝主要影响发光区而非外壳存在。',
                      '远处灯点/侧向符号类别无法可靠确定；左侧数字倒计时不属于灯体。',
                      'COCO基线同样漏检这2个横排灯体。'),
        'SC_YJ_103': (2, 0, '2个完整横排机动车灯体均漏检；不能把颜色过曝扩展成灯体未知。',
                      '远处灯点及侧向符号单列unknown，不计作正例或背景。',
                      '新模型0.333行人灯体大框落在左下路面/汽车/反射区：明显误检。'),
        'SC_YJ_107': (2, 0, '2个完整横排机动车灯体均漏检；当前发光变化不改变灯体定义。',
                      '侧向符号/远灯点不确定；实际颜色和箭头不由检测框赋值。',
                      '新权重与COCO基线均无框；亮路灯/楼宇灯光本帧未被误检。'),
        'SC_YJ2_043': (0, 0, '高架蓝调场景，无清楚可辨的常规机动车/行人灯体，新模型无框。',
                       '地平线细小光点无法排除其他目标，保持unknown；LED提示板不强行归类。',
                       '近处尾灯、路灯和道路牌本帧未误框，是局部负例抑制成功，不能称全图真负例。'),
        'SC_YJ2_047': (0, 0, '未发现可确认的机动车/行人灯体；640无框。',
                       '更远光点不可判定；不把unknown计入准确率。',
                       '近处尾灯、车身、路灯在640未误框；960则将底部日期字符框成行人灯体。'),
        'SC_YJ2_051': (0, 0, '未发现可确认的机动车/行人灯体；640无框。',
                       '远车尾灯与光点无法逐一确定，保留unknown；大车对远景有遮挡。',
                       '近处货车尾灯在640未误框；960再次误框底部日期字符。'),
    }
    notes960 = {
        'SC_BT_049': '无框；中央灯体仍漏检。',
        'SC_BT_053': '新增1个机动车框，落在高楼顶部/立面，明显误检。',
        'SC_BT_057': '新增1个机动车框，落在树梢，明显误检。',
        'SC_BT2_018': '原大框消失；3个车道信号仍无检出。',
        'SC_BT2_022': '仍无框，3个车道信号未恢复。',
        'SC_BT2_026': '新增1个行人框，覆盖右侧楼宇/天空，明显误检。',
        'SC_YJ_099': '行人框落在机动车灯体右端/支架与旗帜附近，类别和完整壳体边界错误；不算检出。',
        'SC_YJ_103': '无框；两处横排灯体仍漏检。',
        'SC_YJ_107': '新增行人大框落在左下车辆/路面区域，明显误检。',
        'SC_YJ2_043': '无框。',
        'SC_YJ2_047': '新增行人框落在录像日期字符，明显误检。',
        'SC_YJ2_051': '新增行人框落在相同日期字符，明显误检。',
    }
    font = ImageFont.truetype(FONT, 20)
    small = ImageFont.truetype(FONT, 17)
    all_cards = []
    for row, r960 in zip(predictions['rows'], large['rows']):
        assert row['raw'] == r960['raw']
        stem = Path(row['raw']).stem.removesuffix('_raw')
        motor, lane, observation, uncertain, other = description[stem]
        review = {'frame_id': stem, 'video': row['video'], 'source_pts': row['decoded_pts_seconds'],
                  'raw_sha256': sha(ROOT/row['raw']), 'reviewer': 'Codex_PC_AI_visual_evaluation',
                  'independent_human_annotation': False, 'formal_generalization_test': False,
                  'actually_viewed_whole': row['preview'], 'actually_viewed_detail': row['source_detail']['file'],
                  'conventional_motor_bodies_identifiable': motor, 'pedestrian_bodies_identifiable': 0,
                  'lane_control_heads_separate_scope': lane,
                  'correct_complete_body_detections_640': 0, 'missed_conventional_bodies_640': motor,
                  'obvious_false_detections_640': len(row['detections']),
                  'observation': observation, 'unknown_excluded_from_count': uncertain,
                  'baseline_or_negative_example': other, 'fixed_same_frame_960': notes960[stem]}
        reviews.append(review)
        im = cv2.imread(str(ROOT/row['raw']))
        right = Image.open(ROOT/row['rendered']).convert('RGB')
        right = right.resize((800, round(right.height*800/right.width)))
        raw = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
        raw = raw.resize((800, round(raw.height*800/raw.width)))
        panel_h = right.height
        canvas = Image.new('RGB', (1600, panel_h+144), '#111b2b')
        canvas.paste(raw, (0, panel_h-raw.height))
        canvas.paste(right, (800, 0))
        dr = ImageDraw.Draw(canvas)
        dr.text((14, 12), f'原图 {row["video"]} / {row["decoded_pts_seconds"]:.3f}s', fill='white', font=font)
        lines = [observation, other, 'AI视觉评估：'+uncertain]
        yy = panel_h+12
        for line in lines:
            for chunk in textwrap.wrap(line, width=86):
                dr.text((14, yy), chunk, fill='#dbe8f7', font=small)
                yy += 23
        cmp_path = OUT/'frames'/f'{stem}_compare.jpg'
        canvas.save(cmp_path, quality=94)
        review['comparison'] = cmp_path.relative_to(ROOT).as_posix()
        # Render existing960 predictions only, without running the model again.
        v960 = draw(im, r960['detections'], '同一固定帧 / 仅一次960对照', row['decoded_pts_seconds'], input_size=960)
        pp = OUT/'frames'/f'{stem}_best960.jpg'
        cv2.imwrite(str(pp), v960, [cv2.IMWRITE_JPEG_QUALITY, 93])
        review['rendered960'] = pp.relative_to(ROOT).as_posix()
        baseline = row.get('baseline', {})
        all_cards.append(f'''<article id="{stem}"><h3>{html.escape(row['video'])} · {row['decoded_pts_seconds']:.3f}s</h3>
<a href="{rel(cmp_path)}" target="_blank"><img loading="lazy" src="{rel(cmp_path)}" alt="原图与真实640推理结果对照"></a>
<p>{observation} {other}</p><p class="muted">待定：{uncertain}</p>
<div class="links"><a href="{rel(ROOT/row['raw'])}" target="_blank">原始PNG</a><a href="{rel(ROOT/row['source_detail']['file'])}" target="_blank">原图局部放大</a>
<a href="{rel(ROOT/baseline['rendered'])}" target="_blank">COCO基线640</a><a href="{rel(pp)}" target="_blank">固定帧960</a></div>
<details><summary>960对照与不确定范围</summary><p>{notes960[stem]}</p><p>{uncertain}</p></details></article>''')
    video_html = []
    title = {'SC_BT': '日间复杂路口 / 远小灯体', 'SC_BT2': '黄昏高架 / 车道信号与路牌',
             'SC_YJ': '夜间路口 / 横排灯体与过曝', 'SC_YJ2': '蓝调高架 / 尾灯、路灯、文字干扰'}
    checks = []
    for entry in manifest['entries']:
        stem = Path(entry['name']).stem
        rs = [r for r in videos['rows'] if r['video'] == entry['name']]
        main_video = next(r for r in rs if not r['baseline'])
        base_video = next(r for r in rs if r['baseline'])
        # Decode every delivered video fully; never infer additional inputs.
        for r in rs:
            cap = cv2.VideoCapture(str(ROOT/r['file']))
            frames = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frames += 1
            cap.release()
            assert frames == 300 and sha(ROOT/r['file']) == r['sha256']
            checks.append({'file': r['file'], 'fully_decoded_frames': frames, 'sha256': r['sha256']})
        video_html.append(f'''<article><h2>{title[stem]}</h2><p>{entry['name']} · 固定 {entry['start_seconds']}–{entry['end_seconds']}s · 10秒 / 300帧</p>
<video controls preload="metadata" playsinline src="{rel(ROOT/main_video['file'])}"></video>
<div class="links"><a href="{rel(ROOT/main_video['file'])}">打开新权重视频</a><a href="{rel(ROOT/base_video['file'])}">打开同片段COCO基线</a></div>
<details><summary>播放同片段COCO基线</summary><video controls preload="none" playsinline src="{rel(ROOT/base_video['file'])}"></video></details></article>''')
    timing_rows = []
    primary = [r for r in videos['rows'] if not r['baseline']]
    for r in primary:
        a = r['timing_ms']['forward_ms']
        b = r['timing_ms']['decode_infer_draw_ms']
        timing_rows.append(f'<tr><td>{r["video"]}</td><td>{a["p50"]:.2f} / {a["p95"]:.2f}</td><td>{b["p50"]:.2f} / {b["p95"]:.2f}</td></tr>')
    summary = {
        'recorded_at': datetime.now(timezone.utc).isoformat(), 'weight_sha256': manifest['weight_sha256'],
        'source_selection_manifest_sha256': sha(OUT/'selection_manifest.json'),
        'scope': 'AI visual development/regression evaluation; not independent human labels or formal accuracy.',
        'fixed_frames': len(reviews), 'motor_body_frame_occurrences_identifiable': sum(r['conventional_motor_bodies_identifiable'] for r in reviews),
        'pedestrian_body_frame_occurrences_identifiable': 0,
        'lane_control_frame_occurrences_separate_scope': sum(r['lane_control_heads_separate_scope'] for r in reviews),
        'confirmed_correct_full_body_detections_640_in_fixed_frames': 0,
        'obvious_false_detections_640_in_fixed_frames': sum(r['obvious_false_detections_640'] for r in reviews),
        'confirmed_correct_full_body_detections_960_in_fixed_frames': 0,
        'formal_accuracy_computed': False, 'unknown_as_background': False,
        'prior_tiny_val640_mAP50': .5192899999999999, 'prior_tiny_val_originals': 5, 'prior_tiny_val_bodies': 8,
        'prior_val_used_to_claim_China_accuracy': False,
        'next_priority': 'C', 'ready_for_deployment': False,
        'recommendation': '优先补齐并核对中国路口横排/远小灯体、夜间和文字/装饰物负例的完整监督，再决定重训。此轮不自动开训。',
        'board_numeric_failure_unchanged': True, 'no_train_no_export_no_install_no_download_no_new_RKNN': True,
        'primary_timing_device': videos['device'],
        'forward_mean_ms': float(np.mean([r['timing_ms']['forward_ms']['mean'] for r in primary])),
        'decode_infer_draw_mean_ms': float(np.mean([r['timing_ms']['decode_infer_draw_ms']['mean'] for r in primary])),
        'reviews': reviews, 'video_validation': checks,
    }
    save(OUT/'visual_evaluation.json', summary)
    # Three comparisons per source, kept as four moderate overview artifacts.
    for entry in manifest['entries']:
        stem = Path(entry['name']).stem
        selected = [r for r in reviews if r['video'] == entry['name']]
        cards = []
        for r in selected:
            card = Image.open(ROOT/r['comparison']).convert('RGB')
            card = card.resize((1200, round(card.height*1200/card.width)))
            cards.append(card)
        sheet = Image.new('RGB', (1200, sum(c.height for c in cards)), '#111b2b')
        yy = 0
        for card in cards:
            sheet.paste(card, (0, yy)); yy += card.height
        sheet.save(OUT/f'{stem}_three_comparisons.jpg', quality=92)
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>现有模型 · 四段真实录像评估</title><style>
*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#e4edfa;font:16px/1.65 "Microsoft YaHei",sans-serif}main{max-width:1320px;margin:auto;padding:30px 24px 80px}h1{font-size:34px;line-height:1.3}h2{font-size:24px}h3{font-size:20px}p{max-width:1100px}a{color:#83c9ff;text-decoration:none}a:hover{text-decoration:underline}.muted{color:#b1c2da}.notice{border-left:4px solid #ffb45b;padding:12px 20px;background:#241e20}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}article{background:#141f31;border:1px solid #2c3b53;border-radius:12px;padding:18px;margin-bottom:20px;overflow:hidden}video,img{display:block;width:100%;height:auto;background:#080b12;border-radius:6px}.links{display:flex;gap:20px;flex-wrap:wrap;margin:10px 0}details{margin-top:12px}summary{cursor:pointer;color:#aad6ff}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:10px;border-bottom:1px solid #344258}.stats{display:flex;gap:14px;flex-wrap:wrap}.stats span{background:#182a40;border-radius:8px;padding:14px}nav{display:flex;gap:24px;margin:24px 0}.samples article{margin-top:18px}code{overflow-wrap:anywhere;color:#c5d6ed;font-size:13px}@media(max-width:800px){.grid{grid-template-columns:1fr}main{padding:20px 12px}h1{font-size:28px}}
</style><main><p class="muted">首轮最佳模型 · PC实际推理 · 仅使用四个既有SC开发录像</p>
<h1>视频已经能看，当前模型尚不值得部署</h1>
<p class="notice">固定12帧中，新权重640没有确认检出完整灯体，出现2个明显误检；夜间2个横排灯体持续漏检。没有凑出“成功正例”。成功对照包括COCO基线框中3个车道信号，以及640在部分高架帧对尾灯/路灯的正确抑制。</p>
<div class="stats"><span>4段连续录像 × 10秒</span><span>12张固定原图/结果对照</span><span>640 / conf0.25 / IoU0.45</span><span>仅灯体，不识别灯色/箭头/控制方向</span></div>
<nav><a href="#videos">看四段视频</a><a href="#samples">看12张对照</a><a href="#timing">看PC耗时</a><a href="#decision">建议</a></nav>
<p class="muted">选段在模型推理前固定，未按效果换段。SC_BT2实际为黄昏高架，SC_YJ2为蓝调高架；素材不包含第二段日间复杂路口。连续源画面按30Hz呈现，每帧真实推理；无时间/场景/位置规则、跟踪或隐藏框。视频无音频。</p>
<h2 id="videos">四段真实检测视频</h2><div class="grid">'''+''.join(video_html)+'''</div>
<p class="muted">COCO对照直接读取m406既有YOLOv8s原权重，只看class9，同样全图640。它不是完整m406的交替半图、几何、灯色或跟踪系统，也不是板端性能对照。</p>
<h2 id="samples">逐张原图、检测结果及视觉结论</h2><p>这12帧在推理前固定为每片第1、5、9秒。AI实际看过整图与局部放大；unknown逐张保留。18处常规机动车灯体是跨帧重复出现次数，另外6处车道通行信号单列范围，均不构成正式准确率。未找到可确认行人灯体，无法评价行人召回。</p>
<div class="samples">'''+''.join(all_cards)+'''</div>
<h2 id="timing">PC耗时，单位ms / 帧</h2><p>设备：'''+html.escape(videos['device'])+'''。FP32，TF32关闭，batch1；每模型预热5次后，每片300帧。纯前向使用CUDA同步计时，含原生检测头解码；解码→推理→绘制含预处理、拷贝、NMS与中文绘制，不含编码。不是香橙派性能。</p>
<table><tr><th>片段</th><th>纯前向 p50 / p95</th><th>解码+推理+绘制 p50 / p95</th></tr>'''+''.join(timing_rows)+'''</table>
<p class="muted">保存视频的编码提交和最终flush另有记录；本次短片不证明持续温控性能。没有重新跑CUDA预检。</p>
<h2 id="decision">唯一优先建议：C，先补对应完整数据监督</h2>
<p>先核对并补齐中国路口横排/远小灯体、夜间、楼宇/文字/装饰物负例的完整标注，再决定下一轮训练。固定同一12帧的单次960对照没有恢复可靠完整灯体检出，反而在楼顶、树梢、日期文字等处增加错误；因此当前证据不足以优先投入板端部署，或仅靠升高输入尺寸解决。</p>
<p>已有验证报告：640 mAP50=0.5193；960 mAP50=0.7546，仅5张原图/8个目标，不代表中国道路精度。本页开发帧具有选择性，不输出正式P/R或准确率。原RKNN数值门槛及失败结论不变。</p>
<p class="muted">权重SHA256：<code>'''+manifest['weight_sha256']+'''</code><br>类别0=机动车灯体，1=行人灯体。RGB、居中letterbox114、固定正方形640、/255一次；原生PT检测头Sigmoid一次，未二次激活。</p>
<p>本轮交付已完成，停止执行，等待用户审核安排后续。</p></main></html>'''
    (OUT/'index.html').write_text(page, encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ['fixed_frames', 'motor_body_frame_occurrences_identifiable', 'obvious_false_detections_640_in_fixed_frames', 'next_priority', 'forward_mean_ms', 'decode_infer_draw_mean_ms']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
