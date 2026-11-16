"""Durable publication intents and receipts for this authorised batch."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import sys

OUT=Path(__file__).resolve().parent
records=json.loads((OUT/'posts.json').read_text())
mode, number, platform=sys.argv[1:4]
p=records[int(number)-1]
name=f'{platform}-{int(number):02d}'
stamp=lambda:datetime.now(timezone.utc).isoformat()
if mode=='intent':
    path=OUT/(name+'-intent.json')
    payload={'status':'PUBLISH_INTENT','utc':stamp(),'catalogue_id':p['catalogue_id'],
       'sku':p['sku'],'title':p['title'],'platform':platform,'media_sha256':p['sha256'],
       'captions':{k:p['captions'][k] for k in (['facebook','instagram'] if platform=='meta' else [platform])},
       'user_authorization':'Post a new 5 to all platforms',
       'duplicate_check':'Saved batch receipts excluded; Meta title search had no matching recent posts.',
       'tag_title':p['title'] if platform=='meta' else None,
       'tag_price_gbp':p['price_gbp'] if platform=='meta' else None}
    assert hashlib.sha256(Path(p['media_path']).read_bytes()).hexdigest()==p['sha256']
    with path.open('x') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    print('INTENT SAVED',name,p['title'])
elif mode=='receipt':
    data=json.loads(sys.argv[4]);assert data.get('url')
    data={'status':'PUBLISHED_NATIVE_READBACK','verified_utc':stamp(),
          'catalogue_id':p['catalogue_id'],'sku':p['sku'],'title':p['title'],**data}
    path=OUT/(name+'-receipt.json')
    with path.open('x') as f:
        json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    group=[json.loads(q.read_text()) for q in sorted(OUT.glob(platform+'-??-receipt.json'))]
    (OUT/(platform+'-publication-receipts.json')).write_text(json.dumps(group,ensure_ascii=False,indent=2)+'\n')
    print('RECEIPT SAVED',name,data['url'])
else: raise ValueError(mode)
