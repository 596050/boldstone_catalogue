"""Independent file readback of full-selection native save receipts."""
import hashlib
import json
import re
from datetime import datetime,timezone
from pathlib import Path

OUT=Path(__file__).parent
full=json.loads((OUT/'full-gallery-reconciliation.json').read_text())
source={r['sku']:r for r in full['records']}
receipts=json.loads((OUT/'full-gallery-native-receipts.json').read_text())
assert len(receipts)==len({r['native_draft_id'] for r in receipts})
verified=[]
for receipt in receipts:
    target=source[receipt['sku']]
    text=Path(receipt['evidence']).read_text()
    assert 'draftId='+receipt['native_draft_id'] in text
    assert re.search(r'text field \(settable\) Custom label \(SKU\), Value: '+re.escape(receipt['sku'])+r'$',text,re.M)
    count=int(re.search(r'text (\d+) out of 25 photos or videos uploaded',text)[1])
    assert count==receipt['photos']==len(target['desired_gallery_ids'])
    controls=[int(m[1]) for m in re.finditer(r'^\s*\d+ button Edit or view photo (\d+)$',text,re.M)]
    assert controls==list(range(1,count+1))
    assert re.search(r'^\s*\d+ button Select$',text,re.M)
    assert not re.search(r'image Loading|Uploading|uploading|progress indicator',text)
    assert receipt['photo_ids']==target['desired_gallery_ids']
    lookup={p['id']:p for p in target['image_sources']}
    assert receipt['source_content_hashes']==[lookup[aid]['original']['dropbox_content_hash'] for aid in target['desired_gallery_ids']]
    native_order=receipt.get('native_gallery_source_order_ids',receipt['photo_ids'])
    assert set(native_order)==set(target['desired_gallery_ids']) and native_order[0]==target['desired_gallery_ids'][0]
    assert receipt['primary_id']==target['desired_gallery_ids'][0]
    assert not receipt['published']
    verified.append(dict(sku=receipt['sku'],native_draft_id=receipt['native_draft_id'],photos=count,
                         evidence_sha256=hashlib.sha256(text.encode()).hexdigest(),status='PASS_REOPENED_NATIVE_COUNT_AND_COMPLETE_SOURCE_SELECTION'))
result=dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),verified_existing_drafts=len(verified),
            verified_photo_placements=sum(r['photos'] for r in verified),records=verified,
            scope='Saved native draft IDs, SKU, completed photo controls, persisted count and controlled exact-original source manifest. Native eBay image byte/ID extraction is not available.',
            public_visibility_implied=False,new_listings_created=0)
(OUT/'full-gallery-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
