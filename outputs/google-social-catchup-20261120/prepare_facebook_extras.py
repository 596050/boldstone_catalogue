"""Freeze the reviewed, previously unrepresented Facebook-only sculpture images."""
import json,sys
from pathlib import Path
from urllib.parse import urlencode
from PIL import Image
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from common import atomic_json,digest,utc
folder=OUT/'history-facebook-extra1';folder.mkdir(exist_ok=True);assert not (folder/'manifest.json').exists()
receipts={r['photo_id']:r for r in json.loads((OUT/'facebook-unmatched-photo-receipts.json').read_text())}
rows=[('968769045393133','Colour and texture — landscape studies','A Boldstone surface study in deep blues, greens and copper tones. The original Facebook post explores landscape, forests, waterfalls and rivers, and the branching patterns shared by plant growth and geological formations.','2025'),('406915868245123','Spirals in relief — five-panel wall sculpture','Five sculpted wall panels form a continuous rhythm of curves and spirals against a brick wall. Changing light reveals the depth and texture of the pale relief surfaces.','2021–2022')]
posts=[];prepared=[]
for photo_id,title,body,year in rows:
 r=receipts[photo_id];path=Path(r['media_path']);assert digest(path.read_bytes())==r['sha256'];assert digest(Path(r['evidence_path']).read_bytes())==r['evidence_sha256']
 w,h=Image.open(path).size;assert w>=400 and h>=300 and path.stat().st_size<=5_000_000
 key='FACEBOOK-ARCHIVE-'+photo_id;url='https://boldstonesculpture.com/?'+urlencode({'utm_source':'google_business_profile','utm_medium':'social','utm_campaign':'sculpture_archive_catchup_20261120','utm_content':photo_id})
 caption=title+'\n\n'+body+'\n\nFrom the Boldstone sculpture archive ('+year+'). Use Learn more to explore sculptures and commissions on our website.'
 sources=list(r['sources'])
 if photo_id=='406915868245123':sources+=receipts['103781881870689']['sources']
 posts.append({'post_key':key,'title':title,'alt_text':title,'media_path':str(path.resolve()),'sha256':r['sha256'],'targets':{'boldstone_google_business_profile':{'caption':caption,'purchase_url':url,'button_label':'Learn more'}}})
 prepared.append({**r,'source_key':digest(key),'sources':sources,'google_post_key':key,'google_caption':caption,'google_url':url,'google_button':'Learn more','title':title,'review_decision':{'decision':'INCLUDE_SCULPTURE','reason':'Native Boldstone-owned photograph and full source caption reviewed; not represented by an Instagram or 2026 source cover. Identical cover photograph from 2021 and 2022 shares one counterpart.'}})
atomic_json(folder/'prepared-posts.json',prepared);atomic_json(folder/'manifest.json',{'schema_version':1,'batch_id':'google-social-catchup-20261120-'+folder.name,'publish_authorized':True,'posts':posts})
print(len(Settings().jobs(folder/'manifest.json')))
