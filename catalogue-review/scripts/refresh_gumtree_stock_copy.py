"""Apply the owner's exact stock confirmation to the prepared Gumtree copy."""
import html
import json
from pathlib import Path
import re
import sys

out=Path(sys.argv[1]).resolve()
packet=json.loads((out/'gumtree-ready.json').read_text())
confirmation=json.loads((out/'gumtree-owner-stock-confirmation.json').read_text())
assert confirmation['owner_statement']=='Yes, all 176 are physically available in the UK'
assert len(packet['records'])==176 and len({r['catalogue_id'] for r in packet['records']})==176
dispatch='Dispatch time: If Gumtree Delivery is offered and selected, the item will be packaged and sent within seven calendar days of payment. For separately arranged delivery, the dispatch date must be agreed before purchase. Carrier transit time is additional.'
delivery='Delivery: Inspection and collection in the UK are available by arrangement. If Gumtree Delivery is offered and selected, its checkout delivery charge applies. Otherwise, any delivery service, charge and timing must be agreed before purchase.'
for record in packet['records']:
    text=record['description']
    text,n=re.subn(r'^Availability:.*$', 'Availability: Finished sculpture physically available in the UK; inspection and collection by arrangement.',text,flags=re.M)
    assert n==1
    text,n=re.subn(r'^Dispatch time:.*$',dispatch,text,flags=re.M)
    assert n==1
    text,n=re.subn(r'^Delivery:.*$',delivery,text,flags=re.M)
    assert n==1
    assert '10 working days' not in text and not re.search(r'made.to.order',text,re.I)
    record['description']=text
    record['actual_uk_possession_confirmed']=True
(out/'gumtree-ready.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
first_path=out/'gumtree-first-ad.json'
if first_path.exists():
    old=json.loads(first_path.read_text())
    first=next(r for r in packet['records'] if r['sku']==old['sku'])
    first.update({k:old[k] for k in ('primary_upload_path','primary_sha256')})
    first_path.write_text(json.dumps(first,ensure_ascii=False,indent=2)+'\n')
body=['<!doctype html><html lang="en"><meta charset="utf-8"><title>Boldstone Gumtree adverts</title><style>body{font:16px/1.5 system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#26342b}article{border-top:1px solid #bbc8bb;padding:24px 0}.photos{display:flex;gap:8px;overflow:auto}img{height:160px;width:160px;object-fit:contain;background:#f5f5ee}pre{white-space:pre-wrap;font:inherit}</style><h1>Gumtree product and service adverts</h1><p>176 products confirmed physically available in the UK by the owner, plus one bespoke sculpture-making service. No adverts have been published in this run. Collection postcode and native business posting fields remain to be checked.</p>']
for record in packet['records']+[packet['service_ad']]:
    price='£%.2f'%record['price_gbp'] if 'price_gbp' in record else 'Quote per commission'
    body.append('<article><h2>'+html.escape(record['title'])+'</h2><p>'+html.escape(record['sku'])+' · '+price+'</p><div class="photos">'+''.join('<img loading="lazy" src="'+html.escape(url,quote=True)+'" alt="'+html.escape(record['title'],quote=True)+'">' for url in record['image_urls'][:20])+'</div><pre>'+html.escape(record['description'])+'</pre></article>')
body.append('</html>')
(out/'gumtree-ad-review.html').write_text(''.join(body))
print(json.dumps(dict(product_records=176,service_adverts=1,stock_copy_updated=True,dispatch_copy_checked=True,native_published_this_run=0)))
