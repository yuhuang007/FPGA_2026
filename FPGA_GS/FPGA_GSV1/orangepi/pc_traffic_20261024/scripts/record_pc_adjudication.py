"""Persist explicit PC findings after actual viewing; never create independent review."""
import csv, hashlib, json
from pathlib import Path
from datetime import datetime, timezone

R=Path(__file__).resolve().parents[1]


def record(cases):
    path=R/'reports/pc_adjudication_20261025.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    rows={r['sample_id']:r for r in csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig'))}
    for i,case in cases.items():
        sid=f's2tld1080_{i:04d}'
        assert sid not in {c['candidate_id'] for c in data['cases']}, 'Preserve prior adjudication'
        label=R/rows[sid]['annotation_file']
        ev=[R/f'review_stage2/adjudication_20261025/{i:04d}_{suffix}' for suffix in ['full.jpg','detail.png']]
        ev += [R/name for name in case.pop('extra_evidence',[])]
        assert all(p.is_file() for p in ev)
        data['cases'].append({'candidate_id':sid,'annotation_file':label.relative_to(R).as_posix(),
            'annotation_sha256':hashlib.sha256(label.read_bytes()).hexdigest(),
            'whole_image_standard_yolo_release':False,**case,
            'evidence':[{'path':p.relative_to(R).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in ev]})
    data['recorded_at']=datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Persisted actual PC adjudications:',list(cases))
