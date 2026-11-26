"""Freeze five original-photo posts and authorize only Google and LinkedIn."""
from pathlib import Path
import json,sys,sqlite3,hashlib
from bs4 import BeautifulSoup
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
from settings import Settings
COPY={
 'BSI-8957C5C51828':('Botanical detail, held within a generous curve.',
  'Rounded grapes and a finely detailed vine leaf sit between sweeping curved edges in Gleneagles Vine IV. The square relief brings small botanical forms together with a broad, quiet expanse of pale surface.',
  'Square pale Gleneagles Vine IV relief with a cluster of raised grapes, a vine leaf near the top and sweeping curved edges.'),
 'BSI-3BFB1137D230':('Circular relief at the heart of a garden water feature.',
  'A circular relief and central opening give the square Knightsbridge fountain block its focus. This photograph shows the pale sculptural block within a round pool, with water and planting framing its simple geometry.',
  'Square pale Knightsbridge fountain block with a circular relief and central opening, photographed within a round pool in a planted garden.'),
 'BSI-791ADD96D660':('A broad curve gathering into a small spiral.',
  'A sweeping crescent curls into a small spiral across the tall, textured surface of Lava Moon II. The contrast between the open upper panel and the curved relief gives the composition room to unfold.',
  'Tall pale Lava Moon II relief panel with a sweeping curved ridge curling into a small spiral across a lightly textured surface.'),
 'BSI-27B50C52ED10':('A compact study in curved relief.',
  'A rounded central form sits within a sweeping crescent on the square Crater Moon I panel. Its raised surfaces and curved recesses give a small sculpture a strong play of light and shadow.',
  'Square pale Crater Moon I relief with a rounded central form and a broad curved crescent around its edge.'),
 'BSI-65A93033A200':('A spiral contained by a square frame.',
  'A broad spiral gathers within the square border of Lunar Phase I. The curved centre and straight outer frame create a balanced relief, with a pale textured surface that catches changing light.',
  'Square pale Lunar Phase I relief with a broad inward-curling spiral enclosed by a raised rectangular border.')}
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
 unit='One individual fountain block by Boldstone, designed by Sally Price. The pool and surrounding installation are shown for context.' if pid=='BSI-3BFB1137D230' else 'One individual sculpture by Boldstone, designed by Sally Price. Companion pieces are sold separately.'
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
for filename,batch,authorized,content in [('publish-manifest.json','component-sculptures-20261126-2',True,publishing),('combined-draft-manifest.json','component-sculptures-combined-drafts-20261126-2',False,drafts)]:
 manifest={'schema_version':1,'batch_id':batch,'publish_authorized':authorized,'posts':content};path=OUT/filename
 if path.exists():assert json.loads(path.read_text())==manifest
 else:atomic_json(path,manifest)
 assert len((settings if authorized else Settings(OUT/'draft-config/profiles.json')).jobs(path,require_authorized=authorized))==10
atomic_json(OUT/'posts.json',{'batch_id':'component-sculptures-20261126-2','posts':posts})
atomic_json(OUT/'website-verification.json',verified)
atomic_json(OUT/'authorization.json',{'utc':utc(),'instruction':'Can you post to Google Posts/LinkedIn and set up posts for threads/facebook and Instagram. Can you find 5 other platforms to post static content that would be relevant to Boldstone.','background_instruction':'All browser work remains in background tabs and must not steal user focus.','batch':'Next five sculptures; exclude all recorded prior publications and prepared batches.','authorized_publication_profiles':['sally_linkedin','boldstone_google_business_profile'],'other_platforms_prepare_only':True,'additional_platforms_research_only':True})
print(json.dumps({'sculptures':len(posts),'publish_targets':10,'draft_composers':10,'threads_lengths':[len(p['captions']['threads']) for p in posts]},ensure_ascii=False))
