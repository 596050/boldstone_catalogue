import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent;OLD=OUT.parent/'resume-0220'
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
manifest=json.loads((OLD/'ebay-gallery-source-manifest.json').read_text())
receipts=json.loads((OLD/'ebay-gallery-replacement-receipts.json').read_text())
done={r['native_draft_id'] for r in receipts}
verified=[]
with connection(ROOT) as (db,_):
    for record in manifest['records']:
        if record['native_draft_id'] in done:continue
        for photo in record['files']:
            body=Path(photo['path']).read_bytes()
            assert hashlib.sha256(body).hexdigest()==photo['sha256']
            meta=db.files_get_metadata(photo['photo_id'])
            assert meta.id==photo['photo_id'] and meta.content_hash==photo['content_hash']
        verified.append(dict(sku=record['sku'],native_draft_id=record['native_draft_id'],verified_originals=len(record['files'])))
result=dict(status='PASS_STAGED_BYTES_AND_CURRENT_DROPBOX_IDENTITIES',checked_utc=datetime.now(timezone.utc).isoformat(),records=verified,mutations=0)
(OUT/'ready-gallery-source-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
