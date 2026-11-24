"""Fail-closed small crop pilot; never assigns splits or promotes originals.

Only exact-SHA independently confirmed labels are eligible.  Source ignores,
standalone emitters, unconfirmed/unsupported bodies and truncated bodies are
obstacles.  Output labels describe every complete body in a crop, not its anchor.
"""
import argparse, csv, hashlib, itertools, json, math
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CLASSES = {'motor_vehicle': 0, 'pedestrian': 1}
DEFAULT_IDS = ['0000','0012','0013','0016','0215','0285','0339','0390']

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def area(b): return (b[2]-b[0])*(b[3]-b[1])
def intersects(a,b): return min(a[2],b[2])>max(a[0],b[0]) and min(a[3],b[3])>max(a[1],b[1])
def contains(a,b): return a[0]<=b[0] and a[1]<=b[1] and a[2]>=b[2] and a[3]>=b[3]
def padded(b,w,h,p): return [max(0,b[0]-p),max(0,b[1]-p),min(w,b[2]+p),min(h,b[3]+p)]

def candidates(a,e):
    w,h=a['image_size']; confirmed=set(e['confirmed_body_ids'])
    bodies=[o for o in a['objects'] if o['type']=='body' and o['id'] in confirmed
            and o.get('kind') in CLASSES and not o.get('truncated',False)]
    good={o['id'] for o in bodies}
    obstacles=[]
    for o in a['objects']:
        if (o['type']=='ignore' or (o['type']=='body' and o['id'] not in good)
                or (o['type'] in ('emitter','lens') and o.get('parent_id') not in good)):
            b=o['bbox_xyxy'];p=max(12,min(32,math.ceil(.2*max(b[2]-b[0],b[3]-b[1]))))
            obstacles.append({'id':o['id'],'source_bbox':b,'padded_bbox':padded(b,w,h,p),'padding':p})
    # Boundary candidates lie on padded obstacle edges. Body edges additionally
    # allow excluding a complete body without introducing a partial target.
    xs={0,w};ys={0,h}
    for b in [o['padded_bbox'] for o in obstacles]+[padded(o['bbox_xyxy'],w,h,32) for o in bodies]:
        xs.update((b[0],b[2]));ys.update((b[1],b[3]))
    options={}
    # Keep the obstacle grid fixed. Recursively expanding each axis from all
    # pairs of the other axis caused combinatorial growth on multi-body scenes.
    # Aspect-constrained variants are clipped within each base rectangle.
    minwidth=math.ceil(w*.1875);minheight=math.ceil(h/3)
    def rectangles():
        for x,u in itertools.combinations(sorted(xs),2):
            if u-x<minwidth:continue
            for y,v in itertools.combinations(sorted(ys),2):
                cw,ch=u-x,v-y
                if ch<minheight or cw*ch<.15*w*h:continue
                if .5<=cw/ch<=2.5:
                    yield [x,y,u,v]
                elif cw/ch>2.5:
                    width=math.floor(2.5*ch)
                    starts={x,u-width}
                    for o in bodies:
                        b=o['bbox_xyxy'];starts.add(max(x,min(u-width,math.floor((b[0]+b[2]-width)/2))))
                    for left in starts:yield [left,y,left+width,v]
                else:
                    height=2*cw
                    starts={y,v-height}
                    for o in bodies:
                        b=o['bbox_xyxy'];starts.add(max(y,min(v-height,math.floor((b[1]+b[3]-height)/2))))
                    for top in starts:yield [x,top,u,top+height]
    for c in rectangles():
            x,y,u,v=c;cw,ch=u-x,v-y
            if ch<minheight or not .5<=cw/ch<=2.5 or area(c)<.15*w*h:continue
            if any(intersects(c,o['padded_bbox']) for o in obstacles):continue
            included=[];bad=False
            for o in bodies:
                b=o['bbox_xyxy']
                if not intersects(c,b):continue
                # One body width of lateral context and half a body height
                # vertically, each at least 32 native pixels. Never cut bodies.
                px=max(32,b[2]-b[0]);py=max(32,math.ceil(.5*(b[3]-b[1])))
                # An original frame may provide less context than the nominal
                # margin. Preserve all available context at that original edge;
                # do not reject a complete, reviewed head merely because pixels
                # outside the source photo do not exist.
                needed=[max(0,b[0]-px),max(0,b[1]-py),min(w,b[2]+px),min(h,b[3]+py)]
                if not contains(c,needed):bad=True;break
                included.append(o)
            if bad or not included:continue
            scale=640/max(cw,ch)
            if any(min(o['bbox_xyxy'][2]-o['bbox_xyxy'][0],o['bbox_xyxy'][3]-o['bbox_xyxy'][1])*scale<4 for o in included):continue
            options[tuple(c)]=(len(included),area(c),included)
    if not options:return None,obstacles
    c,(_,_,included)=max(options.items(),key=lambda t:(t[1][0],t[1][1],t[0]))
    return {'crop_xyxy':list(c),'bodies':included},obstacles

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ids',nargs='+',default=DEFAULT_IDS)
    ap.add_argument('--output',default='review_stage2/clean_crop_pilot_r1')
    ap.add_argument('--scan-selected-only',action='store_true',help='Limit geometry scan to requested originals; never bulk convert.')
    ap.add_argument('--production',action='store_true',help='Require SHA-bound released original groups/splits; create reviewable export, never start training.')
    args=ap.parse_args();out=ROOT/args.output
    # Published pilots are immutable; make a new version instead of overwriting.
    if (out/'manifest.json').exists():raise SystemExit('Pilot exists; select a new --output version')
    out.mkdir(parents=True,exist_ok=True)
    for d in ['images','labels','views']:(out/d).mkdir(exist_ok=True)
    final_path=ROOT/'review_stage2/final_candidates_r1/manifest.json';final=read(final_path)
    external_path=ROOT/'reports/external_scene_review_intake.json'
    external=read(external_path) if external_path.exists() else {'entries':[]}
    combined=final['entries']+external['entries']
    groups={x['candidate_id']:x for x in read(ROOT/'data/conservative_groups_r2.json')['groups']}
    rows={r['sample_id']:r for r in csv.DictReader((ROOT/'data/candidates.csv').open(encoding='utf-8-sig'))}
    wanted={'s2tld1080_'+x if not x.startswith(('s2tld','coco_scene','oi_scene','commons_scene')) else x for x in args.ids}
    if args.production:
        released=read(ROOT/'data/released_original_groups.json')
        assert released['official_split_released'] is True
        assert sha(ROOT/released['immutable_release'])==released['immutable_release_sha256']
        groups={x['candidate_id']:x for x in released['groups']}
    entries=[];geometry=[]
    for e in combined:
        if not e['confirmed_body_ids']:continue
        if args.scan_selected_only and e['candidate_id'] not in wanted:continue
        p=ROOT/e['annotation_file'];a=read(p);image=ROOT/a['image_path']
        assert sha(p)==e['annotation_sha256']
        if e['candidate_id'] in rows:assert sha(p)==sha(ROOT/rows[e['candidate_id']]['annotation_file'])
        assert sha(image)==e['image_sha256']==a['image_sha256']
        if a.get('license_status','').startswith('quarantine') or a.get('planned_split','').startswith('quarantine'):
            if e['candidate_id'] in wanted:
                entries.append({'candidate_id':e['candidate_id'],'status':'source_quality_or_license_quarantine','training_release':False})
            continue
        chosen,obstacles=candidates(a,e)
        geometry.append({'candidate_id':e['candidate_id'],'confirmed_bodies':len(e['confirmed_body_ids']),
            'geometrically_retained_bodies':len(chosen['bodies']) if chosen else 0,
            'has_candidate':bool(chosen),'visual_validation':'not_performed_for_geometry_scan'})
        if e['candidate_id'] not in wanted:continue
        g=groups.get(e['candidate_id'],{'leakage_group':e.get('scene_id'),'official_split':'unassigned'})
        if args.production:
            assert g['official_split'] in ('train','val','holdout') and g['group_status']=='verified'
            assert g['image_sha256']==e['image_sha256'] and g['annotation_sha256']==e['annotation_sha256']
            assert not g.get('redundant_capture_of'), 'Redundant captures do not qualify'
        if not chosen:
            entries.append({'candidate_id':e['candidate_id'],'status':'no_safe_context_crop','obstacles':obstacles});continue
        c=chosen['crop_xyxy'];cw,ch=c[2]-c[0],c[3]-c[1];scale=640/max(cw,ch)
        im=Image.open(image).convert('RGB');crop=im.crop(c)
        stem=e['candidate_id']+'_clean01';cp=out/'images'/f'{stem}.png';lp=out/'labels'/f'{stem}.txt'
        crop.save(cp);labels=[];targets=[]
        for o in chosen['bodies']:
            x,y,u,v=o['bbox_xyxy'];b=[x-c[0],y-c[1],u-c[0],v-c[1]]
            labels.append(f"{CLASSES[o['kind']]} {(b[0]+b[2])/2/cw:.9f} {(b[1]+b[3])/2/ch:.9f} {(u-x)/cw:.9f} {(v-y)/ch:.9f}")
            targets.append({'source_id':o['id'],'kind':o['kind'],'bbox_xyxy':b,
                'native_size':[u-x,v-y],'at_640_letterbox_size':[(u-x)*scale,(v-y)*scale],
                'source_truncated':False,'new_truncation':False})
        lp.write_text('\n'.join(labels)+'\n',encoding='utf-8')
        view=im.copy();dr=ImageDraw.Draw(view)
        for o in a['objects']:
            if o['type'] not in ('ignore','body'):continue
            dr.rectangle(o['bbox_xyxy'],outline='red' if o['type']=='ignore' else 'lime',width=3)
        dr.rectangle(c,outline='cyan',width=5);view.thumbnail((960,540));vp=out/'views'/f'{stem}_source.jpg';view.save(vp,quality=90)
        overlay=crop.copy();dr=ImageDraw.Draw(overlay)
        for t in targets:dr.rectangle(t['bbox_xyxy'],outline='lime',width=2);dr.text((t['bbox_xyxy'][0],max(0,t['bbox_xyxy'][1]-14)),t['source_id'],fill='lime')
        overlay.thumbnail((960,720));op=out/'views'/f'{stem}_crop.jpg';overlay.save(op,quality=92)
        entries.append({'candidate_id':e['candidate_id'],'source_image':a['image_path'],'source_image_sha256':sha(image),
            'source_annotation':e['annotation_file'],'source_annotation_sha256':sha(p),'source_label_version':a['label_version'],
            'crop_xyxy':c,'size':[cw,ch],'retained_area_fraction':area(c)/area([0,0,*a['image_size']]),
            'body_count_original':len(e['confirmed_body_ids']),'body_count_retained':len(targets),'targets':targets,
            'letterbox_scale_640':scale,'magnification_vs_full_image_640':max(a['image_size'])/max(cw,ch),
            'obstacles':obstacles,'ignore_intersections':0,'partial_body_intersections':0,
            'crop_file':cp.relative_to(ROOT).as_posix(),'crop_sha256':sha(cp),'yolo_label_file':lp.relative_to(ROOT).as_posix(),
            'yolo_label_sha256':sha(lp),'source_view':vp.relative_to(ROOT).as_posix(),'crop_view':op.relative_to(ROOT).as_posix(),
            'inherited_group':g['leakage_group'],'inherited_split':g['official_split'],
            'split_assigned_before_derivation':g['official_split'] in ('train','val','holdout'),
            'status':'pilot_pending_visual_check','training_release':False})
    report={'schema_version':'clean_crop_pilot_v1','recorded_at':datetime.now(timezone.utc).isoformat(),
        'source_final_manifest':final_path.relative_to(ROOT).as_posix(),'source_final_manifest_sha256':sha(final_path),
        'purpose':('Split-bound reviewable clean export; training gates remain separately enforced.' if args.production else
            'Small actual crop pilot only. No dataset split, no qualification promotion, no bulk conversion.'),
        'original_split_release_verified':bool(args.production),
        'original_group_release':released['immutable_release'] if args.production else None,
        'original_group_release_sha256':released['immutable_release_sha256'] if args.production else None,
        'source_external_final_register':external_path.relative_to(ROOT).as_posix(),
        'source_external_final_register_sha256':sha(external_path) if external_path.exists() else None,
        'rules':{'ignore_padding':'max(12px,min(32px,20% longest region side))','minimum_crop':'width>=18.75% original width; height>=one third original height (360x360 for1920x1080)',
            'minimum_source_area_fraction':.15,'minimum_body_short_side_at_640':4,
            'minimum_context':'x=max(32px,body width), y=max(32px,half body height), capped at the original image boundary; source-truncated bodies remain excluded',
            'selection':'maximize retained whole bodies then source area; one crop per original',
            'unparented_emitters_and_unsupported_or_truncated_bodies':'padded obstacles',
            'augmentation':'standard YOLO sees only clean pixels and all included body boxes; no mask/ignore custom loss',
            'split':'Pilot only while unassigned. Production derivation must require original split before crop creation.',
            'qualification_unit':'unique original images, never count crops as additional originals'},
        'entries':entries,'geometry_only_scan':geometry,'geometry_scan_selected_only':args.scan_selected_only,
        'class_names':['motor_vehicle_body','pedestrian_body'],'training_release':False}
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pilot_crops':sum('crop_file' in e for e in entries),'pilot_originals':len(entries),
        'pilot_retained_bodies':sum(e.get('body_count_retained',0) for e in entries),
        'geometry_only_originals_with_candidate':sum(g['has_candidate'] for g in geometry),
        'geometry_only_retained_bodies':sum(g['geometrically_retained_bodies'] for g in geometry)}))

if __name__=='__main__':main()
