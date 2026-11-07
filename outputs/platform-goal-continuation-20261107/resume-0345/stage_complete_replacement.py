"""Stage one complete gallery; mixed imported/local eBay galleries did not persist."""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen
from PIL import Image

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
parser=argparse.ArgumentParser();parser.add_argument('--sku',required=True);parser.add_argument('--previous-count',type=int,required=True)
args=parser.parse_args()
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
full=json.loads((OUT/'full-gallery-reconciliation.json').read_text())
with urlopen('http://127.0.0.1:8767/api/specifications',timeout=90) as response:
    assert json.load(response)['revision']==full['source_app_revision'], 'Current app selections changed; rebase before staging'
r=next(r for r in full['records'] if r['sku']==args.sku)
path=OUT/('complete-replacement-'+r['native_draft_id']+'.json')
assert not path.exists(), 'Reconcile an already staged replacement before rerunning'
reuse={}
for manifest_path in [OUT/'full-gallery-repair-manifest.json',OUT/'new-selection-additions-manifest.json',*OUT.glob('complete-replacement-*.json')]:
    data=json.loads(manifest_path.read_text())
    for record in data['records']:
        for f in record.get('files',[])+record.get('upload_files',[]):
            if f.get('path') and Path(f['path']).exists():reuse[f['photo_id']]=f
directory=OUT/'complete-replacements'/r['native_draft_id'];directory.mkdir(parents=True,exist_ok=True)
files=[];total=downloaded=reused=0
with connection(ROOT) as (db,_):
    for index,image in enumerate(r['image_sources'],1):
        aid=image['id'];meta=db.files_get_metadata(aid);expected=image['original']['dropbox_content_hash']
        assert meta.id==aid and meta.content_hash==expected
        assert meta.size<50_000_000 and total+meta.size<180_000_000
        suffix=Path(meta.name).suffix.lower();assert suffix in {'.png','.jpg','.jpeg'}
        staged=directory/(f'{index:02d}'+suffix);assert not staged.exists()
        if aid in reuse:
            source=Path(reuse[aid]['path']);body=source.read_bytes()
            assert hashlib.sha256(body).hexdigest()==reuse[aid]['sha256']
            os.link(source,staged);reused+=1
        else:
            read_meta,response=db.files_download('rev:'+meta.rev)
            try:body=response.content
            finally:response.close()
            assert read_meta.id==aid
            staged.write_bytes(body);downloaded+=1
        digest=hashlib.sha256(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304))).hexdigest()
        assert digest==expected and len(body)==meta.size
        with Image.open(staged) as photo:
            width,height=photo.size;photo.verify()
        assert max(width,height)>=500
        total+=meta.size
        files.append(dict(photo_id=aid,original_name=meta.name,revision=meta.rev,content_hash=digest,
                          sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),width=width,height=height,path=str(staged.resolve())))
        print(json.dumps(dict(sku=r['sku'],staged=index,total=len(r['image_sources']))),flush=True)
record=dict(sku=r['sku'],native_draft_id=r['native_draft_id'],title=r['title'],
            previous_native_photo_count=args.previous_count,desired_photo_count=len(files),
            mode='REPLACE_COMPLETE_GALLERY_AVOID_MIXED_IMPORT_PERSISTENCE_LOSS',directory=str(directory.resolve()),
            files=files,upload_files=files,status='EXACT_COMPLETE_ORIGINALS_READY_NATIVE_REPLACEMENT_PENDING')
with urlopen('http://127.0.0.1:8767/api/specifications',timeout=90) as response:
    assert json.load(response)['revision']==full['source_app_revision'], 'Current app selections changed during staging'
result=dict(status='READY_EXACT_COMPLETE_GALLERY',checked_utc=datetime.now(timezone.utc).isoformat(),
            source_app_revision=full['source_app_revision'],records=[record],bytes=total,
            downloaded_files=downloaded,reused_files=reused,native_writes=0,original_edits=0)
path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2),flush=True)
