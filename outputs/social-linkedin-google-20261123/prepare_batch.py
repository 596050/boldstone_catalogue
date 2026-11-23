"""Freeze this authorized LinkedIn/Google batch from the five reviewed sculptures."""
import json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from common import atomic_json,digest
source=json.loads((ROOT/'outputs/social-drafts-20261123/posts.json').read_text())
settings=Settings();records=[];delivery=[];media=[]
for p in source['posts']:
 original=Path(p['media_path']);assert digest(original.read_bytes())==p['sha256']
 path=OUT/(p['catalogue_id']+'.jpg') if p['catalogue_id']=='BSI-DDD53E46FB3F' else original
 sha=digest(path.read_bytes());assert path.stat().st_size<=settings.policy['max_media_bytes']
 if p['catalogue_id']=='BSI-DDD53E46FB3F':assert path.stat().st_size<=5000000
 body=p['captions']['instagram'].split('\n\nView this sculpture:',1)[0]
 if p['catalogue_id']=='BSI-923D5E50A898':body+='\n\nShown under coloured light; the offered finish is White.'
 linkedin=body+'\n\nView this sculpture: '+p['website_url']+'\n\n#Boldstone #SallyPrice #WallSculpture #ReliefSculpture #InteriorDesign'
 google=body+'\n\nExplore this sculpture using the Buy button.'
 captions={'linkedin':linkedin,'google_business_profile':google}
 targets={'sally_linkedin':{'caption':linkedin,'purchase_url':p['website_url']}}
 if p['catalogue_id']!='BSI-923D5E50A898':targets['boldstone_google_business_profile']={'caption':google,'button_label':'Buy','purchase_url':p['website_url']}
 row={k:p[k] for k in ['post_key','catalogue_id','sku','title','alt_text']};row.update(media_path=str(path.resolve()),sha256=sha,targets=targets)
 records.append(row);delivery.append({**p,'media_path':str(path.resolve()),'sha256':sha,'captions':captions})
 media.append({'post_key':p['post_key'],'original_path':str(original),'original_sha256':p['sha256'],'delivery_path':str(path.resolve()),'delivery_sha256':sha,'delivery_bytes':path.stat().st_size,'conversion':'JPEG quality 90, original dimensions retained with macOS sips' if path!=original else 'Original bytes unchanged'})
manifest={'schema_version':1,'batch_id':'component-sculptures-linkedin-google-20261123','publish_authorized':True,'posts':records}
path=OUT/'manifest.json'
if path.exists():assert json.loads(path.read_text())==manifest,'Frozen manifest differs; inspect before proceeding'
else:atomic_json(path,manifest)
jobs=settings.jobs(path);assert len(jobs)==9
atomic_json(OUT/'posts.json',delivery);atomic_json(OUT/'media-delivery-receipts.json',media)
atomic_json(OUT/'authorization.json',{'utc':datetime.now(timezone.utc).isoformat(),'instruction':'Post to these two now: LinkedIn — Sally Price’s account. Google Business Profile / Google Posts — Boldstone’s business profile.','source_batch':source['batch_id'],'profiles':['sally_linkedin','boldstone_google_business_profile'],'expected_new_publications':9,'existing_google_post_to_verify':'7043713459646511209'})
print(json.dumps({'manifest':str(path),'sculptures':len(records),'new_deliveries':len(jobs),'platform_counts':{'linkedin':5,'google_business_profile':4},'media':[{'post_key':r['post_key'],'bytes':r['delivery_bytes'],'conversion':r['conversion']} for r in media]},ensure_ascii=False))
