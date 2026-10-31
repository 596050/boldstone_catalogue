from pathlib import Path
import csv,json,html,re
OUT=Path(__file__).resolve().parent
read=lambda f:json.loads((OUT/f).read_text())
plan=read('website-copy-plan.json');assets={x['filename']:x['src'] for x in read('native-insitu-assets.json')};stage=read('staged-in-situ.json');order=read('insitu-review-order.json')
assert len(assets)==227
assert set(assets)=={x['filename'] for x in stage.values() if x['bytes']<=20000000}
exclude_numbers={62:'Film-frame border and duplicated product shot',64:'Cropped surface detail',70:'Composite close-up details',122:'Unfinished installation / workshop',123:'Unfinished installation / workshop',161:'Close-up detail, not a room setting',202:'Close-up detail',205:'Close-up detail',207:'Workshop process',210:'Close-up detail'}
skips={x['image_id']:exclude_numbers[x['number']] for x in order if x['number'] in exclude_numbers}
with (OUT/'inventory-after-retail.csv').open(encoding='utf-8-sig',newline='') as f:r=csv.DictReader(f);headers=r.fieldnames;native=list(r)
byid={x['Product ID [Non Editable]']:x for x in native if x['Product ID [Non Editable]']};rows=[]
for p in plan['products']:
 if not p.get('product_id'):continue
 before=byid[p['product_id']];assert before['SKU']==p['sku']
 p['website_in_situ']=[];p['website_in_situ_skipped']=[]
 for x in (p['in_situ'] if p.get('public') else []):
  aid=x.get('id',x.get('image_id'));s=stage[aid]
  if aid in skips or s['filename'] not in assets:
   p['website_in_situ_skipped'].append({'id':aid,'reason':skips.get(aid,'Original exceeds Squarespace 20 MB image limit')});continue
  p['website_in_situ'].append({'id':aid,'url':assets[s['filename']].split('?')[0],'original_name':s['original_name'],'dropbox_path':s['path']})
 body=p['website_description_html']
 if p['website_in_situ']:
  body+='<h3>In a setting</h3><p>Styling inspiration showing the sculpture in context. Room settings and group arrangements are illustrative; this listing is for the individual sculpture described above.</p>'
  for n,x in enumerate(p['website_in_situ'],1):
   alt=p['retail_name']+' - styling inspiration '+str(n)
   body+='<p><img src="'+html.escape(x['url']+'?format=1500w',quote=True)+'" alt="'+html.escape(alt,quote=True)+'" loading="lazy" style="max-width:100%;height:auto;" /></p>'
 assert not re.search(r'GFRC|Jesmonite|Royal Mail|Tracked 48|rigid.board|framework metal|cast.composite',body,re.I)
 row=before.copy();row['Title']=p['retail_name'];row['Description']=body;rows.append(row);p['published_description_html']=body
 for k in headers:
  if k not in {'Title','Description'}:assert row[k]==before[k],k
assert len(rows)==178
for name,items in [('squarespace-description-update.csv',rows),('squarespace-description-test.csv',rows[:1])]:
 with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(items)
(OUT/'website-final-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
report={'products_to_update':len(rows),'published':sum(p.get('public',False) for p in plan['products']),'public_with_two_context_images':sum(p.get('public',False) and len(p.get('website_in_situ',[]))==2 for p in plan['products']),'public_with_one_context_image':sum(p.get('public',False) and len(p.get('website_in_situ',[]))==1 for p in plan['products']),'public_without_context_images':sum(p.get('public',False) and not p.get('website_in_situ') for p in plan['products']),'gaps':[{'name':p['retail_name'],'url':p['website_url'],'available':len(p.get('website_in_situ',[])),'skipped':p.get('website_in_situ_skipped',[])} for p in plan['products'] if p.get('public') and len(p.get('website_in_situ',[]))<2]}
(OUT/'website-photo-readiness.json').write_text(json.dumps(report,indent=2));print({k:v for k,v in report.items() if k!='gaps'})
