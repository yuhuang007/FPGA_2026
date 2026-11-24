"""Serialize explicit AI visual decisions. Does not auto-accept XML geometry/classes.

Every coordinate below was selected after viewing the original and context crops.
Unresolved regions deliberately block standard YOLO full-image export.
"""
from pathlib import Path
import csv,hashlib,json,time
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1]
O=R/'review_stage2'; (O/'first_pass').mkdir(exist_ok=True); (O/'overlays').mkdir(exist_ok=True)
def body(box,layout='horizontal',kind='motor_vehicle',truncated=False):
    return {'type':'body','bbox_xyxy':box,'kind':kind,'layout':layout,'group_id':None,
        'occlusion':'none','truncated':truncated,'control_relation':'unknown','quality_flags':[],
        'kind_basis':'可见三孔圆形信号壳体；非仅按道路位置判断'}
def emitter(box,color,symbol='circle',arrow='unknown'):
    return {'type':'emitter','parent_id':'body_1','bbox_xyxy':box,'state':color,
        'color_readable':color!='unknown','symbol':symbol,'arrow_direction':arrow,
        'unknown_reason':None if color!='unknown' else 'too_small','quality_flags':[]}
def ignore(box,reason):
    return {'type':'ignore','bbox_xyxy':box,'kind':'unknown','unknown_reason':reason,
        'quality_flags':['ambiguous_body'],'control_relation':'unknown'}

# Main common housing, actual illuminated circle and unresolved side/distant signals.
horizontal={
0:([614,476,635,523],[619,507,632,521],'green',[[938,465,961,514],[1558,528,1583,562]]),
1:([614,476,635,523],[618,480,632,495],'red',[[938,462,961,514],[1558,528,1583,562]]),
2:([614,476,635,523],[618,480,632,495],'red',[[938,462,961,514],[1558,528,1583,562]]),
3:([614,476,635,523],[618,506,632,521],'green',[[938,465,961,514],[1558,528,1583,562]]),
4:([614,476,635,523],[618,506,632,521],'green',[[938,465,961,514],[1558,528,1583,562]]),
5:([614,476,635,523],[618,506,632,521],'green',[[938,465,961,514],[1558,528,1583,562]]),
6:([614,476,635,523],[618,480,632,495],'red',[[938,462,961,514],[1558,528,1583,562]]),
7:([614,476,635,523],[618,480,632,495],'red',[[938,462,961,514],[1558,528,1583,562]]),
212:([1021,367,1068,389],[1047,371,1061,385],'green',[[1304,428,1338,478]]),
213:([960,345,1005,368],[986,352,1003,365],'green',[[1308,414,1345,468]]),
214:([1017,325,1071,349],[1050,327,1067,344],'green',[[1316,428,1342,477]]),
215:([1023,289,1082,316],[1059,292,1080,313],'green',[[1392,410,1430,474],[1184,431,1208,460]]),
216:([1080,275,1146,306],[1120,280,1143,302],'green',[[1520,400,1560,469],[1235,431,1264,462]]),
217:([1064,242,1140,274],[1093,246,1118,271],'yellow',[[1625,382,1664,475],[1195,431,1222,465]]),
218:([1094,221,1184,259],[1100,225,1129,254],'red',[[1809,376,1852,478],[1214,443,1242,479]]),
219:([1280,0,1458,72],[1294,7,1348,59],'red',[[1270,480,1310,515]]),
220:([1280,0,1458,72],[1294,7,1348,59],'red',[[1270,480,1310,515]]),
221:([1280,0,1458,72],[1294,7,1348,59],'red',[[1270,480,1310,515]]),
222:([1280,0,1458,72],[1294,7,1348,59],'red',[[1270,480,1310,515]]),
223:([1280,0,1458,72],[1398,6,1452,59],'green',[[1270,480,1310,515]]),
}

def main():
    rows=list(csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig')))
    source=json.loads((O/'source_reference.json').read_text())
    notes=json.loads((O/'visual_snapshot_0400.json').read_text())
    now=time.strftime('%Y-%m-%dT%H:%M:%S%z')
    for i,(bb,eb,color,unknowns) in horizontal.items():
        objects=[dict(body(bb,layout='vertical' if i<8 else 'horizontal',truncated=i>=219),id='body_1'),dict(emitter(eb,color),id='emitter_1')]
        objects += [dict(ignore(b,'cannot_identify_kind'),id=f'ignore_{k+1}') for k,b in enumerate(unknowns)]
        record={'schema_version':'0.1','label_version':'pc-ai-r1.0-20261024',
            'candidate_id':rows[i]['sample_id'],'image_path':rows[i]['image_path'].replace('\\','/'),
            'image_sha256':rows[i]['sha256'],'image_size':[1920,1080],
            'reviewer':'Codex_PC_AI_stage2','reviewer_type':'AI','human_signoff':False,'recorded_at':now,
            'review_status':'AI_first_pass_detailed_pending_independent',
            'actual_method':['prior unmarked full image + XML-context panel',
                f'original-pixel upper image including y=0 + 4x nearest crop: review_stage2/zooms/{i:04d}.png',
                ('right omitted candidate 5x crop: review_stage2/zooms/gate_0000_0007.png' if i<8 else
                 'side candidate 4x crop: review_stage2/zooms/side_candidates.png' if i<=219 else 'same-scene far area inspected at original image scale')],
            'complete_image_annotation':False,'eligible_for_yolo_export':False,
            'blocked_reason':'侧/远信号有不能确认kind或外壳的ignore区域；标准YOLO不得把它们当背景。独立复审和人工确认未完成。',
            'objects':objects,'source_reference_only':source[i],
            'changes':['按可见外壳重新核上/下边界，保留一件共壳灯体；不导出源框作为真值。',
                '补录源XML遗漏的侧面/远处疑难区域为ignore；不按位置猜pedestrian。',
                '内嵌数字不另建交通灯body/emitter；当前圆灯发光区域单独标。',
                '219–223灯壳顶部触图像边界，visible body从y=0起，truncated=true。' if i>=219 else '灯体与发光区域分别记录。'],
            'first_screening_note':notes[i]['note'],
            'arbitration':['侧面三孔外观能否确定motor_vehicle，需独立核实；保守ignore。',
                '远端小亮点可能是信号/尾灯，kind与边界不可辨，不能强行补确定正例。',
                '内嵌倒计时与共壳body定义按原规范待人工确认；数字本身不作为灯。']}
        p=O/'first_pass'/f'{rows[i]["sample_id"]}.json'
        # Keep a prior serialized decision stable on rerun; edit explicit JSON for amendments.
        if not p.exists(): p.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        else: record=json.loads(p.read_text(encoding='utf-8'))
        im=Image.open(R/rows[i]['image_path']).convert('RGB');d=ImageDraw.Draw(im)
        for obj in record['objects']:
            c={'body':'#00ff70','emitter':'#ffff00','ignore':'#ff40ff','hard_negative':'#ff9800'}[obj['type']]
            d.rectangle(obj['bbox_xyxy'],outline=c,width=2)
            d.text((obj['bbox_xyxy'][0],max(0,obj['bbox_xyxy'][1]-13)),obj['id']+' '+obj.get('kind',obj.get('state','')),fill=c)
        im.save(O/'overlays'/f'{rows[i]["sample_id"]}.jpg',quality=96)
    print(f'{len(horizontal)} detailed AI drafts serialized; none approved or train-exportable')
if __name__=='__main__': main()
