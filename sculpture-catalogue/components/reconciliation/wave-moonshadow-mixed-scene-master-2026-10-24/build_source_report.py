"""Publish source-level corroboration, keeping current catalogue/physical authority separate."""
import csv,hashlib,html,json,re
from pathlib import Path
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda v:html.escape(str(v),quote=True)
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
g=read(H/'canonical-master-register.json');v=g['current_authenticated_squarespace_inventory_observation'];r=read(H/'report-verification.json');opts={o['product_id']:o for o in g['options']};cards=[];rows=[]
for x in v['retained_offer_observations']:
 t=x['observed_native_source_tuple'];fields={f['field']:f for f in x['fields']};title=fields['Title']['current_csv_value_raw'];links=[]
 for oid in x['existing_related_option_ids']:
  o=opts[oid]
  if o.get('image_url'):links.append('<p>'+esc(o['name'])+': <a href="'+esc(o['image_url'])+'">Catalogue image</a> · <a href="'+esc(o['folder_url'])+'">Containing folder</a>. Existing qualified association retained.</p>')
 rawrows=''.join('<tr><th>'+esc(f['field'])+'</th><td>'+esc(f['current_csv_value_raw'])+'</td><td>'+esc(f['comparison'])+'</td></tr>'for f in x['fields'])
 cards.append('<article id="'+esc(x['offer_ref'])+'"><h2>'+esc(x['offer_ref'])+' '+esc(title)+'</h2><p>Squarespace product '+esc(t['product_id'])+'; variant '+esc(t['variant_id'])+'; source SKU '+esc(t['sku_raw'])+'.</p><p><a href="'+esc(x['observed_source_url'])+'">Source listing URL</a></p>'+''.join(links)+'<details><summary>Nine retained raw-field comparisons</summary><table>'+rawrows+'</table></details></article>')
 rows.append({'offer_ref':x['offer_ref'],'squarespace_product_id':t['product_id'],'squarespace_variant_id':t['variant_id'],'source_sku':t['sku_raw'],'source_capture_utc':v['squarespace_source_clock']['captured_utc'],'source_record_locator':json.dumps(x['source_record_locator'],ensure_ascii=False),'existing_related_option_ids':'\n'.join(x['existing_related_option_ids']),'new_exact_individual_configuration_verified':False,'new_physical_verification':False})
css='body{font:17px Arial;line-height:1.5;max-width:1100px;margin:40px auto;padding:0 20px;color:#202020}article{border-top:1px solid #aaa;margin-top:30px;padding-top:15px}td,th{padding:9px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}'
qual=''.join('<li>'+esc(q)+'</li>'for q in v['qualifications'])
page=OUT/'captured-platform-source-observations.html';page.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Captured platform source observations</title><style>'+css+'</style></head><body><h1>Captured platform source observations</h1><p>80 retained Squarespace source product-ID/SKU joins and720 raw-field comparisons corroborated against the authenticated Physical inventory capture at '+esc(v['squarespace_source_clock']['captured_utc'])+'. The export scope is208 products/376 variants; it is not a sculpture count.37 Shopify comparisons use historical source records. No new individual configuration or physical verification.</p><ul>'+qual+'</ul>'+''.join(cards)+'</body></html>')
page.write_text(page.read_text().replace('</h1>','</h1>'+'<p><a href="Captured_Squarespace_Source_Joins_80.csv" download>Download80 Squarespace source joins</a> · <a href="Historical_Shopify_Current_Squarespace_Source_Pairs_37.csv" download>Download37 historical Shopify/Squarespace source pairs</a></p>',1))
r['pages'].append({'path':str(page),'sha256':sha(page),'cards':80})
def csvout(name,data):
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 r['csv_files'].append({'path':str(p),'sha256':sha(p),'rows':len(data)})
csvout('Captured_Squarespace_Source_Joins_80.csv',rows)
pairs=[]
for x in v['historical_shopify_comparison']['pairs']:
 t=x['fresh_squarespace_variant'];pairs.append({'historical_shopify_handle':x['historical_shopify_handle'],'historical_shopify_sku':x['historical_shopify_variant']['sku_raw'],'squarespace_product_id':t['product_id'],'squarespace_variant_id':t['variant_id'],'squarespace_sku':t['sku_raw'],'historical_shopify_source':json.dumps(x['historical_shopify_variant']['source_locator'],ensure_ascii=False),'squarespace_capture_utc':v['squarespace_source_clock']['captured_utc'],'current_shopify_inventory_verified':False,'exact_individual_configuration_verified':False})
csvout('Historical_Shopify_Current_Squarespace_Source_Pairs_37.csv',pairs)
# Expose the source report from each current navigation page without rewriting source statements.
for item in r['pages']:
 p=Path(item['path'])
 if p==page:continue
 text=p.read_text();text=text.replace('</h1>','</h1><p><a href="captured-platform-source-observations.html">Captured Squarespace source observations and historical Shopify comparisons</a></p>',1);p.write_text(text);item['sha256']=sha(p)
r['counts'].update(source_product_sku_observations_added=80,historical_shopify_pair_observations_added=37,new_exact_individual_configuration_matches=0,owner_depiction_corrections_this_refresh=0);r['register_sha256']=sha(H/'canonical-master-register.json');write(H/'report-verification.json',r)
c=read(OUT/'current-count-summary.json');c['latest_authenticated_source_observation_import']=g['latest_authenticated_source_observation_import'];write(OUT/'current-count-summary.json',c)
print('Source report saved:80 source joins,720 field observations,37 historical Shopify pairs; no authority or price adoption')
