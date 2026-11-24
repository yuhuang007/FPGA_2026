"""Acquire a bounded CC-BY photo batch with current, per-photo source evidence."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import argparse,hashlib,io,json,re
import requests
from PIL import Image

R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def short_photo_url(photo_id):
    alphabet='123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
    number=int(photo_id);encoded=''
    while number:
        number,rem=divmod(number,58);encoded=alphabet[rem]+encoded
    return 'https://flic.kr/p/'+encoded

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--batch',required=True);ap.add_argument('--limit',type=int,default=12);args=ap.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*',args.batch) and 1<=args.limit<=16
    out=R/'data'/('external_scene_candidates_'+args.batch);assert not out.exists(),'Preserve published acquisition batch'
    for sub in ('images','views','provenance'):(out/sub).mkdir(parents=True,exist_ok=True)
    catalog=read(R/'sources/external_scene_research/coco_traffic_candidates.json')
    cached={e['id']:e for e in read(R/'sources/external_scene_research/coco_flickr_provenance_candidates.json')}
    used=set();attempted=set()
    for p in list((R/'data').glob('external_scene_candidates_r*/acquisition_manifest.json'))+[R/'data/external_coco_scene_pilot_r1/acquisition_manifest.json']:
        for e in read(p)['entries']:
            attempted.add(e.get('coco_id',e.get('id')))
            if e.get('image') or e.get('local_image'):used.add(e.get('coco_id',e.get('id')))
    available=[e for e in catalog if e['id'] not in used and (e['id'] not in cached or cached[e['id']].get('oembed',{}).get('url'))]
    available.sort(key=lambda e:e['id'] in attempted)
    def acquire(e):
        pid=re.search(r'/([0-9]+)_',e['flickr_url']).group(1)
        prior=cached.get(e['id'],{}).get('oembed',{});page=prior.get('web_page') or 'https://www.flickr.com/photo.gne?id='+pid
        record={'candidate_id':f'coco_scene_{e["id"]:012d}','coco_id':e['id'],'photo_id':pid,
            'source_catalog':'sources/external_scene_research/coco_traffic_candidates.json','source_catalog_sha256':sha(R/'sources/external_scene_research/coco_traffic_candidates.json'),
            'source_reference_size':[e['width'],e['height']],'source_annotations_reference_only':e['source_traffic_annotations'],
            'source_boxes_are_project_truth':False,'training_release':False,'review_status':'acquired_not_reviewed'}
        try:
            tries=[]
            for url in dict.fromkeys([page,short_photo_url(pid)]):
                response=requests.get('https://www.flickr.com/services/oembed/',params={'url':url,'format':'json'},timeout=20)
                tries.append({'source_url':url,'http_status':response.status_code})
                if response.ok:break
            record['oembed_attempts']=tries
            response.raise_for_status();o=response.json()
            p=out/'provenance'/f'{e["id"]}_oembed.json';p.write_text(json.dumps({'retrieved_at':datetime.now(timezone.utc).isoformat(),'request_url':response.url,'payload':o},ensure_ascii=False,indent=2),encoding='utf-8')
            record.update({'photo_page':o.get('web_page',page),'title':o.get('title'),'author':o.get('author_name'),
                'current_license':o.get('license'),'current_license_url':o.get('license_url'),
                'source_oembed':p.relative_to(R).as_posix(),'source_oembed_sha256':sha(p)})
            assert o.get('license_url','').startswith(('https://creativecommons.org/licenses/by/2.0/','https://creativecommons.org/licenses/by/4.0/')),'Current photo license is not selected CC-BY'
            assert pid in o['url'],'Source photo identity mismatch'
            response=requests.get(o['url'],timeout=30);response.raise_for_status();assert len(response.content)<15000000
            im=Image.open(io.BytesIO(response.content));im.load();p=out/'images'/e['file_name'];p.write_bytes(response.content)
            view=im.convert('RGB');view.thumbnail((900,650));vp=out/'views'/e['file_name'];view.save(vp,quality=92)
            record.update({'image':p.relative_to(R).as_posix(),'image_sha256':sha(p),'image_size':list(im.size),
                'unmarked_view':vp.relative_to(R).as_posix(),'download_url':o['url'],'license_status':'verified_current_oembed_CC_BY'})
            try:
                response=requests.get(record['photo_page'],timeout=15);response.raise_for_status();p=out/'provenance'/f'{e["id"]}_page.html';p.write_text(response.text,encoding='utf-8')
                record.update({'photo_page_evidence':p.relative_to(R).as_posix(),'photo_page_sha256':sha(p)})
            except requests.RequestException as ex:record['photo_page_error']=str(ex)
        except Exception as ex:record.update({'review_status':'acquisition_failed_or_quarantined','error':type(ex).__name__+': '+str(ex)})
        return record
    entries=[]
    # Stop after at most16 attempted originals; image review remains a later,
    # real small-batch task rather than an automated label conversion.
    with ThreadPoolExecutor(max_workers=3) as pool:
        entries=list(pool.map(acquire,available[:args.limit]))
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'batch':args.batch,'entries':entries,
        'acquired_originals':sum('image' in e for e in entries),'initial_review_completed':0,
        'source_annotations_are_not_project_truth':True,'training_release':False}
    (out/'acquisition_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'acquired_originals':report['acquired_originals'],'attempted':len(entries),
        'ids':[e['candidate_id'] for e in entries if e.get('image')],'failures':[{'id':e['candidate_id'],'error':e.get('error')} for e in entries if not e.get('image')]}))

if __name__=='__main__':main()
