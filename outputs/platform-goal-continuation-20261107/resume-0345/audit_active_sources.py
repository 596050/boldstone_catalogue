"""Read-only source comparison; historical offer IDs are not current bindings."""
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
coverage=json.loads((OUT/'app-coverage.json').read_text())['products']
targets=json.loads((ROOT/'outputs/catalogue-marketplace-publication-20261101/catalogue-copy-disclosures/ebay-sapr-active-targets.json').read_text())
records=[]
for target in targets:
    source=target.get('source')
    if not source:
        records.append(dict(sku=target.get('sku'),historical_native_id=target.get('item_id'),status='NO_COMPONENT_SOURCE_BINDING_PRESERVE_EXISTING_OFFER'))
        continue
    pid=source['catalogue_id'];product=coverage.get(pid)
    if not product or product['excluded']:
        records.append(dict(sku=target['sku'],catalogue_id=pid,status='OUTSIDE_CURRENT_COMPONENT_PUBLICATION_SCOPE_PRESERVE_EXISTING_OFFER'))
        continue
    primary=product['primary_listing']['image_id']
    current=list(dict.fromkeys([primary]+product['listing']['image_ids']+product['in_situ']['image_ids']))[:24]
    old=[i['id'] for i in source['photos'][:24]]
    kind=('selection_changed' if set(current)!=set(old) else 'primary_changed' if current[0]!=old[0]
          else 'order_only' if current!=old else 'unchanged')
    records.append(dict(sku=target['sku'],catalogue_id=pid,historical_native_id=target['item_id'],
                        old_count=len(old),full_current_count=len(current),difference_kind=kind,
                        added_ids=[i for i in current if i not in old],removed_ids=[i for i in old if i not in current],
                        status='SOURCE_RECONCILIATION_ONLY_NATIVE_VERIFICATION_REQUIRED'))
counts={kind:sum(r.get('difference_kind')==kind for r in records) for kind in ['unchanged','order_only','selection_changed','primary_changed']}
result=dict(checked_utc=datetime.now(timezone.utc).isoformat(),historical_active_source_records=len(targets),
            scope='Compare stored import source with complete current app IDs. Historical offer IDs are not current bindings. No native writes.',
            difference_counts=counts,records=records)
(OUT/'active-source-gallery-reconciliation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(counts))
print(json.dumps([r for r in records if r.get('difference_kind') in ['selection_changed','primary_changed']],indent=2))
