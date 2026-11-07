"""Compare the dated native active table with the current catalogue, without writes."""
import hashlib
import json
import math
import re
import sys
import unicodedata
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx
pointer=json.loads((ROOT/'sculpture-catalogue/current-master.json').read_text())['current_app_review_workbook']
workbook=Path(pointer['path'])
assert hashlib.sha256(workbook.read_bytes()).hexdigest()==pointer['sha256']
book=Xlsx(workbook)
headers={book.value('Wall Sculptures',c):re.sub(r'\d+','',c) for c in book.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7',c)}
rows={str(book.value('Wall Sculptures','AQ'+str(n))):n for n in range(8,189)}
publication=json.loads((OUT/'full-gallery-reconciliation.json').read_text())['records']
historical=json.loads((ROOT/'outputs/catalogue-marketplace-publication-20261101/catalogue-copy-disclosures/ebay-sapr-active-targets.json').read_text())
publication_ids={r['catalogue_id'] for r in publication}|{r['source']['catalogue_id'] for r in historical if r.get('source')}
assert len(publication_ids)==176
source=OUT.parent/'resume-0041/ebay-active-extracted.json'
native=json.loads(source.read_text())['rows']
normalize=lambda s:' '.join(unicodedata.normalize('NFKC',s).replace('—','-').replace('–','-').casefold().split())
records=[];unmatched=[]
for observed in native:
    sku=observed.get('sku')
    row=rows.get(sku)
    if not row or book.value('Wall Sculptures','AA'+str(row)) not in publication_ids:
        unmatched.append(observed)
        continue
    value=lambda key:book.value('Wall Sculptures',headers[key]+str(row))
    price=float(observed['price_gbp']);target=float(value('ebay_price_gbp'))
    assert math.isfinite(price) and price>0 and math.isfinite(target) and target>0
    records.append(dict(sku=sku,catalogue_id=value('Product ID'),native_id=observed['native_id'],
                        observed_title=observed['title'],catalogue_title=value('ebay_catalogue_title'),
                        observed_price_gbp=price,catalogue_price_gbp=target,
                        price_differs=abs(price-target)>.005,
                        title_differs=normalize(observed['title'])!=normalize(value('ebay_catalogue_title')),
                        status='DATED_NATIVE_ACTIVE_OBSERVATION_FRESH_NATIVE_CHECK_REQUIRED_BEFORE_REVISION'))
assert len(records)==110 and len({r['sku'] for r in records})==110
result=dict(status='DATED_NATIVE_ACTIVE_TABLE_RECONCILED_NO_WRITES',checked_utc=datetime.now(timezone.utc).isoformat(),
            native_snapshot_file_utc=datetime.fromtimestamp(source.stat().st_mtime,timezone.utc).isoformat(),
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),workbook_sha256=pointer['sha256'],
            matched_current_publication_products=len(records),unmatched_or_outside_component_scope=len(unmatched),
            price_differences=sum(r['price_differs'] for r in records),title_differences=sum(r['title_differs'] for r in records),
            records=records,scope='Only the dated native active-table observation. It is not a fresh public checkout or editor readback and does not authorize blind changes.',
            native_writes=0)
(OUT/'active-native-inventory-reconciliation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
print(json.dumps([r for r in records if r['price_differs'] or r['title_differs']],indent=2))
