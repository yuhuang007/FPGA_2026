"""Prepare only explicitly inspected candidate evidence, no approval or gate changes."""
import csv
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/independent_review_r1'


def main():
    OUT.mkdir(exist_ok=True)
    crops={0:[(1548,510,1590,574)],64:[(646,500,690,580)],
           200:[(538,170,627,273),(1280,220,1350,382)],300:[(795,425,846,469)]}
    manifest=[]
    for index,regions in crops.items():
        source=ROOT/'data/candidate_images'/f's2tld1080_{index:04d}.jpg'
        im=Image.open(source).convert('RGB')
        for j,region in enumerate(regions):
            crop=im.crop(region);scale=4
            out=OUT/f'candidate_{index:04d}_suspect_{j}.png'
            crop.resize((crop.width*scale,crop.height*scale),Image.Resampling.NEAREST).save(out)
            manifest.append({'index':index,'crop_xyxy':region,'magnification':scale,
                             'resampling':'nearest; no added visual detail','path':str(out),
                             'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
    a=Image.open(ROOT/'data/candidate_images/s2tld1080_0032.jpg').convert('RGB')
    b=Image.open(ROOT/'data/candidate_images/s2tld1080_0127.jpg').convert('RGB')
    aa=np.array(a);bb=np.array(b)
    pair={'a':'s2tld1080_0032','b':'s2tld1080_0127',
          'sha_a':hashlib.sha256((ROOT/'data/candidate_images/s2tld1080_0032.jpg').read_bytes()).hexdigest(),
          'sha_b':hashlib.sha256((ROOT/'data/candidate_images/s2tld1080_0127.jpg').read_bytes()).hexdigest(),
          'pixel_identical':bool(np.array_equal(aa,bb)),
          'mean_abs_rgb':float(np.abs(aa.astype(float)-bb).mean()),
          'scope':'Pixel comparison corroborates separate AI visual inspection; not final split approval'}
    (OUT/'probe_evidence.json').write_text(json.dumps({'crops':manifest,'pair':pair},indent=2),encoding='utf-8')
    print(json.dumps(pair,indent=2))


if __name__=='__main__':main()
