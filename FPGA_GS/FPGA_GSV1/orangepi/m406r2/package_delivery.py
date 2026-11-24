"""Package existing evidence only; never run inference or control a service."""
import hashlib, html, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))
def write(name, obj):
    (ROOT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

deploy = read(ROOT/'evidence/deployment_check.json')
assert all(sha(ROOT.parent/'m406'/n) == v for n,v in deploy['original'].items())
assert all(sha(ROOT/n) == v for n,v in deploy['candidate'].items() if (ROOT/n).is_file())
for n in ['driving.py','road.py','lane_semantics.py']:
    assert sha(ROOT/n) == sha(ROOT.parent/'m406'/n)

original = read(ROOT.parent/'m406/model_manifest.json')
model = dict(original['selected'])
model['sha256'] = deploy['original']['yolov8s640_fp16.rknn']
model['schedule'] = {'target_total_hz':4,'cycle':['center','left','right','center','full','left','right'],
                     'regions_normalized':{'center':[.30,.12,.70,.70],'left':[0,.12,.40,.70],'right':[.60,.12,1,.70],'full':[0,0,1,1]},
                     'note':'one neural call per observation; this is not four observations per second for every individual light'}
manifest = {'release':'M4-06-r2-candidate','selected':model,
 'existing_environment':{'python':'../.venv404/bin/python','RKNN_Lite':'2.5.0','runtime':'2.3.0','driver':'0.9.8','model_build_toolkit':'2.3.2','new_packages_or_conversion':False},
 'weight_storage':{'remote_symlink':'yolov8s640_fp16.rknn -> ../m406/yolov8s640_fp16.rknn','local_original':'../m406/yolov8s640_fp16.rknn'},
 'color':{'source':'CPU original RGB/HSV within bounded model or paired-capsule candidates; bright-core centering is localization only',
          'geometry_hypothesis_factors':[.65,.85,1.05,1.35],'geometry_limit':'paired horizontal three-cell casing hypothesis, not a trained light-body result',
          'confirmation':'two distinct, increasing source images; changed color becomes UNKNOWN pending immediately',
          'expiry_ms':600,'template_max_age_ms':1200,'template_refresh':'independent direct detection only; tracked image rereads current RGB',
          'edge_candidate':'UNKNOWN; crop boundary cannot establish a complete light',
          'shape':'UNKNOWN','direction':'UNKNOWN','control_relation':'UNKNOWN','automatic_release':False,'OFF':'never inferred from a miss'},
 'protected':deploy['original'],'candidate_source_sha256':deploy['candidate'],
 'scope':'FILE_TEST + SIMULATION vehicle only. No LIVE, FPGA, UDP, new trained weights, final-test input, network/environment change.'}
write('model_manifest.json',manifest)

offline=[]
for meta in read(ROOT/'evidence/offline/summary.json'):
    stem=Path(meta['video']).stem
    rows=[json.loads(line) for line in (ROOT/f'evidence/offline/{stem}_predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    versions={}
    for name in ['m406','m406r2']:
        results=[x['versions'][name] for x in rows]
        counts={c:sum(b.get('color')==c for r in results for b in r['lights']) for c in ['RED','YELLOW','GREEN','UNKNOWN']}
        versions[name]={'observations':len(rows),'observations_with_any_confirmed_color':sum(any(b.get('color') in ['RED','YELLOW','GREEN'] for b in r['lights']) for r in results),
                        'observations_without_candidate':sum(not r['lights'] for r in results),'light_observation_counts':counts,
                        'transitions':[{'source_pts':x['source_pts'],'source_frame_id':x['source_frame_id'],'events':x['versions'][name]['transitions']} for x in rows if x['versions'][name].get('transitions')]}
    offline.append(dict(meta,versions=versions,comparison_video=f'evidence/offline/{stem}_source_exact.mp4'))

performance={}
for version in ['baseline','candidate']:
    performance[version]=[]
    for row in read(ROOT/f'evidence/browser/{version}/performance.json'):
        ages=[s.get('perception',{}).get('traffic',{}).get('age_ms') for s in row['samples']]
        ages=[a for a in ages if isinstance(a,(int,float))]
        keep={k:v for k,v in row.items() if k!='samples'}
        keep['sampled_traffic_observation_age_max_ms']=max(ages) if ages else None
        performance[version].append(keep)
report={'release':'M4-06-r2-candidate','recommend_replace_default':False,
 'decision':'Night SC_YJ 98-108s improved; day/other scene continuity and false bodies remain inadequate. Retain independent candidate.',
 'evaluation_scope':{'training':False,'final_test_used':False,'fixed_images':12,'additional_LED_negative':1,
   'videos':'Four original development/regression videos; selected frozen continuous windows only, not full-length acceptance',
   'baseline':'complete original m406 traffic crop/geometry/color/tracking branch, not PC full-image YOLO alone',
   'replay':'same source PTS and object exclusion input for both; source-exact thumbnails; 15fps rendered output is not measured throughput',
   'browser':'actual headless Edge canvas through SSH, unique epoch/frame_id counts, recordings include failures. Sequential runs, not simultaneous or strict performance causality.'},
 'offline':offline,'real_time_browser':performance,
 'age_definition':'host decode-complete to host observation/display time; not camera-to-browser or physical event latency. Expired observations >600ms carry no valid old light.',
 'switch_observation':'YJ current GREEN 104.933s -> pending UNKNOWN -> confirmed GREEN 105.233s (300ms source PTS); source data in predictions.jsonl, not physical end-to-end latency',
 'known_failures':[
   'SC_BT 49.2s camera/information plate misdetected as a traffic-light body; retained UNKNOWN with raw evidence.',
   'SC_YJ2 44.4s roadside fixture/backplate misdetected; retained UNKNOWN.',
   'Day SC_BT/BT2: real remote lights often missed or UNKNOWN; new schedule has MORE zero-candidate observations in these windows, not a broad recall improvement.',
   'SC_YJ browser recording after 109s includes expired empty observations and later ID loss/UNKNOWN. Stable selected 98-108s does not generalize to all night footage.',
   'Existing LED negative: no left sign promoted by paired-housing geometry, but partially clipped side/countdown candidate remains UNKNOWN.',
   'Yellow lacks reliable positive validation; OFF, arrow, vehicle/pedestrian lamp classification and request control attribution not established.',
   'No labelled truth set/mAP/accuracy; certain-color coverage is not accuracy. Geometry body score is not neural confidence.'
 ],
 'checks':{'targeted_tests':'evidence/targeted_tests.log','pause_and_switch':'evidence/browser/candidate/expiry_switch_checks.json','loop':'evidence/browser/candidate/loop_check.json',
           'browser_exports':'evidence/browser/exports.json','protected_source_and_runtime':'evidence/deployment_check.json',
           'lifecycle':'candidate state/candidate_start_*.json and candidate_stop_*.json: start, repeated start same PID, graceful stop, repeated stop, restarted current candidate'},
 'render_note':'Use *_source_exact.mp4 and *_source_exact.jpg. Earlier *_m406_vs_m406r2.mp4 / *_compare.jpg are retained intermediate renders; their enlarged crops were sampled from display rather than original observation frame and are superseded.',
 'operation':{'remote_directory':deploy['remote']+'/m406r2','url':'http://127.0.0.1:18082/','remote_bind':'127.0.0.1:8082','start':'启动交通灯候选.cmd','stop':'停止交通灯候选.cmd',
              'configuration':'../oneclick/config.json SSH user/host/port/remote_dir; candidate ports isolated from defaults',
              'closing_launcher':'remote continues running; use candidate stop for a deliberate stop',
              'rollback':['stop candidate using 停止交通灯候选.cmd','start original ../oneclick/启动智驾录像演示.cmd'],
              'concurrency':'candidate refuses original full demo already running; stop candidate before starting original, do not share NPU across these benchmarks'},
 'new_numeric_experiments_or_training':False}
write('delivery.json',report)

cards=[]
for stem,title,sec in [('SC_YJ','夜间两个横排灯／红绿转换',103),('SC_BT','日间远灯及漏检',53),('SC_BT2','高架干扰与未知',22),('SC_YJ2','弱灯与环境结构误检',43)]:
    cards.append(f'''<section><h2>{title}</h2><p>左：原m406完整交通灯支路；右：候选。相同源时间；放大窗取检测实际来源帧。离线渲染供视觉比较，不能据此声称实时15fps。</p>
<video controls preload="metadata" src="evidence/offline/{stem}_source_exact.mp4" poster="evidence/offline/{stem}_{sec}_source_exact.jpg"></video>
<details><summary>实际浏览器连续录屏：原版／候选（包含失败）</summary><div class="pair"><div>原版<video controls preload="none" src="evidence/browser/baseline/{stem}.mp4"></video></div><div>候选<video controls preload="none" src="evidence/browser/candidate/{stem}.mp4"></video></div></details></section>''')
rows=''.join(f"<tr><td>{r['video']}</td><td>{r['processedFps']:.2f}</td><td>{r['previewNewFrameFps']:.2f}</td><td>{r['objectHz']:.2f}</td><td>{r['roadHz']:.2f}</td><td>{r['trafficHz']:.2f}</td><td>{r['sampled_traffic_observation_age_max_ms']:.1f}</td></tr>" for r in performance['candidate'])
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>m406 / m406r2 交通灯对照</title>
<style>body{max-width:1320px;margin:24px auto;padding:0 16px;background:#111820;color:#e7edf4;font:17px/1.6 system-ui}a{color:#8dd5ff}video,img{width:100%;height:auto;background:#000}section{border-top:1px solid #526270;margin-top:24px;padding-top:12px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #526270;padding:6px}summary{cursor:pointer}.warning{background:#463d21;padding:12px}</style>
<h1>原m406与独立m406r2候选</h1><p class="warning">FILE_TEST／模拟车辆。原YOLOv8s COCO权重不变，RKNN/NPU灯体候选＋CPU原图灯色与几何。箭头及本车控制关系均UNKNOWN，不自动放行。建议暂不替换默认版本。</p>
<p><a href="http://127.0.0.1:18082/" target="_blank">打开当前香橙派候选预览</a> · <a href="启动交通灯候选.cmd">启动入口</a> · <a href="停止交通灯候选.cmd">停止入口</a>（cmd请在资源管理器双击）</p>
<p>建议先点网页“夜间红灯”，再点“转灯观察101秒”：两个横排灯由红转绿时先待确认再显示绿；看灯框、来源帧、结果年龄及放大窗。日间点“日间远灯53秒”。可关交通灯图层对照原图。关闭启动窗口后远端仍运行。</p>
<p>固定夜间98–108秒34次同源观测：原版1次有确认灯色，候选32次；这是覆盖记录，不是准确率。当前绿光首次观测至确认300ms（源时间）。亮芯定位与灯壳尺度修正有效，日间仍漏检，夜间110秒后也有ID丢失。完整失败保留在下方录屏。</p>
'''+''.join(cards)+'''<section><h2>实际浏览器测量</h2><p>640宽，真实时间轴，经SSH转发，headless Edge实际页面canvas；每次仅1个图片请求在途，无重复帧计入新帧率。每片约13秒短窗，原版与候选顺序运行；数字有短窗波动，不是全片性能保证。</p><table><tr><th>视频</th><th>处理fps</th><th>网页新帧fps</th><th>人车Hz</th><th>道路Hz</th><th>交通灯Hz</th><th>采样灯观测最大龄ms</th></tr>'''+rows+'''</table><p>交通灯一次观测约205–227ms，其中NPU约99–103ms，CPU几何/灯色约87–107ms；不是15Hz灯态检测。单灯观测率与总交通灯Hz不同。图龄从主机解码完成起算，超过600ms旧灯消失；不能视为摄像头到网页延迟。</p></section>
<section><h2>真实页面及原始证据</h2><div class="pair"><a href="evidence/visible/red_page.png"><img src="evidence/visible/red_page.png" alt="候选红灯页面"></a><a href="evidence/visible/green_page.png"><img src="evidence/visible/green_page.png" alt="候选绿灯页面"></a></div><p>原始帧、叠加帧及对应状态另存于evidence/visible，原录像不改写。</p></section>
<section><h2>保留的失败</h2><p>日间摄像头/信息牌、蓝调路侧装置仍被误检为灯体（UNKNOWN）；日间远灯与高架缺少可靠灯色；夜间后段跟踪中断。黄灯无可靠正例、熄灭不可由漏检推断。不能把更少的框或更多UNKNOWN算成准确率改善。</p><div class="pair"><div>日间误检<a href="evidence/failures/SC_BT_raw.jpg"><img src="evidence/failures/SC_BT_detail.jpg"></a></div><div>路侧装置误检<a href="evidence/failures/SC_YJ2_raw.jpg"><img src="evidence/failures/SC_YJ2_detail.jpg"></a></div></div></section>
<section><h2>停止与回退</h2><p>双击本目录“停止交通灯候选.cmd”，只停止身份一致的候选和其SSH转发。回退后双击原orangepi/oneclick/启动智驾录像演示.cmd；默认入口和m406源码未改。候选不会自动停止原演示，避免两套模型争用NPU。</p><p><a href="delivery.json">完整结果JSON</a> · <a href="model_manifest.json">模型/参数/SHA清单</a> · <a href="evidence/offline/fixed_results.json">12固定帧＋LED结果</a> · <a href="evidence/targeted_tests.log">定向检查</a> · <a href="evidence/deployment_check.json">本地/远端保护核对</a></p></section></html>'''
(ROOT/'查看候选对照.html').write_text(page,encoding='utf-8')
print('packaged existing evidence; no inference, network or service operation')
