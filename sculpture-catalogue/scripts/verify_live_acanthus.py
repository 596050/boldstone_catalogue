import hashlib,html,json,re
from html.parser import HTMLParser
from pathlib import Path
project=Path(__file__).resolve().parents[1];ev=project/'evidence';folder=ev/'live-acanthus'
source=json.loads((ev/'catalogue_source_tables_2026-10-15.json').read_text())
native={r['Product ID [Non Editable]']:r for r in source['SS Wall Products']}
class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
def plain(value):
    p=Text();p.feed(value);return re.sub(r'\s+',' ',''.join(p.parts)).strip()
rows=[]
for receipt in json.loads((folder/'receipts.json').read_text()):
    if receipt.get('status')!=200:continue
    p=folder/(receipt['id']+'.html');text=p.read_text()
    assert re.search(r'data-product-id="'+receipt['id']+'"',text),'Live native product identity differs'
    bodies=re.findall(r'<div class="product-description[^\"]*">(.*?)</div>',text,re.S)
    bodies=list(dict.fromkeys(plain(x) for x in bodies))
    products=[]
    for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',text,re.S):
        value=json.loads(raw)
        if value.get('@type')=='Product':products.append(value)
    assert len(products)==1
    product=products[0];o=product['offers'];assert o['sku']==native[receipt['id']]['SKU']
    rows.append(dict(product_id=receipt['id'],url=receipt['url'],observed='2026-10-16',http_status=200,html_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),live_native_id_confirmed=True,public_product_name=product['name'],public_short_description=product['description'],public_descriptions=bodies,export_body_matches_live=plain(native[receipt['id']]['Description']) in bodies,sku=o['sku'],price=o['price'],currency=o['priceCurrency'],availability=o['availability'],availability_scope='Public commerce availability only; manufactured quantity not established',additional_specification_block_found=False))
(ev/'live_acanthus_verification.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
print(json.dumps([dict(product_id=r['product_id'],sku=r['sku'],body_matches=r['export_body_matches_live'],price=r['price'],currency=r['currency']) for r in rows]))
