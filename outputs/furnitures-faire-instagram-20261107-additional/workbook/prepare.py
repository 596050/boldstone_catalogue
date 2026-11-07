import json,re,sys
from pathlib import Path

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent;RUN=OUT.parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx
x=Xlsx(OUT/'previous-catalogue.xlsx');sheet='Wall Sculptures'
headers={x.value(sheet,a):re.sub(r'\d','',a) for a in x.cells[sheet] if re.fullmatch(r'[A-Z]+7',a)}
rows={x.value(sheet,'AA'+str(n)):n for n in range(8,189)}
faire=json.loads((RUN/'faire-price-reconciliation.json').read_text())
posts=json.loads((RUN/'instagram-five-posts.json').read_text())
assert len(faire['records'])==176 and not faire['differences']
assert len(posts)==5 and all(p['status']=='PUBLISHED_VERIFIED' and p['product_tag_saved'] and p['permalink'] for p in posts)
patches=[]
def patch(pid,key,value):
    cell=headers[key]+str(rows[pid]);before=x.value(sheet,cell)
    if before!=value:patches.append(dict(sheet=sheet,cell=cell,before=before,value=value))
for r in faire['records']:
    pid=r['catalogue_id']
    for field,key in [('faire_native_wholesale_gbp','wholesale_gbp'),('faire_native_retail_gbp','retail_gbp')]:
        assert abs(float(x.value(sheet,headers[field]+str(rows[pid])))-r[key])<.001
    patch(pid,'faire_native_checked_utc','Checked UTC: '+faire['checked_utc'])
    patch(pid,'faire_native_price_source','Fresh native product export, 7 November 2026: https://www.faire.com/brand-portal/my-shop/products/bulk-uploader . Exact product-token and SKU reconciliation for all 176 published products. Native GBP wholesale and retail prices match the recorded values. Onboarding requirements retained from 6 November 2026.')
    patch(pid,'faire_pricing_action','7 November 2026: fresh native export confirms published products and unchanged GBP wholesale/retail prices. Native prices remain separate from the profit-protection model. Reconcile the recorded retail and wholesale channel differences before changing prices; existing app retail and protected targets preserved.')
for p in posts:
    pid=p['catalogue_id']
    assert x.value(sheet,'AQ'+str(rows[pid]))==p['sku']
    for field,value in dict(instagram_post_url=p['permalink'],instagram_native_post_id=p['native_id'],
        instagram_product_tag_sku=p['sku'],instagram_published_status='Published on Instagram; native Published row and permalink verified. Current selected original used, full caption checked before publishing, exact design/finish product tag and alt text saved.',
        instagram_checked_utc='Checked UTC: '+p['verified_utc']).items():patch(pid,field,value)
plan=dict(scope='Refresh 176 Faire native price verification dates and provenance from the fresh native export, preserving actual prices and protected model targets. Record five new product-tagged Instagram publications. All other catalogue data, app prices, manufacturing costs, zero labour, selected photo purposes, formulas and workbook features remain unchanged.',
          patches=patches,faire_products_verified=176,new_instagram_publications=5,
          new_native_publications_recorded=0,new_native_drafts_recorded=0,
          previews=[dict(range='UX7:UY11',name='faire-prices'),dict(range='VD7:VD10',name='faire-checked'),
                    dict(range='ST'+str(rows[posts[0]['catalogue_id']])+':SX'+str(rows[posts[0]['catalogue_id']]),name='instagram-coral')])
(OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(patches=len(patches),faire_products=176,instagram_posts=5)))
