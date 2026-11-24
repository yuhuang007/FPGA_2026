"""Freeze public-label reuse plus existing safe crops; never approves or trains."""
import collections
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
import yaml
from source_partial_yolo import validate_release_entries

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out=ROOT/'datasets/public_body_r1';assert not out.exists(),'Frozen versions are immutable'
    for split in ('train','val','holdout'):
        for kind in ('images','labels'):(out/kind/split).mkdir(parents=True,exist_ok=True)
    china=read(ROOT/'reports/s2tld720_structure_audit_r1.json')
    tlony=read(ROOT/'reports/tlony_structure_audit_r1.json')
    intake=read(ROOT/'reports/tlony_source_intake_r1.json')
    legacy=read(ROOT/'datasets/clean_body_r3/manifest.json')
    groups={e['candidate_id']:e for e in read(ROOT/'data/group_releases/r4/manifest.json')['groups']}
    china_group=next(e['leakage_group'] for e in legacy['entries'] if e['candidate_id'].startswith('s2tld1080_'))
    entries=[];excluded=[];seen=set()

    def append(cid,canonical,split,group,policy,data,suffix,lines,source):
        digest=hashlib.sha256(data).hexdigest()
        if digest in seen:
            excluded.append({'candidate_id':cid,'reason':'Exact image bytes duplicate an already included original'});return
        seen.add(digest);image=out/'images'/split/(cid+suffix);image.write_bytes(data)
        label=out/'labels'/split/(cid+'.txt');label.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        entries.append({'candidate_id':cid,'canonical_original_id':canonical,'split':split,'leakage_group':group,
            'supervision':policy,'image_absolute':image.as_posix(),'image':image.relative_to(ROOT).as_posix(),
            'label':label.relative_to(ROOT).as_posix(),'image_sha256':digest,'label_sha256':sha(label),
            'body_count':len(lines),'source':source})

    acquisition=read(ROOT/'data/public_datasets/s2tld720_r1/acquisition_manifest.json')
    archive=ROOT/'data/public_datasets/s2tld720_r1/s2tld720.zip'
    assert acquisition['verified'] and sha(archive)==acquisition['actual_sha256']
    with zipfile.ZipFile(archive) as z:
        for e in china['entries']:
            if e['storage_subset']!='normal_1':continue
            w,h=e['image_size'];lines=[]
            for o in e['objects']:
                assert o['source_class'] in ('red','green','yellow','off')
                x,y,u,v=o['bbox_xyxy'];assert 0<=x<u<=w and 0<=y<v<=h
                lines.append(f'0 {(x+u)/2/w:.9f} {(y+v)/2/h:.9f} {(u-x)/w:.9f} {(v-y)/h:.9f}')
            assert lines and hashlib.sha256(z.read(e['source_annotation_member'])).hexdigest()==e['source_annotation_sha256']
            append(e['candidate_id'],'S2TLD720:'+e['source_image_member'],'train',china_group,'positive_only',
                z.read(e['source_image_member']),'.jpg',lines,{'family':'S2TLD720_native_day','archive':archive.relative_to(ROOT).as_posix(),
                'image_member':e['source_image_member'],'annotation_member':e['source_annotation_member'],
                'annotation_sha256':e['source_annotation_sha256'],'supervision_scope':'Published motor-body positives; all other image/class terms unknown. Color classes are not state truth.'})
    excluded_images={e['image'] for e in intake['temporarily_excluded']}
    for e in tlony['entries']:
        if e['image'] in excluded_images:
            excluded.append({'candidate_id':Path(e['image']).stem,'reason':'Known source kind/geometry dispute; entire original withheld','source_image':e['image']});continue
        label=ROOT/e['label'];image=ROOT/e['image'];lines=[];invalid=False
        for line in label.read_text(encoding='utf-8').splitlines():
            if not line.strip():continue
            c,x,y,w,h=map(float,line.split());assert c.is_integer() and 0<=c<=7
            # Withhold a whole photo for substantive source overhang, rather
            # than silently deleting/clamping a troublesome body annotation.
            iw,ih=e['image_size']
            if min((x-w/2)*iw,(y-h/2)*ih)<-1 or max((x+w/2)*iw-iw,(y+h/2)*ih-ih)>1:invalid=True
            lines.append(str(0 if c<5 else 1)+' '+line.split(maxsplit=1)[1])
        if invalid:
            excluded.append({'candidate_id':image.stem,'reason':'Native bbox extends materially beyond photo; whole original withheld','source_image':e['image']});continue
        append('tlony_'+image.stem,'TLoNY:'+image.stem,'train','TLoNY_Manhattan_unresolved_joint_train','complete',
            image.read_bytes(),image.suffix,lines,{'family':'TLoNY_native','image':e['image'],'annotation':e['label'],
            'annotation_sha256':sha(label),'supervision_scope':'Source-author annotations reused following sampled taxonomy/body-scope audit; not individually two-AI confirmed.'})
    for e in legacy['entries']:
        image=ROOT/e['crop_file'];label=ROOT/e['yolo_label_file']
        assert sha(image)==e['crop_sha256'] and sha(label)==e['yolo_label_sha256']
        g=groups[e['candidate_id']];assert g['official_split']==e['split'] and g['leakage_group']==e['leakage_group']
        append(e['candidate_id'],e['canonical_original_id'],e['split'],e['leakage_group'],'complete',image.read_bytes(),image.suffix,
            label.read_text(encoding='utf-8').splitlines(),{'family':'legacy_verified_clean_crop','original_image_sha256':e['source_image_sha256'],
            'crop_file':e['crop_file'],'annotation_sha256':e['source_annotation_sha256'],'legacy_registry_sources':legacy['registry_sources'],
            'supervision_scope':'Actual SHA-bound body/ignore reviews and pixel/geometry/visual validated clean crop; one original counted once.'})
    validate_release_entries(entries)
    lists={}
    for split in ('train','val','holdout'):
        chosen=[e for e in entries if e['split']==split];p=out/(split+'.txt')
        p.write_text(''.join(e['image_absolute']+'\n' for e in chosen),encoding='utf-8')
        lists[split]={'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'originals':len(chosen)}
    config={'path':ROOT.as_posix(),'train':(out/'train.txt').as_posix(),'val':(out/'val.txt').as_posix(),
        'nc':2,'names':{0:'motor_vehicle_body',1:'pedestrian_body'}}
    yp=out/'data.yaml';yp.write_text(yaml.safe_dump(config,sort_keys=False),encoding='utf-8')
    refs=['reports/s2tld720_structure_audit_r1.json','reports/tlony_source_intake_r1.json','datasets/clean_body_r3/manifest.json',
        'review_stage2/public_dataset_compatibility_r2/request.json','reports/source_partial_loss_validation_r1.json',
        'scripts/source_partial_yolo.py','data/group_releases/r4/manifest.json']
    family=collections.Counter(e['source']['family'] for e in entries);classes=collections.Counter()
    for e in entries:
        for line in (ROOT/e['label']).read_text(encoding='utf-8').splitlines():classes[(e['split'],int(line.split()[0]))]+=1
    result={'recorded_at':datetime.now(timezone.utc).isoformat(),'release_id':'public_body_r1','route':'source_positive_only_for_sparse_images',
        'entries':entries,'unique_originals':len(entries),'train_val_originals':sum(e['split'] in ('train','val') for e in entries),
        'body_targets':sum(e['body_count'] for e in entries),'family_counts':dict(family),
        'class_counts':{s:{str(c):classes[s,c] for c in (0,1)} for s in ('train','val','holdout')},
        'file_lists':lists,'yaml':yp.relative_to(ROOT).as_posix(),'yaml_sha256':sha(yp),'excluded_originals':excluded,
        'evidence':[{'path':p,'sha256':sha(ROOT/p)} for p in refs],
        'source_photo_counts_not_per_image_independent_rechecks':True,'independent_sample_and_implementation_review_pending':True,
        'all_legacy_unselected_originals_excluded_from_this_release_not_relabelled_background':True,
        'night_normal2_originals_deferred':3785,'holdout_in_tuning_yaml':False,'training_started':False,
        'global_training_release':False,'validation_scope':'Five complete safe external source originals only; insufficient China-domain precision evidence. No sparse-source mAP and no final-test tuning.',
        'augmentation':{'mosaic':0.,'mixup':0.,'copy_paste':0.,'degrees':0.,'translate':0.,'scale':0.,'shear':0.,'perspective':0.,'flipud':0.,'fliplr':.5,'multi_scale':False,'rect':False}}
    (out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('unique_originals','train_val_originals','body_targets','family_counts','class_counts')}))
    print('withheld source originals',len(excluded))


if __name__=='__main__':main()
