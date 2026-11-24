"""Integrate genuine, version-bound AI reviews; keep label and data release separate."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv, hashlib, json, zipfile

R=Path(__file__).resolve().parents[1]


def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,a):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')


def structural_check(label):
    objects={o['id']:o for o in label['objects']}
    assert len(objects)==len(label['objects'])
    for o in objects.values():
        x,y,u,v=o['bbox_xyxy'];assert 0<=x<u<=1920 and 0<=y<v<=1080
        assert o.get('control_relation','unknown')=='unknown'
        if o.get('parent_id'):
            p=objects[o['parent_id']]
            if p['type']=='body':
                a,b,c,d=p['bbox_xyxy'];assert a<=x<u<=c and b<=y<v<=d
        if o['type']=='body':assert o['kind'] in ('motor_vehicle','pedestrian')
        if o['type']=='emitter':
            assert o['color_readable']==(o['state']!='unknown')
            assert o.get('arrow_direction','unknown')=='unknown' or o['symbol']=='arrow'


def main():
    now=datetime.now(timezone.utc).isoformat()
    directory=R/'review_stage2/independent_codex_board_r2'
    validation=read(directory/'final_validation.json')
    assert not validation['changed_files']
    records=[];candidates=[];sources=[]
    rows={a['sample_id']:a for a in csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig'))}
    disposition_path=R/'reports/pc_sample_dispositions.json'
    dispositions=read(disposition_path)
    for bn in ('001','002','003'):
        source=directory/f'fillback_batch_{bn}.jsonl'
        source_hash=sha(source);manifest_path=R/f'review_stage2/frozen/batch_{bn}/manifest.json'
        manifest=read(manifest_path);entries={e['candidate_id']:e for e in manifest['entries']}
        for n,line in enumerate(source.read_text(encoding='utf-8-sig').splitlines(),1):
            review=json.loads(line);e=entries[review['candidate_id']]
            label_path=manifest_path.parent/e['annotation'];image=manifest_path.parent/e['image'];label=read(label_path)
            assert review['manifest_sha256']==sha(manifest_path)
            assert review['image_sha256']==e['image_sha256']==sha(image)==label['image_sha256']
            assert review['reviewed_annotation_sha256']==e['annotation_sha256']==sha(label_path)
            assert review['label_version']==e['label_version']==label['label_version']
            assert review['reviewer_id']!=label['reviewer'] and review['independent_from_first_pass'] is True
            assert review['reviewer_type']=='AI' and not review.get('human_signoff')
            assert review['old_precheck_reused_as_formal_review'] is False
            assert all(review[k] is True for k in ('full_original_checked','omission_search_completed','bounds_checked','kind_checked','attributes_checked'))
            for ev in review['viewed_evidence']:assert sha(R/ev['path'])==ev['sha256']
            structural_check(label)
            binding={'file':source.relative_to(R).as_posix(),'sha256':source_hash,'line':n}
            records.append({'candidate_id':review['candidate_id'],'first_pass':{
                'file':label_path.relative_to(R).as_posix(),'sha256':sha(label_path),'reviewer_id':label['reviewer'],
                'reviewer_type':label['reviewer_type'],'reviewed_at':label['recorded_at']},
                'independent_review_source':binding,'independent_review_record':review})
            if review['decision']!='accept':continue
            # An old acceptance cannot confirm a changed label.
            if sha(R/rows[review['candidate_id']]['annotation_file'])!=sha(label_path):continue
            bodies=[o['id'] for o in label['objects'] if o['type']=='body']
            ignores=[o['id'] for o in label['objects'] if o['type']=='ignore']
            entry={'candidate_id':review['candidate_id'],'image_sha256':e['image_sha256'],
                'annotation_file':label_path.relative_to(R).as_posix(),'annotation_sha256':sha(label_path),
                'label_version':label['label_version'],'first_pass_reviewer':label['reviewer'],
                'independent_reviewer':review['reviewer_id'],'independent_review_source':binding,
                'confirmed_body_ids':bodies,'retained_ignore_ids':ignores,
                'label_status':'body_targets_confirmed_with_ignore_constraints' if bodies else 'ignore_only_explicit_body_training_exclusion',
                'confirmation_scope':'Exact-version body targets and conservative ignore representation; not a statement that every possible signal kind is resolved.',
                'body_attribute_unknown_is_not_a_detection_blocker':True,
                'standard_full_image_yolo_label_compatible':bool(bodies) and not ignores,
                'independent_findings':review['findings'],'original_arbitration_requests':review['PC_arbitration_required'],
                'PC_resolution':'One physical signal shell is one body, including an integrated numeric display; digits are not another body/emitter. Retain uncertain side/far regions as ignore, never ordinary background. Optional exposure flags do not invalidate confirmed body geometry. Site/split questions are data conditions, not a request to invent human signoff.',
                'data_blockers':['site/group independence and split not verified']+(['ignore-aware detection export required; ordinary full-image YOLO export blocked'] if ignores and bodies else []),
                'human_signoff':False,'AI_records_represented_as_human':False,'training_release':False}
            candidates.append(entry)
            if not bodies and review['candidate_id'] not in {d['candidate_id'] for d in dispositions['entries']}:
                dispositions['entries'].append({'candidate_id':review['candidate_id'],
                    'annotation_sha256':sha(label_path),'manifest_sha256':sha(manifest_path),
                    'action':'excluded_from_training','reason':'Two AI reviews agree this is ignore-only, without a reliable target body. PC excludes it from ordinary body detection; it is not negative background. Original annotations retained.',
                    'independent_review_file':binding['file'],'independent_review_file_sha256':source_hash,
                    'independent_reviewer_id':review['reviewer_id'],'training_approval':False,'human_signoff':False})
        assert sha(source)==source_hash
        sources.append({'file':source.relative_to(R).as_posix(),'sha256':source_hash})
    assert len(records)==len({r['candidate_id'] for r in records})==48
    counts=dict(Counter(r['independent_review_record']['decision'] for r in records))
    assert counts==validation['counts']
    assert len(candidates)==34
    archive_path=R/'data/s2tld_1080.zip';provenance=read(R/'data/archive_provenance.json')
    assert sha(archive_path)==provenance['sha256']
    originals=[]
    with zipfile.ZipFile(archive_path) as archive:
        names={}
        for name in archive.namelist():
            names[name]=name
            try: names[name.encode('cp437').decode('gbk')]=name
            except (UnicodeEncodeError,UnicodeDecodeError):pass
        for e in candidates:
            row=rows[e['candidate_id']];member=names[row['source_member']]
            assert hashlib.sha256(archive.read(member)).hexdigest()==row['sha256']==e['image_sha256']
            row['clean_original']='verified'
            originals.append({'candidate_id':e['candidate_id'],'image_sha256':e['image_sha256'],
                'source_member':row['source_member'],'archive_sha256':provenance['sha256'],
                'independent_original_visual_review':e['independent_review_source'],
                'basis':'Byte-identical source archive original; two genuine AI records include original full-frame review before label inspection. Camera timestamp is original, not an inference overlay.'})
    with (R/'data/candidates.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=next(iter(rows.values())).keys());writer.writeheader();writer.writerows(rows.values())
    save(R/'reports/clean_original_verified_by_formal_review.json',{'recorded_at':now,
        'verified_images':len(originals),'human_signoff':False,'entries':originals})
    out=R/'review_stage2/final_candidates_r1'
    ledger=out/'review_ledger.jsonl'
    ledger.parent.mkdir(exist_ok=True)
    ledger.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
    save(disposition_path,dispositions)
    result={'recorded_at':now,'first_pass_completed':len(list((R/'review_stage2/first_pass').glob('*.json'))),
        'independent_review_completed':48,'final_label_candidates':len(candidates),
        'final_body_label_confirmed_images':sum(bool(e['confirmed_body_ids']) for e in candidates),
        'confirmed_body_count':sum(len(e['confirmed_body_ids']) for e in candidates),
        'confirmed_ignore_only_exclusions':sum(not e['confirmed_body_ids'] for e in candidates),
        'standard_full_image_yolo_label_compatible_images':sum(e['standard_full_image_yolo_label_compatible'] for e in candidates),
        'qualified_all_data_conditions':read(R/'reports/readiness.json')['qualified_images'],
        'original_decision_counts':counts,'source_files':sources,
        'final_validation_sha256':sha(directory/'final_validation.json'),
        'two_AI_review_ledger':ledger.relative_to(R).as_posix(),'two_AI_review_ledger_sha256':sha(ledger),
        'human_signoff_required_for_this_integration':False,'human_signoffs_created':0,
        'label_confirmation_does_not_inherit_to_new_sha':True,'entries':candidates}
    save(out/'manifest.json',result)
    save(R/'reports/formal_review_integration.json',{k:v for k,v in result.items() if k!='entries'})
    print(json.dumps({k:result[k] for k in ('first_pass_completed','independent_review_completed','final_label_candidates','final_body_label_confirmed_images','confirmed_body_count','confirmed_ignore_only_exclusions','standard_full_image_yolo_label_compatible_images','qualified_all_data_conditions')}))


if __name__=='__main__':main()
