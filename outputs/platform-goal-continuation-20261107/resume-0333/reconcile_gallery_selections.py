import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
app=json.loads((OUT/'app-specifications.json').read_text());products={p['id']:p for p in app['products']}
targets=json.loads((ROOT/'outputs/catalogue-marketplace-publication-20261101/catalogue-copy-disclosures/ebay-sapr-66-draft-targets.json').read_text())
results=[]
for t in targets:
    p=products[t['source']['catalogue_id']]
    old=t['source']['photos'][:24]
    current=[p['photos']['primary_listing']['image_id']]
    hashes={}
    for kind in ['listing','in_situ']:
        for image in p['photos'].get(kind,{}).get('images',[]):
            hashes[image['id']]=image['original'].get('dropbox_content_hash')
            if image['id'] not in current:current.append(image['id'])
    current=current[:24];previous=[i['id'] for i in old]
    changed_hashes=[i['id'] for i in old if i['id'] in hashes and hashes[i['id']]!=i.get('content_hash')]
    same=previous==current and not changed_hashes
    results.append(dict(sku=t['sku'],catalogue_id=p['id'],title=p['retail_name'],
                        historical_gallery_count=len(previous),current_selected_count=len(current),
                        selected_ids_or_order_changed=previous!=current,changed_content_hashes=changed_hashes,
                        historical_gallery_ids=previous,current_gallery_ids=current,
                        status='UNCHANGED_SOURCE_MANIFEST_NATIVE_COUNT_CHECK_STILL_REQUIRED' if same else 'REPLACE_GALLERY_FROM_CURRENT_SELECTIONS'))
result=dict(checked_utc=datetime.now(timezone.utc).isoformat(),records=results,
            changed_selection_records=sum(r['status'].startswith('REPLACE') for r in results),
            unchanged_selection_records=sum(r['status'].startswith('UNCHANGED') for r in results),
            scope='Compare exact original IDs, order and content hashes from the original 66-draft import source to the current app. This is source reconciliation, not native gallery identity verification.')
(OUT/'ebay-gallery-selection-reconciliation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
print(json.dumps([dict(sku=r['sku'],title=r['title'],old=r['historical_gallery_count'],current=r['current_selected_count']) for r in results if r['status'].startswith('REPLACE')],indent=2))
