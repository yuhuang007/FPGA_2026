"""Validate actual crop pixels, every object, YOLO coordinate round trips and loader."""
import json, hashlib, argparse, re
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from PIL import Image
from pilot_clean_crops import ROOT, read, sha, intersects, contains, CLASSES

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--version',default='r2')
    ap.add_argument('--manifest');ap.add_argument('--report');args=ap.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*',args.version)
    path=ROOT/args.manifest if args.manifest else ROOT/f'review_stage2/clean_crop_pilot_{args.version}/manifest.json'
    m=read(path);results=[]
    groups={}
    if m.get('original_split_release_verified'):
        gp=ROOT/m['original_group_release'];assert sha(gp)==m['original_group_release_sha256']
        groups={g['candidate_id']:g for g in read(gp)['groups']}
    for e in m['entries']:
        if 'crop_file' not in e:continue
        assert sha(ROOT/e['source_annotation'])==e['source_annotation_sha256']
        assert sha(ROOT/e['source_image'])==e['source_image_sha256']
        assert sha(ROOT/e['crop_file'])==e['crop_sha256']
        assert sha(ROOT/e['yolo_label_file'])==e['yolo_label_sha256']
        if groups:
            g=groups[e['candidate_id']]
            assert g['image_sha256']==e['source_image_sha256'] and g['annotation_sha256']==e['source_annotation_sha256']
            assert g['official_split']==e['inherited_split'] and g['leakage_group']==e['inherited_group']
            assert e['split_assigned_before_derivation'] and not g.get('redundant_capture_of')
        a=read(ROOT/e['source_annotation']);c=e['crop_xyxy'];w,h=e['size']
        actual=np.asarray(Image.open(ROOT/e['crop_file']).convert('RGB'))
        expected=np.asarray(Image.open(ROOT/e['source_image']).convert('RGB').crop(c))
        assert np.array_equal(actual,expected), 'Crop must preserve exact original pixels'
        for obstacle in e['obstacles']:assert not intersects(c,obstacle['padded_bbox'])
        bodies=[o for o in a['objects'] if o['type']=='body' and intersects(c,o['bbox_xyxy'])]
        assert {o['id'] for o in bodies}=={t['source_id'] for t in e['targets']}
        for o in a['objects']:
            if o['type'] in ('ignore','body','emitter','lens') and intersects(c,o['bbox_xyxy']):
                assert contains(c,o['bbox_xyxy']), 'No partial signal component is allowed'
                if o['type'] in ('emitter','lens'):assert o.get('parent_id') in {b['id'] for b in bodies}
                assert o['type']!='ignore'
        lines=(ROOT/e['yolo_label_file']).read_text().splitlines();assert len(lines)==len(e['targets'])
        error=0
        for line,t in zip(lines,e['targets']):
            cls,cx,cy,bw,bh=map(float,line.split());assert int(cls)==CLASSES[t['kind']]
            recovered=[(cx-bw/2)*w,(cy-bh/2)*h,(cx+bw/2)*w,(cy+bh/2)*h]
            error=max(error,max(abs(x-y) for x,y in zip(recovered,t['bbox_xyxy'])))
        assert error<1e-5
        results.append({'candidate_id':e['candidate_id'],'pixel_exact':True,'all_intersecting_bodies_included':True,
            'ignore_and_partial_signal_intersections':0,'yolo_roundtrip_max_native_pixel_error':error,
            'body_count':len(bodies)})
    # Exercise the installed standard YOLO reader, with no synthetic split or training.
    from ultralytics.data.dataset import YOLODataset
    ds=YOLODataset(img_path=str(path.parent/'images'),imgsz=640,batch_size=2,augment=False,
        data={'names':{0:'motor_vehicle_body',1:'pedestrian_body'},'nc':2},cache=False)
    loaded=[]
    for i in range(len(ds)):
        sample=ds[i];assert tuple(sample['img'].shape)==(3,640,640)
        assert (sample['bboxes']>=0).all() and (sample['bboxes']<=1).all()
        assert len(sample['bboxes'])==len(ds.labels[i]['bboxes'])
        loaded.append({'file':Path(sample['im_file']).name,'targets':len(sample['cls'])})
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'pilot_manifest':path.relative_to(ROOT).as_posix(),
        'pilot_manifest_sha256':sha(path),'passed':True,'originals':len(results),
        'targets':sum(r['body_count'] for r in results),'checks':results,
        'standard_yolo_640_loader':{'passed':True,'loaded':loaded,'augment':False,'training_started':False},
        'does_not_release_splits_or_training':True}
    report['original_group_release_sha256']=m.get('original_group_release_sha256')
    dest=ROOT/args.report if args.report else ROOT/f'reports/clean_crop_validation_{args.version}.json'
    assert not dest.exists(), 'Validation evidence is immutable; select a new report'
    dest.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'originals':report['originals'],'targets':report['targets'],'loader':'standard YOLO, 640 square'}))

if __name__=='__main__':main()
