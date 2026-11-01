from pathlib import Path
import csv,json
OUT=Path(__file__).resolve().parent
OLD=OUT.parent/'01a13fe6-495b-7253-b923-31823b4cbca8/squarespace-replacement-20261030'
read=lambda p:json.loads(p.read_text())
snapshot=read(OUT/'catalogue-snapshot-latest.json')
plan=read(OUT/'website-final-plan.json')
original=read(OLD/'replacement-plan.json')
native=list(csv.DictReader((OUT/'inventory-after.csv').open(encoding='utf-8-sig')))
native_by_id={r['Product ID [Non Editable]']:r for r in native if r['Product ID [Non Editable]']}
products={p['id']:p for p in snapshot['products']}
hash_by_id={a['image_id']:a['content_hash'] for p in original['products'] for a in p['image_rows']}
old_checks=read(OLD/'uploaded-photo-content-verification.json')['checks']
native_by_url={a['native_url']:dict(a,content_hash=hash_by_id[a['image_id']]) for a in old_checks}
result=[]
for prior in plan['products']:
 if not prior.get('product_id'):continue
 p=products[prior['catalogue_id']]
 images={r['image']['id']:r for r in snapshot['images'] if r['product_id']==p['id'] and r['scope']=='Associated' and not r['image']['excluded'] and not r['image']['withheld_reasons']}
 listing=[x for x in p['photos']['listing_ids'] if x in images]
 primary=p['photos'].get('primary_id')
 if primary in listing:listing=[primary]+[x for x in listing if x!=primary]
 situ=[x for x in p['photos']['in_situ_ids'] if x in images]
 gallery=[];seen=set()
 for aid in listing+situ:
  r=images[aid];a=r['image'];h=a['original']['dropbox_content_hash'];assert h
  if h in seen:continue
  seen.add(h);gallery.append({'image_id':aid,'content_hash':h,'name':a['name'],'path':a['provenance']['path'],'bytes':a['original']['bytes'],'alt':r['choice'].get('alt') or p['retail_name']+(' - in situ' if aid in situ else ''),'role':'primary' if aid==primary else ('listing' if aid in listing else 'in_situ')})
 urls=native_by_id[prior['product_id']]['Hosted Image URLs'].split()
 old_images=[native_by_url[u] for u in urls if u in native_by_url]
 assert len(old_images)==len(urls),(p['id'],len(old_images),len(urls))
 wanted_listing=[a for a in gallery if a['role']!='in_situ']
 listing_changed=[a['content_hash'] for a in old_images]!=[a['content_hash'] for a in wanted_listing]
 result.append({'catalogue_id':p['id'],'product_id':prior['product_id'],'variant_id':prior['variant_id'],'name':p['name'],'retail_name':p['retail_name'],'public':prior['public'],'website_url':prior['website_url'],'primary_id':primary,'gallery':gallery,'existing':old_images,'listing_changed':listing_changed,'listing_count':len(wanted_listing),'in_situ_count':len(gallery)-len(wanted_listing)})
payload={'snapshot_utc':snapshot['created_utc'],'event_cutoff':snapshot['event_cutoff'],'products':result}
(OUT/'all-image-plan.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
print(json.dumps({'products':len(result),'listing_gallery_changes':sum(p['listing_changed'] for p in result),'listing_placements':sum(p['listing_count'] for p in result),'in_situ_placements':sum(p['in_situ_count'] for p in result),'max_gallery':max(len(p['gallery']) for p in result),'changed':[{'id':p['catalogue_id'],'name':p['name'],'before':len(p['existing']),'after':p['listing_count']} for p in result if p['listing_changed']]},indent=2))
