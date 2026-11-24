"""Consume genuine body-only decisions while preserving full-label disagreements."""
import json
import csv
from datetime import datetime, timezone
from pilot_clean_crops import ROOT, read, sha


def validate_scope(raw, task, annotation, request_sha):
    assert raw['candidate_id']==task['candidate_id']
    assert raw['request_sha256']==request_sha
    assert raw['image_sha256']==task['image_sha256']
    assert raw['reviewed_annotation_sha256']==task['annotation_sha256']
    assert raw['label_version']==task['label_version']
    assert raw['reviewer_type']=='AI' and raw['independent_from_first_pass'] is True
    assert raw['reviewer_id'] and raw['reviewer_id']!=task['first_pass_reviewer']
    assert raw.get('human_signoff') is False and raw.get('training_approval') is False
    assert raw['auxiliary_emitter_findings_preserved'] is True
    assert raw['attributes_accepted_for_training'] is False
    assert raw['body_detection_decision'] in ('accept','needs_modify','uncertain','exclude')
    assert raw['actual_method'] and raw['findings'] and raw['viewed_evidence']
    datetime.fromisoformat(raw['reviewed_at'])
    if raw['body_detection_decision']=='accept':
        assert all(o.get('kind') in ('motor_vehicle','pedestrian') for o in annotation['objects'] if o['type']=='body')
        assert all(raw.get(k) is True for k in ('body_full_original_checked','body_omission_search_completed',
            'body_kind_checked','body_bounds_checked','ignore_coverage_checked'))
        assert len(raw['confirmed_body_ids'])==len(set(raw['confirmed_body_ids']))
        assert len(raw['confirmed_ignore_ids'])==len(set(raw['confirmed_ignore_ids']))
        assert set(raw['confirmed_body_ids'])=={o['id'] for o in annotation['objects'] if o['type']=='body'}
        assert set(raw['confirmed_ignore_ids'])=={o['id'] for o in annotation['objects'] if o['type']=='ignore'}


def main():
    requests={sha(p):(p,read(p)) for p in (ROOT/'review_stage2').glob('body_detection_scope_r*/request.json')}
    rows={r['sample_id']:r for r in csv.DictReader((ROOT/'data/candidates.csv').open(encoding='utf-8-sig'))}
    originals=read(ROOT/'reports/independent_review_intake.json')
    valid=[];invalid=[]
    for p in (ROOT/'review_stage2/independent_body_detection_r1').glob('*.jsonl'):
        before=sha(p);checked=[]
        try:
            for n,line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(),1):
                if not line.strip():continue
                raw=json.loads(line);rp,request=requests[raw['request_sha256']]
                task=next(t for t in request['tasks'] if t['candidate_id']==raw['candidate_id'])
                assert sha(ROOT/task['image'])==task['image_sha256']
                assert sha(ROOT/task['annotation'])==task['annotation_sha256']
                annotation=read(ROOT/task['annotation'])
                validate_scope(raw,task,annotation,sha(rp))
                prior=task['prior_full_review']
                assert sha(ROOT/prior['file'])==prior['sha256']
                matching=[r for r in originals['reviews'] if r['candidate_id']==task['candidate_id']
                    and r['annotation_sha256']==task['annotation_sha256'] and r['image_sha256']==task['image_sha256']
                    and r['source_file']==prior['file'] and r['source_file_sha256']==prior['sha256'] and r['line']==prior['line']]
                assert len(matching)==1 and matching[0]['review_scope']=='whole_image'
                assert matching[0]['decision']==task['prior_full_label_decision']=='needs_modify'
                ids=[o['id'] for o in annotation['objects']];assert len(ids)==len(set(ids))
                w,h=annotation['image_size']
                for o in annotation['objects']:
                    x,y,u,v=o['bbox_xyxy'];assert 0<=x<u<=w and 0<=y<v<=h
                for e in raw['viewed_evidence']:assert sha(ROOT/e['path'])==e['sha256']
                checked.append({'candidate_id':task['candidate_id'],'annotation_sha256':task['annotation_sha256'],
                    'image_sha256':task['image_sha256'],'source_file':p.relative_to(ROOT).as_posix(),'source_file_sha256':before,
                    'line':n,'request':rp.relative_to(ROOT).as_posix(),'request_sha256':sha(rp),'raw':raw,'task':task,
                    'current_label_sha_matches':sha(ROOT/rows[task['candidate_id']]['annotation_file'])==task['annotation_sha256']})
            assert sha(p)==before
            valid.extend(checked)
        except (AssertionError,KeyError,ValueError,StopIteration,OSError) as error:
            invalid.append({'source_file':p.relative_to(ROOT).as_posix(),'error':type(error).__name__+': '+str(error),'counted':False})
    latest={}
    for v in sorted(valid,key=lambda v:v['raw']['reviewed_at']):
        if v['current_label_sha_matches']:latest[v['candidate_id']]=v
    fp=ROOT/'review_stage2/final_candidates_r1/manifest.json';final=read(fp)
    entries={e['candidate_id']:e for e in final['entries']};ledger_path=ROOT/final['two_AI_review_ledger']
    ledger=[json.loads(l) for l in ledger_path.read_text(encoding='utf-8').splitlines() if l.strip()]
    keys={(r['candidate_id'],r['independent_review_record']['reviewer_id'],r['independent_review_record']['reviewed_at']) for r in ledger}
    changed=False;confirmed=[];pending=[]
    for cid,v in latest.items():
        raw=v['raw'];task=v['task'];a=read(ROOT/task['annotation'])
        ref={'file':v['source_file'],'sha256':v['source_file_sha256'],'line':v['line']}
        key=(cid,raw['reviewer_id'],raw['reviewed_at'])
        if key not in keys:
            ledger.append({'candidate_id':cid,'first_pass':{'file':task['annotation'],'sha256':task['annotation_sha256'],
                'reviewer_id':task['first_pass_reviewer'],'reviewer_type':'AI','reviewed_at':task['first_pass_recorded_at']},
                'independent_review_source':ref,'independent_review_record':raw,'review_scope':'body_detection_only'})
            keys.add(key);changed=True
        if raw['body_detection_decision']!='accept':
            pending.append(cid)
            if entries.get(cid,{}).get('label_status')=='body_only_confirmed_auxiliary_disagreements_preserved':
                del entries[cid];changed=True
            continue
        e={'candidate_id':cid,'image_sha256':task['image_sha256'],'annotation_file':task['annotation'],
           'annotation_sha256':task['annotation_sha256'],'label_version':a['label_version'],
           'first_pass_reviewer':task['first_pass_reviewer'],'independent_reviewer':raw['reviewer_id'],
           'independent_review_source':ref,'confirmed_body_ids':raw['confirmed_body_ids'],'retained_ignore_ids':raw['confirmed_ignore_ids'],
           'label_status':'body_only_confirmed_auxiliary_disagreements_preserved','body_scope_reviewed_at':raw['reviewed_at'],
           'prior_full_label_review':task['prior_full_review'],'prior_full_label_decision':'needs_modify',
           'original_auxiliary_findings':task['prior_findings_preserved'],'auxiliary_attributes_accepted_for_training':False,
           'confirmation_scope':'Genuine explicit body/ignore whole-original review on exact unchanged SHA. Auxiliary emitter/color/arrow disagreements stay unresolved and are NOT detection training targets.',
           'body_attribute_unknown_is_not_a_detection_blocker':True,
           'standard_full_image_yolo_label_compatible':bool(raw['confirmed_body_ids']) and not raw['confirmed_ignore_ids'],
           'independent_findings':raw['findings'],'human_signoff':False,'AI_records_represented_as_human':False,'training_release':False}
        if entries.get(cid)!=e:entries[cid]=e;changed=True
        confirmed.append(cid)
    if changed:
        hist=fp.parent/'history';hist.mkdir(exist_ok=True);snapshot=hist/(sha(fp)+'.json')
        if not snapshot.exists():snapshot.write_bytes(fp.read_bytes())
        ledger_path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in ledger),encoding='utf-8')
        final.update(recorded_at=datetime.now(timezone.utc).isoformat(),entries=sorted(entries.values(),key=lambda e:e['candidate_id']),
            final_label_candidates=len(entries),final_body_label_confirmed_images=sum(bool(e['confirmed_body_ids']) for e in entries.values()),
            confirmed_body_count=sum(len(e['confirmed_body_ids']) for e in entries.values()),
            confirmed_ignore_only_exclusions=sum(not e['confirmed_body_ids'] for e in entries.values()),
            standard_full_image_yolo_label_compatible_images=sum(e['standard_full_image_yolo_label_compatible'] for e in entries.values()),
            two_AI_review_ledger_sha256=sha(ledger_path),version_bound_review_records_preserved=len(ledger))
        fp.write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'body_scope_confirmed_ids':confirmed,
        'body_scope_pending_ids':pending,'body_scope_confirmed_images':len(confirmed),'invalid_or_in_progress_files':invalid,
        'new_whole_image_independent_image_count':0,'old_full_label_decisions_not_rewritten':True,
        'auxiliary_disagreements_not_accepted_for_training':True,'reviews':valid,'training_release':False}
    (ROOT/'reports/body_detection_scope_intake.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('body_scope_confirmed_images','body_scope_pending_ids','invalid_or_in_progress_files')}))


if __name__=='__main__':main()
