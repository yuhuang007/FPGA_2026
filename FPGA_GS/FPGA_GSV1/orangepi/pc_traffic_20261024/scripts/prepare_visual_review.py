from pathlib import Path
import json,csv,xml.etree.ElementTree as ET,hashlib
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];out=R/'review_stage2';out.mkdir(exist_ok=True);(out/'panels').mkdir(exist_ok=True);(out/'batches').mkdir(exist_ok=True);(out/'first_pass').mkdir(exist_ok=True);(out/'overlays').mkdir(exist_ok=True)
rows=list(csv.DictReader((R/'data/candidates.csv').open(encoding='utf-8-sig')))
source=[]
for i,row in enumerate(rows):
 im=Image.open(R/row['image_path']).convert('RGB');a=ET.parse(R/row['source_xml']).getroot();obs=[]
 for j,o in enumerate(a.findall('object')):
  bb=o.find('bndbox');box=[int(float(bb.findtext(x))) for x in ['xmin','ymin','xmax','ymax']];obs.append({'source_index':j,'source_class':o.findtext('name'),'bbox_xyxy':box})
 source.append(obs)
 can=Image.new('RGB',(1280,600),'#eeeeee');d=ImageDraw.Draw(can);d.text((8,4),f'{i:04d} FULL UNMARKED + source-XML regions (NOT approved)',fill='black')
 full=im.resize((800,450));can.paste(full,(0,28));d.text((5,485),f'Source {im.size} | {row["source_member"].split("/")[-1]}',fill='black')
 # Every XML region enlarged with context; bounding box identifies only source proposal.
 n=len(obs);cw=240;ch=min(180,550//max(1,(n+1)//2))
 for j,o in enumerate(obs):
  b=o['bbox_xyxy'];pad=max(10,min(50,max(b[2]-b[0],b[3]-b[1])//3));crop=[max(0,b[0]-pad),max(0,b[1]-pad),min(im.width,b[2]+pad),min(im.height,b[3]+pad)];a=im.crop(crop);scale=min((cw-8)/a.width,(ch-28)/a.height,5);nw,nh=round(a.width*scale),round(a.height*scale);a=a.resize((nw,nh));x=800+(j%2)*240;y=28+(j//2)*ch;can.paste(a,(x,y+20));d.text((x+2,y),f'#{j} {o["source_class"]} {b}',fill='black');d.rectangle([x+(b[0]-crop[0])*scale,y+20+(b[1]-crop[1])*scale,x+(b[2]-crop[0])*scale,y+20+(b[3]-crop[1])*scale],outline='cyan',width=1)
 can.save(out/'panels'/f'{i:04d}.jpg',quality=92)
for b in range(50):
 can=Image.new('RGB',(2560,2400),'white')
 for k in range(8):can.paste(Image.open(out/'panels'/f'{b*8+k:04d}.jpg'),((k%2)*1280,(k//2)*600))
 can.save(out/'batches'/f'{b:02d}.jpg',quality=94)
(out/'source_reference.json').write_text(json.dumps(source,indent=2),encoding='utf-8')
print('400 individual review panels + 50 batches generated; no review conclusions generated')
