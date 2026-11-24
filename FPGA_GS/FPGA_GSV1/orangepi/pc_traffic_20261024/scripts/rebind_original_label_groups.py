"""Refresh exact label SHA bindings without changing any source group or split."""
import argparse
import json
from datetime import datetime, timezone
from pilot_clean_crops import ROOT, read, sha
from qualify_clean_originals import confirmed_current


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--release', required=True)
    ap.add_argument('--ids', nargs='+', required=True)
    args=ap.parse_args()
    out=ROOT/('data/group_releases/'+args.release)
    assert not out.exists(), 'Never overwrite a group release'
    pointer=read(ROOT/'data/released_original_groups.json')
    prior=ROOT/pointer['immutable_release']
    assert sha(prior)==pointer['immutable_release_sha256']
    old=read(prior); current=confirmed_current()
    wanted={'s2tld1080_'+x if x.isdecimal() else x for x in args.ids}
    changes=[];groups=[];evidence={p['path']:p for p in old['evidence']}
    evidence[prior.relative_to(ROOT).as_posix()]={'path':prior.relative_to(ROOT).as_posix(),'sha256':sha(prior)}
    for original in old['groups']:
        g=dict(original);cid=g['candidate_id']
        if cid in wanted:
            c=current[cid];a=read(ROOT/c['annotation_file'])
            assert c['image_sha256']==g['image_sha256']==a['image_sha256']
            assert sha(ROOT/c['annotation_file'])==c['annotation_sha256']
            assert a['supersedes_annotation_sha256']==g['annotation_sha256'], 'Only a direct verified version binding refresh'
            assert g['annotation_sha256']!=c['annotation_sha256']
            ref=c['independent_review_source'];rp=ROOT/ref.get('file',ref.get('source_file'))
            assert sha(rp)==ref.get('sha256',ref.get('source_file_sha256'))
            raw=json.loads(rp.read_text(encoding='utf-8-sig').splitlines()[ref['line']-1])
            assert raw['decision']=='accept' and raw['reviewed_annotation_sha256']==c['annotation_sha256']
            for p in (rp, ROOT/c['annotation_file']):
                evidence[p.relative_to(ROOT).as_posix()]={'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)}
            changes.append({'candidate_id':cid,'old_annotation_sha256':g['annotation_sha256'],'new_annotation_sha256':c['annotation_sha256'],
                'image_group_split_unchanged':True,'label_approval_from_genuine_separate_intake':True,'old_crops_still_stale':True})
            g['annotation_sha256']=c['annotation_sha256']
        assert {k:v for k,v in g.items() if k!='annotation_sha256'}=={k:v for k,v in original.items() if k!='annotation_sha256'}
        groups.append(g)
    assert {c['candidate_id'] for c in changes}==wanted
    out.mkdir(parents=True)
    audit=read(ROOT/'reports/split_audit.json')
    (out/'prior_split_audit_snapshot.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    result=dict(old,release_id='original_groups_'+args.release,recorded_at=datetime.now(timezone.utc).isoformat(),groups=groups,
        evidence=list(evidence.values()),supersedes={'path':prior.relative_to(ROOT).as_posix(),'sha256':sha(prior)},
        annotation_binding_refreshes=changes,source_geography_and_splits_unchanged=True,
        binding_refresh_scope='Only direct accepted label-version SHA changes on identical original bytes. Existing independent source audit and exact group/split identity preserved. No crop/quantity/training approval created.')
    dest=out/'manifest.json';dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    result.update(immutable_release=dest.relative_to(ROOT).as_posix(),immutable_release_sha256=sha(dest))
    (ROOT/'data/released_original_groups.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    audit.update(recorded_at=result['recorded_at'],release=dest.relative_to(ROOT).as_posix(),release_sha256=sha(dest),
        annotation_binding_only_refresh=True,original_source_audit_scope_preserved=True)
    (ROOT/'reports/split_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'group_release':args.release,'annotation_bindings_refreshed':len(changes),'source_groups_or_splits_changed':0}))


if __name__=='__main__':main()
