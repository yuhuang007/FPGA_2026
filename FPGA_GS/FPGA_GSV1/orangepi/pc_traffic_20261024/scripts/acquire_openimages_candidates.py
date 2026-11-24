"""Acquire current-CC-BY Flickr photos from official Open Images metadata."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import argparse,hashlib,io,json,re
import requests
from PIL import Image

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--batch',required=True);args=ap.parse_args()
    assert re.fullmatch('r[1-9][0-9]*',args.batch)
    folder=R/'sources/external_scene_research/openimages';probe=folder/'current_license_probe_r1.json'
    out=R/'data'/('external_scene_candidates_'+args.batch);assert not out.exists()
    for sub in ('images','views','provenance'):(out/sub).mkdir(parents=True,exist_ok=True)
    candidates=[e for e in read(probe) if e.get('current_license_verified')]
    used=set()
    for p in list((R/'data').glob('external_scene_candidates_r*/acquisition_manifest.json'))+[R/'data/external_coco_scene_pilot_r1/acquisition_manifest.json']:
        for e in read(p)['entries']:
            if e.get('image') or e.get('local_image'):used.add(str(e.get('photo_id',e.get('flickr_photo_id'))))
    def acquire(q):
        e=q['image_metadata'];pid=re.search(r'/([0-9]+)/?$',e['OriginalLandingURL']).group(1)
        record={'candidate_id':'oi_scene_'+e['ImageID'],'source_dataset':'OpenImages_v5_validation',
            'source_dataset_image_id':e['ImageID'],'photo_id':pid,'source_annotations_reference_only':e['source_traffic_annotations'],
            'source_reference_size':None,'source_boxes_are_project_truth':False,'training_release':False,
            'source_catalog':(folder/'traffic_photo_catalog_r1.json').relative_to(R).as_posix(),
            'source_catalog_sha256':sha(folder/'traffic_photo_catalog_r1.json'),'official_metadata':e,
            'official_source_evidence':[{'path':p.relative_to(R).as_posix(),'sha256':sha(p)} for p in
                [folder/'official_download.html',folder/'validation-images.csv',folder/'validation-bboxes.csv',folder/'classes.csv']]}
        try:
            assert pid not in used,'Previously acquired original-photo identity'
            response=requests.get('https://www.flickr.com/services/oembed/',params={'url':e['OriginalLandingURL'],'format':'json'},timeout=20);response.raise_for_status();o=response.json()
            p=out/'provenance'/(e['ImageID']+'_oembed.json');p.write_text(json.dumps({'retrieved_at':datetime.now(timezone.utc).isoformat(),'request_url':response.url,'payload':o},ensure_ascii=False,indent=2),encoding='utf-8')
            assert o.get('license_url','').startswith(('https://creativecommons.org/licenses/by/2.0/','https://creativecommons.org/licenses/by/4.0/')),'Current license no longer selected CC-BY'
            assert pid in o['url'],'Photo identity mismatch'
            record.update(photo_page=o.get('web_page',e['OriginalLandingURL']),title=o.get('title'),author=o.get('author_name'),
                current_license=o.get('license'),current_license_url=o.get('license_url'),
                source_oembed=p.relative_to(R).as_posix(),source_oembed_sha256=sha(p))
            response=requests.get(o['url'],timeout=30);response.raise_for_status();assert len(response.content)<15000000
            im=Image.open(io.BytesIO(response.content));im.load();p=out/'images'/(e['ImageID']+'.jpg');p.write_bytes(response.content)
            v=im.convert('RGB');v.thumbnail((900,650));vp=out/'views'/p.name;v.save(vp,quality=92)
            record.update(image=p.relative_to(R).as_posix(),image_sha256=sha(p),image_size=list(im.size),unmarked_view=vp.relative_to(R).as_posix(),
                download_url=o['url'],license_status='verified_current_oembed_CC_BY',review_status='acquired_not_reviewed')
            try:
                response=requests.get(record['photo_page'],timeout=15);response.raise_for_status();p=out/'provenance'/(e['ImageID']+'_page.html');p.write_text(response.text,encoding='utf-8')
                record.update(photo_page_evidence=p.relative_to(R).as_posix(),photo_page_sha256=sha(p))
            except requests.RequestException as ex:record['photo_page_error']=str(ex)
        except Exception as ex:record.update(review_status='acquisition_failed_or_quarantined',error=str(ex))
        return record
    with ThreadPoolExecutor(max_workers=3) as pool:entries=list(pool.map(acquire,candidates))
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'batch':args.batch,'entries':entries,
        'acquired_originals':sum('image' in e for e in entries),'initial_review_completed':0,
        'source_annotations_are_not_project_truth':True,'training_release':False}
    (out/'acquisition_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'acquired_originals':report['acquired_originals'],'ids':[e['candidate_id'] for e in entries if e.get('image')],
        'failures':[e.get('error') for e in entries if not e.get('image')]}))
if __name__=='__main__':main()
