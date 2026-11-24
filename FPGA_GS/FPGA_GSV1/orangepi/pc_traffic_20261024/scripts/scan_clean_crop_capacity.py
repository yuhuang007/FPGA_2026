"""Geometry-only capacity estimate, never export or grant label confirmation."""
from datetime import datetime, timezone
import csv, json, statistics
from pilot_clean_crops import ROOT, read, sha, candidates, area

def main():
    csvpath=ROOT/'data/candidates.csv';rows=list(csv.DictReader(csvpath.open(encoding='utf-8-sig')))
    final={e['candidate_id']:e for e in read(ROOT/'review_stage2/final_candidates_r1/manifest.json')['entries']}
    entries=[]
    for row in rows:
        p=ROOT/row['annotation_file'];a=read(p);b=[o for o in a['objects'] if o['type']=='body']
        # All declared bodies are hypothetical positives for this scan, including
        # drafts awaiting a genuine second review. This cannot approve a sample.
        result,obstacles=candidates(a,{'confirmed_body_ids':[o['id'] for o in b]})
        h=sha(p);accepted=final.get(row['sample_id'])
        record={'candidate_id':row['sample_id'],'annotation':p.relative_to(ROOT).as_posix(),'annotation_sha256':h,
            'current_label_finally_confirmed':bool(accepted and accepted['annotation_sha256']==h),
            'declared_bodies':len(b),'declared_source_truncated_bodies':sum(o.get('truncated',False) for o in b),
            'has_nontruncated_declared_body':any(not o.get('truncated',False) for o in b),
            'has_geometry_proposal':bool(result),'retained_declared_body_ids':[o['id'] for o in result['bodies']] if result else [],
            'visual_crop_review_completed':False,'training_release':False}
        if result:
            c=result['crop_xyxy'];record.update({'crop_xyxy':c,'area_retained_fraction':area(c)/(a['image_size'][0]*a['image_size'][1]),
                'linear_magnification_at_640':max(a['image_size'])/max(c[2]-c[0],c[3]-c[1])})
        entries.append(record)
    positive=sum(e['declared_bodies']>0 for e in entries);proposed=[e for e in entries if e['has_geometry_proposal']]
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'scope':'Hypothetical draft-label geometry capacity over original400, not final labels or usable/qualified image counts.',
        'originals_scanned':len(entries),'declared_body_positive_originals':positive,
        'nontruncated_body_originals_upper_bound_under_current_policy':sum(e['has_nontruncated_declared_body'] for e in entries),
        'declared_body_count':sum(e['declared_bodies'] for e in entries),
        'proposed_originals':len(proposed),'proposed_body_count':sum(len(e['retained_declared_body_ids']) for e in proposed),
        'proposed_originals_with_finally_confirmed_current_labels':sum(e['current_label_finally_confirmed'] for e in proposed),
        'proposed_area_retained':{'min':min(e['area_retained_fraction'] for e in proposed),'median':statistics.median(e['area_retained_fraction'] for e in proposed),'max':max(e['area_retained_fraction'] for e in proposed)},
        'source_truncated_body_count':sum(e['declared_source_truncated_bodies'] for e in entries),
        'current_pipeline_original_proposal_shortfall_to_300':max(0,300-len(proposed)),
        'geometry_search_is_not_a_proof_of_global_impossibility':True,
        'quantity_unit':'Original photos; each counted once. All proposals still need current-SHA label acceptance, real crop QA, licensing and group/split release.',
        'bulk_image_conversion_performed':False,'qualified_images_created':0,'entries':entries}
    out=ROOT/'reports/clean_crop_capacity_original400.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k in ('declared_body_positive_originals','declared_body_count','proposed_originals','proposed_body_count','current_pipeline_original_proposal_shortfall_to_300','proposed_area_retained')}))

if __name__=='__main__':main()
