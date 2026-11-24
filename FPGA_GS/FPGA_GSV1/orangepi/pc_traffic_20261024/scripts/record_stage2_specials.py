"""Explicit visual corrections / exclusion proposals for twelve difficult images."""
from pathlib import Path
import csv,json,time
from PIL import Image,ImageDraw
from record_stage2_labels import body,emitter,ignore
R=Path(__file__).resolve().parents[1]; O=R/'review_stage2'
def b(box,ident,layout='horizontal',truncated=False):
    return dict(body(box,layout=layout,truncated=truncated),id=ident)
def e(box,ident,parent,color,symbol='circle',arrow='unknown'):
    return dict(emitter(box,color,symbol,arrow),id=ident,parent_id=parent,
        unknown_reason='saturation' if color=='unknown' else None)
def ig(box,ident,reason='cannot_identify_kind'):
    return dict(ignore(box,reason),id=ident)
def neg(box,ident,reason):
    return {'type':'hard_negative','bbox_xyxy':box,'id':ident,'reason':reason}
def special_records():
    return {
22:('proposed_exclude_ambiguous_body',[
 ig([591,503,617,538],'ignore_1','too_small')],
 '原图及4倍裁剪只见树叶后的小黄亮点；不能确定kind/灯壳，不沿用XML yellow作motor body。整图不能充当负图。'),
93:('proposed_exclude_ambiguous_body',[
 ig([937,462,962,515],'ignore_1'),ig([1558,528,1583,562],'ignore_2')],
 '左近灯被公交车完全遮住；远树内亮点与门岗小亮物均不足以确认壳体/kind。未画推测的被遮灯框。'),
111:('proposed_exclude_ambiguous_body',[
 ig([922,489,944,518],'ignore_1','too_small')],
 '远竖直灯只见数字和绿亮点，外壳上边及kind不可靠。保留ignore，不能按绿点猜motor。'),
187:('proposed_exclude_ambiguous_body',[
 ig([885,28,969,71],'ignore_1','saturation'),ig([990,27,1077,74],'ignore_2','saturation'),
 ig([416,106,464,161],'ignore_3','saturation'),ig([463,108,493,154],'ignore_4','saturation'),
 ig([1694,197,1723,242],'ignore_5','saturation'),ig([665,201,711,233],'ignore_6','too_small'),
 e([896,36,918,61],'emitter_arrow_1','ignore_1','unknown','arrow','left'),
 e([1698,206,1718,232],'emitter_person_1','ignore_5','unknown','pedestrian'),
 neg([1691,278,1728,409],'negative_LED_text','辅助竖排LED文字，非行人灯壳体'),
 neg([1682,448,1734,591],'negative_reflection','湿地红色反光，非信号灯')],
 '源#1框[1321,204,1327,204]零高度，且所指为限速牌下提示牌；删除无效正例。右侧人形发光可辨但外壳欠曝，单列emitter/ignore，不作为body真值。饱和灯色unknown，左箭头形状可辨。'),
266:('proposed_exclude_ambiguous_body',[
 neg([1415,131,1676,180],'negative_LED_text','左转车进入待转区辅助文字，源wait_on不是交通灯'),
 ig([1390,184,1491,239],'ignore_1','saturation'),ig([1578,182,1695,239],'ignore_2','saturation'),
 ig([567,306,620,428],'ignore_3','saturation'),ig([623,340,672,438],'ignore_4','saturation'),
 e([1401,195,1439,231],'arrow_left','ignore_1','unknown','arrow','left'),
 e([1648,190,1687,228],'green_circle','ignore_2','green'),
 neg([1186,568,1305,596],'negative_taillights','前车尾灯，非交通灯')],
 'LED文字作为hard_negative；数字6/3不能作为独立灯体。夜景壳体不可辨，不能以发光/光晕框替body。源漏左侧竖灯以ignore补录。'),
280:('proposed_exclude_ambiguous_body',[
 neg([838,432,884,447],'negative_LED_text','源green#0实际辅助LED文字'),
 ig([836,443,866,462],'ignore_1','too_small'),ig([871,441,893,460],'ignore_2','too_small')],
 '源#0 green实际LED文字，移出灯体类；两下方小亮区不能可靠确定共壳边界。禁止直接导出3个source框。'),
282:('proposed_exclude_ambiguous_body',[
 neg([838,310,905,327],'negative_LED_text','辅助LED文字不是灯体'),
 ig([834,326,870,346],'ignore_1','too_small'),ig([889,321,917,355],'ignore_2','too_small'),
 ig([354,399,376,429],'ignore_3','too_small'),ig([211,419,234,486],'ignore_4','too_small'),
 e([894,326,906,338],'green_circle','ignore_2','green')],
 '源#2 red对应右侧圆灯实际为green；保留直接可见颜色属性，身体框和kind仍未知。左侧低/侧灯漏标，以ignore补录。'),
285:('detailed_draft_return_for_arbitration',[
 neg([663,195,830,230],'negative_LED_text','辅助LED文字'),
 b([654,228,739,266],'body_1'),b([764,226,843,264],'body_2'),
 e([659,235,687,260],'left_arrow','body_1','red','arrow','left'),
 ig([886,380,917,402],'ignore_1','too_small')],
 '右共壳当前仅可见数字2，不能继承源green标签作可辨绿灯；不给灯面off，也不画数字emitter。左body可辨左红箭头。远横灯待裁决。'),
322:('detailed_draft_return_for_arbitration',[
 b([1259,307,1320,330],'body_1'),ig([1643,430,1681,494],'ignore_1'),ig([1285,447,1307,477],'ignore_2','too_small')],
 '主灯共壳边界可辨，但只有数字2发光，灯面state=unknown/color_readable=false；不根据源green和倒计时颜色推断灯色。侧灯/远灯需kind裁决。'),
339:('detailed_draft_return_for_arbitration',[
 b([1381,224,1499,274],'body_1'),b([1520,220,1641,271],'body_2'),
 e([1392,234,1425,267],'left_arrow','body_1','red','arrow','left'),
 e([1531,229,1563,262],'red_circle','body_2','red'),
 neg([1376,181,1594,216],'negative_LED_text','辅助文字牌，未亮也不是信号灯'),
 ig([1743,376,1794,439],'ignore_1'),ig([1780,464,1836,508],'ignore_2','too_small')],
 '源off#1实际红圆灯+数字9，纠正为可辨red圆灯；保留两件独立横排共壳，数字不另标。远侧灯和小信号kind/外壳待裁决。'),
364:('detailed_draft_return_for_arbitration',[
 b([1048,418,1085,435],'body_1'),ig([1299,497,1327,544],'ignore_1','too_small')],
 '外壳尚可辨但仅数字发光，state=unknown/color_readable=false。不能标可辨green/off。侧面小目标留ignore，边界需复审。'),
390:('detailed_draft_return_for_arbitration',[
 b([516,290,582,455],'body_1','vertical'),b([581,289,649,454],'body_2','vertical'),
 b([1576,130,1749,202],'body_3'),b([1791,124,1920,198],'body_4',truncated=True),
 e([526,302,570,345],'left_arrow_near','body_1','red','arrow','left'),
 e([591,398,638,443],'green_circle_near','body_2','green'),
 e([1590,143,1636,187],'left_arrow_far','body_3','red','arrow','left'),
 e([1907,139,1920,188],'green_partial','body_4','green','unknown'),
 neg([1610,68,1920,113],'negative_LED_text','辅助LED文字；被图像右边截断'),
 ig([1235,490,1270,532],'ignore_1','too_small')],
 '源漏左侧两件竖排独立壳体，按可见分壳线分别补框，不用大框合包；右横壳被图像截断，只框可见区域。LED文字移出body。远灯仍待裁决。')}

def main():
    rows=list(csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig')))
    source=json.loads((O/'source_reference.json').read_text()); notes=json.loads((O/'visual_snapshot_0400.json').read_text())
    for i,(decision,objs,note) in special_records().items():
        rec={'schema_version':'0.1','label_version':'pc-ai-r1.0-20261024','candidate_id':rows[i]['sample_id'],
            'image_path':rows[i]['image_path'].replace('\\','/'),'image_sha256':rows[i]['sha256'],'image_size':[1920,1080],
            'reviewer':'Codex_PC_AI_stage2','reviewer_type':'AI','human_signoff':False,
            'recorded_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'review_status':'AI_first_pass_detailed_pending_independent',
            'actual_method':['unmarked full image / original-pixel upper road region',f'4x nearest-neighbor context crop review_stage2/zooms/{i:04d}.png'],
            'ai_disposition':decision,'complete_image_annotation':False,'eligible_for_yolo_export':False,
            'blocked_reason':'unresolved ignore regions / independent review and human confirmation pending',
            'objects':objs,'source_reference_only':source[i],'changes':[note],
            'first_screening_note':notes[i]['note'],'arbitration':[note],
            'unreadable_attributes_policy':'未单列且可确认的灯面不补off；仅数字发光时灯色unknown。所有control_relation=unknown。'}
        p=O/'first_pass'/f'{rows[i]["sample_id"]}.json'
        if not p.exists():p.write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
        else: rec=json.loads(p.read_text(encoding='utf-8'))
        im=Image.open(R/rows[i]['image_path']).convert('RGB');d=ImageDraw.Draw(im)
        for obj in rec['objects']:
            c={'body':'#00ff70','emitter':'#ffff00','ignore':'#ff40ff','hard_negative':'#ff9800'}[obj['type']]
            d.rectangle(obj['bbox_xyxy'],outline=c,width=2)
            d.text((obj['bbox_xyxy'][0],max(0,obj['bbox_xyxy'][1]-13)),obj['id'],fill=c)
        im.save(O/'overlays'/f'{rows[i]["sample_id"]}.jpg',quality=96)
    print('12 difficult-image decisions serialized; zero qualified training labels')
if __name__=='__main__':main()
