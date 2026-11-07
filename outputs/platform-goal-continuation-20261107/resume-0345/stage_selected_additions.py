"""Stage only newly selected photos missing from seven original eBay imports."""
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
full=json.loads((OUT/'full-gallery-reconciliation.json').read_text())
targets=[r for r in full['records'] if r['difference_kind']=='selection_changed' and r['sku'] not in ['BOLD-22B6E4FB3DD8','BOLD-B6EC1EDD319F']]
assert len(targets)==7
path=OUT/'new-selection-additions-manifest.json'
assert not path.exists(), 'Reconcile the existing staged additions before rerunning'
result=dict(status='PREPARING_NEW_SELECTED_ORIGINALS',source_app_revision=full['source_app_revision'],records=[],native_writes=0,original_edits=0)
save=lambda:path.write_text(json.dumps(result,indent=2)+'\n')
save();total=0;cache={}
with connection(ROOT) as (db,_):
    for r in targets:
        old=r['historical_gallery_ids'];desired=r['desired_gallery_ids']
        missing=[aid for aid in desired if aid not in old]
        assert len(missing)==1 and set(old).issubset(desired) and old[0]==desired[0]
        directory=OUT/'selected-additions'/r['native_draft_id'];directory.mkdir(parents=True,exist_ok=True)
        sources={i['id']:i for i in r['image_sources']};uploaded=[]
        for aid in missing:
            image=sources[aid];meta=db.files_get_metadata(aid);expected=image['original']['dropbox_content_hash']
            assert meta.id==aid and meta.content_hash==expected
            assert meta.size<50_000_000 and total+meta.size<100_000_000
            suffix=Path(meta.name).suffix.lower();assert suffix in {'.png','.jpg','.jpeg'}
            staged=directory/('01'+suffix);assert not staged.exists()
            if aid in cache:
                body=cache[aid]
            else:
                read_meta,response=db.files_download('rev:'+meta.rev)
                try:body=response.content
                finally:response.close()
                assert read_meta.id==aid;cache[aid]=body
            digest=hashlib.sha256(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304))).hexdigest()
            assert digest==expected and len(body)==meta.size
            staged.write_bytes(body)
            with Image.open(staged) as photo:
                width,height=photo.size;photo.verify()
            assert max(width,height)>=500
            total+=meta.size
            uploaded.append(dict(photo_id=aid,content_hash=digest,revision=meta.rev,original_name=meta.name,
                                 path=str(staged.resolve()),sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),width=width,height=height))
        files=[dict(photo_id=aid,content_hash=sources[aid]['original']['dropbox_content_hash'],
                    original_name=sources[aid]['name'],source='CURRENT_COMPLETE_COMPONENT_RECORD') for aid in desired]
        result['records'].append(dict(sku=r['sku'],native_draft_id=r['native_draft_id'],title=r['title'],
                                      previous_native_photo_count=len(old),previous_native_source_ids=old,
                                      desired_photo_count=len(desired),native_upload_source_order_ids=old+missing,
                                      mode='APPEND_ONE_NEW_SELECTED_PHOTO_PRESERVE_EXISTING_PRIMARY',
                                      directory=str(directory.resolve()),files=files,upload_files=uploaded,
                                      status='EXACT_ORIGINAL_READY_NATIVE_APPEND_PENDING'))
        save();print(json.dumps(dict(sku=r['sku'],existing=len(old),add=len(uploaded),target=len(desired))),flush=True)
result.update(status='READY_NEW_SELECTED_ORIGINALS',bytes=total,unique_downloads=len(cache),checked_utc=datetime.now(timezone.utc).isoformat())
save();print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2),flush=True)
