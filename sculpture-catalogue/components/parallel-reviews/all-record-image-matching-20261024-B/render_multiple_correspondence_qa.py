"""Inspection-only boards for source frames with multiple qualified Dropbox versions."""
from pathlib import Path
from collections import defaultdict
import json,hashlib,sqlite3,textwrap
from PIL import Image,ImageOps,ImageDraw
H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=Path(read(H/'current-integration.json')['run']);out=H/'multiple-correspondence-qa';out.mkdir(exist_ok=True)
db=sqlite3.connect(r/'complete-image-platform-register.sqlite');images={f:json.loads(v) for f,v in db.execute('select file_id,record_json from images')}
native={x['file_id']:x for x in read(H.parents[3]/'reports/dropbox-wall-complete-role-review-20261024T214349Z/current-6360-visual-source-evidence.json')}
gallery={x['gallery_entry_id']:x for x in read(r/'source-gallery-review.json')}
grouped=defaultdict(dict)
for m in read(r/'source-photo-correspondences.json'):
    if m['offer_ref']!='O001':grouped[m['gallery_entry_id']].setdefault(m['file_id'],[]).append(m['status'])
groups=[]
for gid,fs in grouped.items():
    if len(fs)<2:continue
    src=gallery[gid]
    groups.append({'key':f"{src['offer_ref']}:{src['gallery_order']:02d}",'gallery_entry_id':gid,'source_path':src['selected_rendition']['path'],'source_sha256':src['selected_rendition']['sha256'],'candidates':[{'file_id':fid,'name':images[fid]['name'],'path':native[fid]['source_image_path'],'sha256':native[fid]['actual_visual_source_sha256'],'evidence_grades':grades} for fid,grades in fs.items()]})
groups.sort(key=lambda x:x['key'])
for start in range(0,len(groups),3):
    rows=groups[start:start+3];board=Image.new('RGB',(1600,450*len(rows)),'white');d=ImageDraw.Draw(board)
    for n,row in enumerate(rows):
        tiles=[{'path':row['source_path'],'sha256':row['source_sha256'],'label':row['key']+' SOURCE'}]+[{'path':x['path'],'sha256':x['sha256'],'label':x['file_id'][-7:]+' '+x['name']} for x in row['candidates']]
        for col,tile in enumerate(tiles):
            assert sha(tile['path'])==tile['sha256']
            with Image.open(tile['path']) as raw:
                im=ImageOps.exif_transpose(raw).convert('RGB');im.thumbnail((390,370));board.paste(im,(col*400+(400-im.width)//2,n*450+20+(370-im.height)//2))
            d.multiline_text((col*400+5,n*450+392),'\n'.join(textwrap.wrap(tile['label'],48)),fill='black',spacing=2)
    path=out/f'page-{start//3+1}.jpg';board.save(path,quality=95)
    for row in rows:row['board']=str(path);row['board_sha256']=sha(path)
(out/'manifest.json').write_text(json.dumps(groups,indent=2)+'\n');print(json.dumps({'groups':len(groups),'boards':[str(out/f'page-{i}.jpg') for i in range(1,(len(groups)+2)//3+1)]},indent=2))
