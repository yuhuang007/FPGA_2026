"""Build immutable explicit file lists from qualified originals, never glob crops."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
import yaml
from pilot_clean_crops import ROOT, read, sha
from qualify_clean_originals import qualification_entries, assert_unique_originals
from current_data_holds import current_holds


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
    out=ROOT/args.output;assert not out.exists(),'Published dataset versions are immutable'
    ready=read(ROOT/'reports/readiness.json');entries=[];sources=[]
    holds, hold_source = current_holds()
    assert hold_source == ready.get('integrity_hold_source'), 'Refresh readiness after hold changes'
    for ref in ready['qualification_registries']:
        p=ROOT/ref['path'];assert sha(p)==ref['sha256'];r=read(p)
        for key in ('production_manifest','validation','visual_QA'):
            assert sha(ROOT/r[key])==r[key+'_sha256']
        active_ids=set(ref['active_candidate_ids'])
        assert not active_ids & set(holds)
        verified=qualification_entries(ROOT/r['production_manifest'],ROOT/r['validation'],ROOT/r['visual_QA'],candidate_ids=active_ids)
        assert verified==[e for e in r['entries'] if e['candidate_id'] in active_ids]
        entries.extend(e for e in verified if e['candidate_id'] not in holds);sources.append(ref)
    assert_unique_originals(entries)
    assert {e['candidate_id'] for e in entries}==set(ready['qualified_original_ids'])
    assert {'train','val'}<={e['split'] for e in entries}
    out.mkdir(parents=True)
    files={}
    for split in ('train','val','holdout'):
        selected=[e for e in entries if e['split']==split]
        if not selected:continue
        p=out/(split+'.txt')
        p.write_text(''.join((ROOT/e['crop_file']).as_posix()+'\n' for e in selected),encoding='utf-8')
        files[split]={'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'unique_originals':len(selected)}
    config={'path':ROOT.as_posix(),'train':(out/'train.txt').as_posix(),'val':(out/'val.txt').as_posix(),
            'names':{0:'motor_vehicle_body',1:'pedestrian_body'},'nc':2}
    # Heldout final-test samples are deliberately absent from tuning YAML.
    yp=out/'data.yaml';yp.write_text(yaml.safe_dump(config,sort_keys=False,allow_unicode=True),encoding='utf-8')
    classes=Counter((e['split'],t['kind']) for e in entries for t in e['targets'])
    manifest={'recorded_at':datetime.now(timezone.utc).isoformat(),'route':'context_preserving_clean_crops_standard_YOLO',
              'registry_sources':sources,'yaml':yp.relative_to(ROOT).as_posix(),'yaml_sha256':sha(yp),'file_lists':files,
              'unique_originals':len(entries),'body_targets':sum(e['body_count'] for e in entries),
              'class_counts':{s:{k:classes[s,k] for k in ('motor_vehicle','pedestrian')} for s in files},
              'entries':entries,'explicit_lists_only_no_directory_globs':True,
              'failed_crop_release_r2_never_included':True,'holdout_in_tuning_yaml':False,
              'integrity_hold_source':hold_source, 'withheld_integrity_hold_ids':sorted(holds),
              'global_training_ready_at_creation':ready['ready_to_train'],'training_started':False,
              'initial_geometry_augmentation':read(ROOT/'reports/ignore_handling_decision.json')['standard_yolo_initial_geometry_augmentation']}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'dataset':args.output,'unique_originals':len(entries),'body_targets':manifest['body_targets'],
                      'splits':{k:v['unique_originals'] for k,v in files.items()},'training_started':False}))


if __name__=='__main__':main()
