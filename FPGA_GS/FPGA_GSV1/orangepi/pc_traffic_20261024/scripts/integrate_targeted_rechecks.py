"""Extend final body-label register only from genuine current-SHA recheck accepts."""
from pathlib import Path
from datetime import datetime, timezone
import csv, json, hashlib, zipfile
from integrate_formal_reviews import structural_check

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,a):p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    intake=read(R/'reports/independent_review_intake.json')
    path=R/'review_stage2/final_candidates_r1/manifest.json';final=read(path)
    rows={r['sample_id']:r for r in csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig'))}
    tasks={t['candidate_id']:t for t in read(R/'review_stage2/targeted_recheck_20261025/task_index.json')['tasks']}
    followup=R/'review_stage2/targeted_recheck_20261025/geometry_followup_0012.json'
    if followup.exists():
        task=read(followup);tasks[task['candidate_id']]=task
    entries={e['candidate_id']:e for e in final['entries'] if sha(R/rows[e['candidate_id']]['annotation_file'])==e['annotation_sha256']}
    ledger_path=R/final['two_AI_review_ledger']
    ledger=[json.loads(l) for l in ledger_path.read_text(encoding='utf-8').splitlines()]
    ledger_keys={(v['candidate_id'],v['independent_review_record']['reviewed_annotation_sha256'],v['independent_review_record']['reviewer_id']) for v in ledger}
    revision_labels={sha(p):p for p in (R/'review_stage2/revisions').glob('*/labels/*.json')}
    for review in intake['reviews']:
        if review.get('review_scope')!='targeted_changes':continue
        key=(review['candidate_id'],review['annotation_sha256'],review['reviewer_id'])
        if key in ledger_keys:continue
        source=R/review['source_file'];assert sha(source)==review['source_file_sha256']
        raw=json.loads(source.read_text(encoding='utf-8-sig').splitlines()[review['line']-1])
        p=revision_labels[review['annotation_sha256']];a=read(p)
        ledger.append({'candidate_id':review['candidate_id'],'first_pass':{'file':p.relative_to(R).as_posix(),
            'sha256':sha(p),'reviewer_id':a['reviewer'],'reviewer_type':'AI','reviewed_at':a['recorded_at']},
            'independent_review_source':{'file':review['source_file'],'sha256':review['source_file_sha256'],'line':review['line']},
            'independent_review_record':raw})
        ledger_keys.add(key)
    disp_path=R/'reports/pc_sample_dispositions.json';disp=read(disp_path)
    accepted=[]
    for sid,task in tasks.items():
        label_path=R/rows[sid]['annotation_file'];h=sha(label_path)
        assert h==task['annotation_sha256']
        reviews=[v for v in intake['reviews'] if v['candidate_id']==sid and v['annotation_sha256']==h]
        if not reviews:continue
        review=max(reviews,key=lambda r:r['reviewed_at'])
        if review['decision']!='accept':continue
        source=R/review['source_file'];assert sha(source)==review['source_file_sha256']
        raw=json.loads(source.read_text(encoding='utf-8-sig').splitlines()[review['line']-1])
        a=read(label_path);structural_check(a)
        assert raw['reviewed_annotation_sha256']==h and raw['reviewer_id']!=a['reviewer']
        assert raw['independent_from_first_pass'] and not raw.get('human_signoff')
        bodies=[o['id'] for o in a['objects'] if o['type']=='body'];ignores=[o['id'] for o in a['objects'] if o['type']=='ignore']
        binding={'file':review['source_file'],'sha256':review['source_file_sha256'],'line':review['line']}
        entries[sid]={'candidate_id':sid,'image_sha256':a['image_sha256'],
            'annotation_file':label_path.relative_to(R).as_posix(),'annotation_sha256':h,'label_version':a['label_version'],
            'first_pass_reviewer':a['reviewer'],'independent_reviewer':raw['reviewer_id'],
            'independent_review_source':binding,'confirmed_body_ids':bodies,'retained_ignore_ids':ignores,
            'label_status':'body_targets_confirmed_with_ignore_constraints' if bodies else 'ignore_only_explicit_body_training_exclusion',
            'confirmation_scope':'Exact current-SHA body targets and conservative regions; no inference of unknown attributes or ordinary background.',
            'body_attribute_unknown_is_not_a_detection_blocker':True,
            'standard_full_image_yolo_label_compatible':bool(bodies) and not ignores,
            'independent_findings':raw.get('findings',[]),'original_arbitration_requests':raw.get('PC_arbitration_required',[]),
            'PC_resolution':'Version-bound independent recheck accepted current amendment; retained unknowns remain ignore and cannot become YOLO background.',
            'data_blockers':['site/group independence and split not verified']+(['ignore-safe detector export required'] if bodies and ignores else []),
            'human_signoff':False,'AI_records_represented_as_human':False,'training_release':False}
        key=(sid,h,raw['reviewer_id'])
        if key not in ledger_keys:
            ledger.append({'candidate_id':sid,'first_pass':{'file':label_path.relative_to(R).as_posix(),'sha256':h,
                'reviewer_id':a['reviewer'],'reviewer_type':'AI','reviewed_at':a['recorded_at']},
                'independent_review_source':binding,'independent_review_record':raw});ledger_keys.add(key)
        if not bodies and not any(d['candidate_id']==sid and d['annotation_sha256']==h for d in disp['entries']):
            disp['entries'].append({'candidate_id':sid,'annotation_sha256':h,'manifest_sha256':raw['manifest_sha256'],
                'action':'excluded_from_training','reason':'Current amended label has no reliable target body; independent recheck accepts conservative ignores. Exclude from body training, never ordinary background.',
                'independent_review_file':review['source_file'],'independent_review_file_sha256':review['source_file_sha256'],
                'independent_reviewer_id':raw['reviewer_id'],'training_approval':False,'human_signoff':False})
        accepted.append(sid)
    if accepted:
        provenance=read(R/'data/archive_provenance.json');archive=R/'data/s2tld_1080.zip'
        assert sha(archive)==provenance['sha256']
        with zipfile.ZipFile(archive) as z:
            names={}
            for name in z.namelist():
                names[name]=name
                try:names[name.encode('cp437').decode('gbk')]=name
                except (UnicodeEncodeError,UnicodeDecodeError):pass
            for sid in accepted:
                row=rows[sid];assert hashlib.sha256(z.read(names[row['source_member']])).hexdigest()==row['sha256']
                row['clean_original']='verified'
        with (R/'data/candidates.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=next(iter(rows.values())).keys());writer.writeheader();writer.writerows(rows.values())
    save(disp_path,disp)
    ledger_path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in ledger),encoding='utf-8')
    final.update({'recorded_at':datetime.now(timezone.utc).isoformat(),'entries':sorted(entries.values(),key=lambda e:e['candidate_id']),
        'final_label_candidates':len(entries),'final_body_label_confirmed_images':sum(bool(e['confirmed_body_ids']) for e in entries.values()),
        'confirmed_body_count':sum(len(e['confirmed_body_ids']) for e in entries.values()),
        'confirmed_ignore_only_exclusions':sum(not e['confirmed_body_ids'] for e in entries.values()),
        'standard_full_image_yolo_label_compatible_images':sum(e['standard_full_image_yolo_label_compatible'] for e in entries.values()),
        'two_AI_review_ledger_sha256':sha(ledger_path),'version_bound_review_records_preserved':len(ledger),
        'targeted_current_version_accept_ids':accepted})
    save(path,final);save(R/'reports/formal_review_integration.json',{k:v for k,v in final.items() if k!='entries'})
    print(json.dumps({'targeted_current_version_accepts':len(accepted),'final_body_label_confirmed_images':final['final_body_label_confirmed_images'],'ignore_only_exclusions':final['confirmed_ignore_only_exclusions']}))


if __name__=='__main__':main()
