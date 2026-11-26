"""Freeze five checked sculptures; publish only Google/LinkedIn, prepare other channels."""
from pathlib import Path
import json,sys,sqlite3
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
from settings import Settings

COPY={
 'BSI-C3858B1FE67E':('A fossil spiral meets a sweeping curve.',
  'Raised shell ridges meet a broad, smooth crescent in Ammonite Grande II. The tall right-hand panel brings fossil-inspired detail into a simple rectangular form, with relief and shadow changing across its surface.',
  'Tall pale Ammonite Grande II right panel with raised shell ridges entering from the left and a broad smooth crescent.'),
 'BSI-BB6D7F02662A':('A palm traced in light and shadow.',
  'Long, slender bands rise and fan across Egyptian Fountain Palm. The botanical pattern stretches through a tall panel, giving light a series of curved edges to follow.',
  'Tall Egyptian Fountain Palm relief with slender raised bands fanning upwards, photographed against a pale wall in warm light.'),
 'BSI-49CB2EDD232C':('Grapes, leaves and one generous curve.',
  'A raised bunch of grapes and finely detailed leaves sit beside a broad curved division in Gleneagles Vine II. The square panel balances small botanical details with a simple sculptural sweep.',
  'Square pale Gleneagles Vine II relief with raised grapes on the left, vine leaves at the upper right and a broad curved division.'),
 'BSI-7357A558C9E8':('A circle unfolding at architectural scale.',
  'A broad circular arc enters from the side of Lava Moon I, crossing a lightly textured, tall rectangular surface. Its restrained geometry gives changing light and shadow room to shape the composition.',
  'Tall pale Lava Moon I panel with a lightly textured surface and a broad raised circular arc entering from the right.'),
 'BSI-B9E2B67965E2':('A shell spiral carried by a wave.',
  'A raised shell spiral sits between sweeping curved bands in Moon and Shell Wave I. Fine grooves and a textured pale surface add detail to the long, narrow relief.',
  'Tall narrow white Moon and Shell Wave I panel with a raised shell spiral, sweeping curved bands and fine flowing grooves.'),
}
settings=Settings();rows=json.loads((OUT/'selected-products.json').read_text());verified=json.loads((OUT/'website-verification.json').read_text())
assert len(rows)==5 and {p['catalogue_id'] for p in rows}==set(COPY)
db=sqlite3.connect((ROOT/'social-publisher/state/outbox.sqlite3').as_uri()+'?mode=ro',uri=True)
posts=[];publishing=[];drafts=[];design=[]
for row in rows:
 pid=row['catalogue_id'];assert row['photo']['primary_eligible'] and not row['photo']['withheld_reasons']
 assert not db.execute('select id from jobs where post_key=?',(pid,)).fetchone()
 assert not db.execute("select id from jobs where json_extract(payload,'$.caption') like ?",('%'+row['title']+'%',)).fetchone()
 path=Path(row['delivery_media_path']);sha=digest(path.read_bytes());assert sha==row['delivery_sha256'] and path.stat().st_size<5000000
 original=Path(row['original_media_path']);assert digest(original.read_bytes())==row['original_sha256']
 assert any(v['catalogue_id']==pid and v['status']==200 and v['price_gbp']==row['price_gbp'] for v in verified)
 opening,description,alt=COPY[pid];dimensions=row['fields']['Dimensions / depth'].split('; four-panel arrangement',1)[0]
 common=row['title']+'\n\n'+opening+'\n\n'+description+'\n\nDimensions: '+dimensions+'.\nMade from a gypsum-based material.\nOne individual sculpture by Boldstone, designed by Sally Price. Companion pieces are sold separately.'
 url=row['website_url'];captions={
  'facebook':common+'\n\nExplore this sculpture through the product tag or visit: '+url+'\n\n#Boldstone #SallyPrice #WallSculpture #ReliefSculpture',
  'instagram':common+'\n\nTap the product tag for this sculpture.\n\n#Boldstone #SallyPrice #WallSculpture #ReliefSculpture #InteriorDesign',
  'threads':row['title']+'\n\n'+opening+'\n\n'+description+'\n\n'+url,
  'linkedin':common+'\n\nView this sculpture: '+url+'\n\n#Boldstone #SallyPrice #WallSculpture #ReliefSculpture #InteriorDesign',
  'google_business_profile':common+'\n\nExplore this sculpture using the Buy button.',
 }
 assert len(captions['threads'])<=500 and len(captions['instagram'])<2200 and len(captions['google_business_profile'])<1500
 base={'post_key':pid,'catalogue_id':pid,'sku':row['sku'],'title':row['title'],'media_path':str(path.resolve()),'sha256':sha,'alt_text':alt}
 publishing.append({**base,'targets':{'sally_linkedin':{'caption':captions['linkedin'],'purchase_url':url},'boldstone_google_business_profile':{'caption':captions['google_business_profile'],'purchase_url':url,'button_label':'Buy'}}})
 tag={'name':row['title'],'price_text':'£'+format(row['price_gbp'],'.2f')}
 drafts.append({**base,'targets':{'boldstone_facebook':{'caption':captions['facebook'],'purchase_url':url,'product_tag':tag},'boldstone_instagram':{'caption':captions['instagram'],'product_tag':tag},'boldstone_threads':{'caption':captions['threads'],'purchase_url':url}}})
 posts.append({**base,'media_sha256':sha,'price_gbp':row['price_gbp'],'website_url':url,'commerce_variant_id':row['commerce_variant_id'],'dimensions':dimensions,'captions':captions,'opening':opening,'description':description,'original_media_path':str(original),'original_sha256':row['original_sha256']})
 for platform in ['Archiproducts','Architonic','Archilovers']:
  body=description+'\n\nDimensions: '+dimensions+'.\nMaterial: '+row['fields']['Material / finish']+'.\nOne individual sculpture or panel; companion pieces are sold separately.\nDesigned by Sally Price for Boldstone.\n\nProduct details: '+url
  design.append({'platform':platform,'status':'CONTENT_PREPARED_NATIVE_ACCESS_TO_BE_CHECKED','catalogue_id':pid,'title':row['title'],'description':body,'short_caption':opening+' '+description,'price_gbp':row['price_gbp'],'dimensions':dimensions,'material_finish':row['fields']['Material / finish'],'sku':row['sku'],'media_path':str(path.resolve()),'original_media_path':str(original),'media_sha256':sha,'alt_text':alt,'product_url':url,'publish_authorized':False})
for filename,batch,authorized,content in [('publish-manifest.json','component-sculptures-20261126',True,publishing),('draft-manifest.json','component-sculptures-drafts-20261126',False,drafts)]:
 manifest={'schema_version':1,'batch_id':batch,'publish_authorized':authorized,'posts':content};path=OUT/filename
 if path.exists():assert json.loads(path.read_text())==manifest
 else:atomic_json(path,manifest)
 jobs=settings.jobs(path,require_authorized=authorized);assert len(jobs)==(10 if authorized else 15)
atomic_json(OUT/'posts.json',{'batch_id':'component-sculptures-20261126','posts':posts})
atomic_json(OUT/'design-platform-drafts.json',{'checked_utc':utc(),'publish_authorized':False,'drafts':design})
atomic_json(OUT/'authorization.json',{'utc':utc(),'instruction':'Can you post to Google Posts/LinkedIn and set up posts for threads/facebook and Instagram. Can you reopen Archiproducts, Architonic and Archilovers and prepare posts for each?','background_instruction':'Make sure all of this is done in the background and does not steal focus from the user.','assumption':'Next five sculptures, excluding prior batches and matching prior captions; optional clarification remained unanswered.','authorized_publication_profiles':['sally_linkedin','boldstone_google_business_profile'],'other_platforms_prepare_only':True})
print(json.dumps({'sculptures':len(posts),'new_publications':10,'native_social_draft_targets':15,'design_platform_content_drafts':15,'titles':[r['title'] for r in posts],'threads_lengths':[len(r['captions']['threads']) for r in posts]},ensure_ascii=False))
