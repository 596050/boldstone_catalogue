"""Prepare an exact 50-product owner preview and an unassigned GTIN register."""
import csv
import hashlib
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx
from channel_content import finish_retail_name,values
read=lambda p:json.loads(Path(p).read_text())
pointer=read(ROOT/'sculpture-catalogue/current-master.json')
source=pointer['current_app_review_workbook']
assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()==source['sha256']
book=Xlsx(source['path'])
headers={book.value('Wall Sculptures',a):re.sub(r'\d','',a) for a in book.cells['Wall Sculptures'] if re.fullmatch('[A-Z]+7',a)}
app=read(OUT/'app-specifications.json');products={p['id']:p for p in app['products']}
rows={book.value('Wall Sculptures','AA'+str(r)):r for r in range(8,189)}
cell=lambda field,r:book.value('Wall Sculptures',headers[field]+str(r))
native=(OUT/'brandboom-fifty-final-native.txt').read_text()
assert '50  /  50' in native and '/p/681160' in native
main=native.split('content list\n',1)[0]
pairs=re.findall(r'\d+ text (Boldstone [^\n]+)\n\s*\d+ text ([^\n]+)\n\s*\d+ container\n\s*\d+ text ([\d,.]+)  GBP',main)
assert len(pairs)==50,len(pairs)
public=read(ROOT/'outputs/catalogue-channel-imports-20261107/google-source-reconciliation.json')['wall_sculpture_matches_detail']
public={r['catalogue_id']:r for r in public}
records=[]
for sequence,(title,sku_text,price) in enumerate(pairs,1):
 matches=[(pid,row) for pid,row in rows.items() if str(cell('brandboom_sku',row)) and (sku_text==str(cell('brandboom_sku',row)) or sku_text.startswith(str(cell('brandboom_sku',row))+' '))]
 assert len(matches)==1,(title,sku_text,matches)
 pid,row=matches[0];p=products[pid];f=values(p)
 assert pid in public and cell('brandboom_name',row)==title,(pid,title)
 assert abs(float(price.replace(',',''))-float(cell('brandboom_wholesale_gbp',row)))<.001
 records.append(dict(sequence=sequence,catalogue_id=pid,sku=cell('brandboom_sku',row),title=finish_retail_name(p),native_title=title,
  native_wholesale_gbp=float(price.replace(',','')),proposed_shared_rrp_gbp=cell('faire_retail_reference_gbp',row),
  current_website_retail_gbp=book.value('Wall Sculptures','H'+str(row)),dimensions=f.get('Dimensions / depth',''),weight=f.get('Weight',''),
  website_url=public[pid]['website_url'],image_url=public[pid]['google_image_link']))
assert len({r['catalogue_id'] for r in records})==50
(OUT/'brandboom-preview50-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
esc=lambda x:html.escape(str(x if x is not None else ''))
money=lambda x:('£'+format(x,',.2f')) if isinstance(x,(int,float)) else 'Not set'
cards=''.join(f'''<article><a href="{esc(r['website_url'])}" target="_blank" rel="noopener"><img loading="lazy" src="{esc(r['image_url'])}" alt="{esc(r['title'])}"></a><div class="copy"><p class="sku">{r['sequence']:02d} · {esc(r['sku'])}</p><h2>{esc(r['title'])}</h2><p>{esc(r['dimensions'])}<br>{esc(r['weight'])}</p><dl><dt>Recorded wholesale</dt><dd>{money(r['native_wholesale_gbp'])}</dd><dt>Proposed shared RRP</dt><dd>{money(r['proposed_shared_rrp_gbp'])}</dd><dt>Current website retail</dt><dd>{money(r['current_website_retail_gbp'])}</dd></dl><a href="{esc(r['website_url'])}" target="_blank" rel="noopener">View sculpture and photographs</a></div></article>''' for r in records)
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone · 50-sculpture preview</title><style>*{box-sizing:border-box}body{margin:0;background:#f7f5ef;color:#273b31;font:16px/1.5 Georgia,serif}header{padding:55px max(5vw,24px);max-width:1350px;margin:auto}header p{max-width:850px}h1{font-size:clamp(32px,5vw,68px);font-weight:400;line-height:1.05}.eyebrow,.sku,dt,dd,a,.note{font-family:Arial,sans-serif}.eyebrow{letter-spacing:.15em;text-transform:uppercase;font-size:12px}.note{padding:16px 20px;background:#e9ecdf;border-left:3px solid #697f5e;font-size:14px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;padding:0 max(5vw,24px) 70px;max-width:1500px;margin:auto}article{background:white;border:1px solid #dce1d6;break-inside:avoid}img{width:100%;height:300px;object-fit:contain;background:#eeede6;display:block}.copy{padding:22px}h2{font-size:23px;font-weight:400;line-height:1.2}.sku{font-size:11px;color:#697567}dl{display:grid;grid-template-columns:1fr auto;font-size:12px;gap:6px}dd{margin:0;font-variant-numeric:tabular-nums}a{color:#35543d;font-size:13px}footer{padding:30px 5vw;text-align:center}@media print{header{padding:20px}main{grid-template-columns:1fr 1fr;padding:0;gap:15px}article{break-inside:avoid}img{height:200px}.note{font-size:11px}a{color:inherit}}</style><header><p class="eyebrow">Boldstone · Sally Price</p><h1>Wall sculptures<br>50-piece preview</h1><p>Handmade reliefs inspired by natural forms, light and shadow, for interiors and gardens. Individual sculptures and coordinating designs, with custom commissions developed in collaboration with Sally Price.</p><p class="note">Private review of Brandboom presentation 681160. Exactly 50 existing products; ordering disabled; no Marketplace submission. Wholesale prices are the recorded Brandboom values. The proposed RRP requires genuine retail alignment before publication. Photographs load from existing public website URLs.</p><p><a href="https://manage.brandboom.com/products/s/111089/p/681160">Open the saved Brandboom draft</a></p></header><main>'''+cards+'''</main><footer>Prepared 8 November 2026. One sculpture per listing. Coordinating pieces and setting props are sold separately.</footer></html>'''
(OUT/'brandboom-50-preview.html').write_text(page)
with (OUT/'gtin-allocation-register.csv').open('w',newline='') as f:
 fields=['catalogue_id','seller_sku','product_name','brand','sale_unit','gtin','gs1_licensee','allocation_source','assignment_status','publication_eligible']
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for pid,row in rows.items():
  w.writerow(dict(catalogue_id=pid,seller_sku=book.value('Wall Sculptures','AQ'+str(row)),product_name=finish_retail_name(products[pid]),brand='Boldstone',sale_unit='One individually described sculpture or panel',gtin='',gs1_licensee='',allocation_source='',assignment_status='Awaiting genuinely assigned GTIN and licence evidence',publication_eligible=pid in public))
shutil.copyfile(source['path'],OUT/'previous-catalogue.xlsx')
(OUT/'source-pointer-before.json').write_text(json.dumps(pointer,indent=2)+'\n')
(OUT/'previous-dropbox-metadata.json').write_text(json.dumps(source['dropbox'],indent=2)+'\n')
print(json.dumps(dict(preview_products=50,unique_skus=50,gtin_register_records=181,gtins_invented=0,source_master_sha256=source['sha256'])))
