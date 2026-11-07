"""Reconcile both complete native portfolio pages against the unchanged scope."""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx
from prepare_saatchi_catalogue import native_artwork_bindings

read=lambda p:json.loads(p.read_text())
normal=lambda s:re.sub(r'[^a-z0-9]+','',s.casefold())
pattern=re.compile(r'\ufffc+([^\ufffc]+?)Sculpture([\d.]+ W x [\d.]+ H x [\d.]+ D centimeters)(Published|Draft)\ufffc*([A-Za-z]{3} \d{1,2}, \d{4})(\$[\d,]+|--)\ufffc*(For Sale|Not For Sale)')
records=[]
for number,count in [(1,100),(2,27)]:
    path=OUT/f'saatchi-current-portfolio-page{number}.txt'
    text=path.read_text()
    selected=re.search(r'Selected text: ```\n([\s\S]*?)\n```',text).group(1)
    matches=list(pattern.finditer(selected))
    assert len(matches)==count
    for match in matches:
        title,dimensions,status,date,price,availability=match.groups()
        records.append(dict(title=title.strip(),dimensions=dimensions,status=status,date=date,
            price_usd=None if price=='--' else float(price[1:].replace(',','')),availability=availability,
            source=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
assert len(records)==len({normal(r['title']) for r in records})==127
assert sum(r['status']=='Published' for r in records)==126
assert [r['title'] for r in records if r['status']=='Draft']==['Gleneagles Vine II - White']
assert all(r['availability']=='For Sale' and r['price_usd']>0 for r in records if r['status']=='Published')
queue=read(OUT/'remaining-native-ready-queue.json')
assert len(queue)==14 and not any(normal(r['packet']['title']) in {normal(n['title']) for n in records} for r in queue)
result=dict(status='PASS_CURRENT_WHOLE_PORTFOLIO_126_PUBLISHED_ONE_DRAFT',checked_utc=datetime.now(timezone.utc).isoformat(),
    total_native_artworks=127,published=126,drafts=1,duplicates_by_normalized_title=0,
    qualified_queue_absent=14,scope='Complete visible native pages:100 and27 records. Native portfolio presence, title, price and sale state only.',records=records)
(OUT/'saatchi-fresh-whole-portfolio.json').write_text(json.dumps(result,indent=2)+'\n')

registry_path=ROOT/'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
bindings=native_artwork_bindings(registry_path)
source=read(ROOT/'outputs/catalogue-marketplace-publication-20261101/current-prepared-catalogue.json')['records']
assert len(source)==176 and len(bindings)==127
aliases={}
def alias(title,sku):
    key=normal(title)
    assert key not in aliases or aliases[key]==sku, ('Ambiguous recorded title',title)
    aliases[key]=sku
for r in source:alias(r['title'],r['sku'])
for r in read(registry_path):alias(r['title'],r['sku'])
pointer=read(ROOT/'sculpture-catalogue/current-master.json')['current_app_review_workbook']
x=Xlsx(Path(pointer['path']));sheet='Wall Sculptures'
headers={x.value(sheet,a):re.sub(r'\d','',a) for a in x.cells[sheet] if re.fullmatch('[A-Z]+7',a)}
rows={x.value(sheet,'AQ'+str(r)):r for r in range(8,189)}
comparisons,unmatched=[],[]
for r in records:
    sku=aliases.get(normal(r['title']))
    if sku not in bindings:
        unmatched.append(r['title']);continue
    target=x.value(sheet,headers['saatchi_asking_price_usd']+str(rows[sku]))
    assert isinstance(target,(int,float)) and target>0
    comparisons.append(dict(sku=sku,native_artwork_id=bindings[sku],title=r['title'],status=r['status'],
        observed_price_usd=r['price_usd'],catalogue_target_usd=target,
        difference=None if r['price_usd'] is None else round(r['price_usd']-target,2),
        match_basis='Unique exact normalized recorded title and existing SKU/artwork binding. Recheck the exact artwork ID before changing it.'))
differences=[r for r in comparisons if r['status']=='Published' and r['observed_price_usd']!=r['catalogue_target_usd']]
price_audit=dict(status='READ_ONLY_PRICE_COMPARISON_NATIVE_ID_RECHECK_REQUIRED',checked_utc=result['checked_utc'],
    matched=len(comparisons),unmatched=unmatched,published_price_differences=len(differences),
    source_workbook_sha256=pointer['sha256'],records=comparisons,differences=differences,native_writes=0)
(OUT/'saatchi-price-comparison.json').write_text(json.dumps(price_audit,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'}))
print(json.dumps(dict(matched=len(comparisons),unmatched=unmatched,published_price_differences=len(differences),
    sample=differences[:5]),ensure_ascii=False))
