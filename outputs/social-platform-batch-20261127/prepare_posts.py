"""Freeze five original-photo posts and authorize only Google and LinkedIn."""
from pathlib import Path
import json,sys,sqlite3,hashlib
from bs4 import BeautifulSoup
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
from settings import Settings
COPY={
 'BSI-2246CBC9C94E':('An elongated crescent, traced by light.',
  'A broad curved relief sweeps down the tall panel of Lava Moon III. Its textured crescent meets a smoother background, creating a strong line of shadow along the curve.',
  'Tall pale Lava Moon III panel with a broad textured crescent sweeping down one side against a smoother rectangular background.'),
 'BSI-8035F91E2A67':('A rounded form embraced by a crescent.',
  'A rounded central form sits inside a sweeping crescent in Crater Moon II. Recessed curves and a raised circular surface bring light and shadow into a compact square relief.',
  'Square pale Crater Moon II relief with a raised rounded centre and a broad crescent-shaped curve around it.'),
 'BSI-CBD8D0C8DE19':('A small basin holding a reflection of the sky.',
  'A deep circular hollow opens within the square form of Crater Moon Basin. Photographed on grass, its water reflects the clouds above while the broad rim frames a quiet pool of colour.',
  'Square pale Crater Moon Basin with a circular hollow containing water that reflects clouds, photographed on grass.'),
 'BSI-4515726BBC18':('A spiral opening within a square border.',
  'An inward-curling spiral expands across Lunar Phase II, held within the straight edges of a square frame. Fine texture and a deep curved recess bring depth to the pale composition.',
  'Square pale Lunar Phase II relief with a large inward-curling spiral enclosed by a raised rectangular border.'),
 'BSI-70C7029C1DB1':('A circular hollow shaped by light and shadow.',
  'A deep circular hollow opens within the square panel of Lunar Water Catcher. The curved inner surface catches light along its rim and casts a broad shadow across the pale relief.',
  'Pale square Lunar Water Catcher relief with a deep circular hollow, a curved inner surface and a broad shadow across its upper section.')}

settings=Settings();rows=json.loads((OUT/'selected-products.json').read_text());assert {r['catalogue_id'] for r in rows}==set(COPY)
db=sqlite3.connect((ROOT/'social-publisher/state/outbox.sqlite3').as_uri()+'?mode=ro',uri=True)
posts=[];publishing=[];drafts=[];verified=[]
for row in rows:
 pid=row['catalogue_id'];assert row['photo']['primary_eligible'] and not row['photo']['withheld_reasons']
 assert not db.execute('select id from jobs where post_key=?',(pid,)).fetchone()
 assert not db.execute("select id from jobs where lower(json_extract(payload,'$.caption')) like ?",('%'+row['title'].lower()+'%',)).fetchone()
 page=OUT/(pid+'-product.html');raw=page.read_bytes();soup=BeautifulSoup(raw,'html.parser');products=[]
 for script in soup.select('script[type="application/ld+json"]'):
  try:product=json.loads(script.get_text())
  except ValueError:continue
  if product.get('@type')=='Product':products.append(product)
 assert len(products)==1;product=products[0];offer=product['offers']
 assert product['name'].removesuffix(' — boldstone')==row['title'] and float(offer['price'])==row['price_gbp'] and offer['priceCurrency']=='GBP' and offer['sku']==row['sku'] and offer['url']==row['website_url']
 verified.append({'catalogue_id':pid,'status':200,'title':row['title'],'price_gbp':row['price_gbp'],'website_url':row['website_url'],'page_sha256':digest(raw),'verified_utc':utc()})
 path=Path(row['delivery_media_path']);sha=digest(path.read_bytes());assert sha==row['delivery_sha256'] and path.stat().st_size<5000000
 assert digest(Path(row['original_media_path']).read_bytes())==row['original_sha256']
 opening,description,alt=COPY[pid];dimensions=row['fields']['Dimensions / depth'].split('; four-panel arrangement',1)[0]
 unit='One individual basin by Boldstone, designed by Sally Price. The surrounding garden is shown for context.' if pid=='BSI-CBD8D0C8DE19' else 'One individual sculpture by Boldstone, designed by Sally Price. Companion pieces are sold separately.'
 common=row['title']+'\n\n'+opening+'\n\n'+description+'\n\nDimensions: '+dimensions+'.\nMade from a gypsum-based material.\n'+unit
 url=row['website_url'];captions={
  'facebook':common+'\n\nExplore this sculpture through the product tag or visit: '+url+'\n\n#Boldstone #SallyPrice #WallSculpture #Sculpture',
  'threads':row['title']+'\n\n'+opening+'\n\n'+description+'\n\n'+url,
  'linkedin':common+'\n\nView this sculpture: '+url+'\n\n#Boldstone #SallyPrice #Sculpture #InteriorDesign',
  'google_business_profile':common+'\n\nExplore this sculpture using the Buy button.'}
 captions['instagram']=captions['facebook']
 assert len(captions['threads'])<=500 and len(captions['instagram'])<2200 and len(captions['google_business_profile'])<1500
 base={'post_key':pid,'catalogue_id':pid,'sku':row['sku'],'title':row['title'],'media_path':str(path.resolve()),'sha256':sha,'alt_text':alt}
 publishing.append({**base,'targets':{'sally_linkedin':{'caption':captions['linkedin'],'purchase_url':url},'boldstone_google_business_profile':{'caption':captions['google_business_profile'],'purchase_url':url,'button_label':'Buy'}}})
 tag={'name':row['title'],'price_text':'£'+format(row['price_gbp'],'.2f')}
 drafts.append({**base,'targets':{'boldstone_facebook':{'caption':captions['facebook'],'purchase_url':url,'product_tag':tag},'boldstone_threads':{'caption':captions['threads'],'purchase_url':url}}})
 posts.append({**base,'media_sha256':sha,'price_gbp':row['price_gbp'],'website_url':url,'commerce_variant_id':row['commerce_variant_id'],'dimensions':dimensions,'captions':captions,'opening':opening,'description':description,'original_media_path':row['original_media_path'],'original_sha256':row['original_sha256']})
for filename,batch,authorized,content in [('publish-manifest.json','component-sculptures-20261127',True,publishing),('combined-draft-manifest.json','component-sculptures-combined-drafts-20261127',False,drafts)]:
 manifest={'schema_version':1,'batch_id':batch,'publish_authorized':authorized,'posts':content};path=OUT/filename
 if path.exists():assert json.loads(path.read_text())==manifest
 else:atomic_json(path,manifest)
 assert len((settings if authorized else Settings(OUT/'draft-config/profiles.json')).jobs(path,require_authorized=authorized))==10
atomic_json(OUT/'posts.json',{'batch_id':'component-sculptures-20261127','posts':posts})
atomic_json(OUT/'website-verification.json',verified)
atomic_json(OUT/'authorization.json',{'utc':utc(),'instruction':'Can you post to Google Posts/LinkedIn and set up posts for threads/facebook and Instagram.','background_instruction':'All browser work remains in background tabs and must not steal user focus.','batch':'Next five sculptures; exclude all recorded prior publications and prepared batches.','authorized_publication_profiles':['sally_linkedin','boldstone_google_business_profile'],'other_platforms_prepare_only':True})
print(json.dumps({'sculptures':len(posts),'publish_targets':10,'draft_composers':10,'threads_lengths':[len(p['captions']['threads']) for p in posts]},ensure_ascii=False))
