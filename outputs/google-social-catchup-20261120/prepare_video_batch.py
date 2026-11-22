"""Freeze the Google video workflow, exact account configuration and reviewed clips."""
import copy,json,sys
from pathlib import Path
from urllib.parse import urlencode
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,utc
from settings import Settings
plan=json.loads((OUT/'google-video-delivery-plan.json').read_text())
config=OUT/'video-config';(config/'workflows').mkdir(parents=True,exist_ok=True)
settings=Settings();base=settings.data
profile=copy.deepcopy(base['profiles']['boldstone_google_business_profile']);recipe=copy.deepcopy(settings.workflow(profile))
video={'locator':[{'selector':'main div[data-file-id] video'}],'video':True,'duration':'$video_duration','width':'$video_width','height':'$video_height'}
recipe['description']='Google Update with one loaded, duration-checked native MP4 and exact action destination.'
recipe['google_video']=video;recipe.pop('google_photo')
recipe['clean_state']['preview']=[{'selector':'main:has(textarea[maxlength="1500"]) div[data-file-id]'}]
for step in recipe['prepare']:
 if step['op']=='upload':step['preview']=video
recipe['ready']=[dict(video,purpose='video') if g['purpose']=='photo' else g for g in recipe['ready']]
profile['workflow']='workflows/google_business_profile_video.json'
atomic_json(config/profile['workflow'],recipe)
atomic_json(config/'profiles.json',{'schema_version':1,'policy':base['policy'],'profiles':{'boldstone_google_business_profile':profile}})
video_settings=Settings(config/'profiles.json');folder=OUT/'history-video-part1';folder.mkdir(exist_ok=True)
assert not (folder/'manifest.json').exists(),'Resume frozen video manifest'
descriptions={
 'DdL9Jx_ApkK':('Project Apollo','Project Apollo: a figurative sculpture study from the Boldstone archive.'),
 'Df2FuDyA9kQ':('Boldstone Sculpture film','An archive film introducing Boldstone sculptures for interiors and exteriors, including bespoke designs and custom finishes.'),
 'CHteknEh9xT':('Cut gold','Cut gold: a studio film exploring light and shadow on a gold-finished sculptural surface.'),
 'DKP1fsCOyux':('Icarus commission','Icarus, a commissioned wall sculpture for an interior garden entertainment area in Kensington. Lighting behind the sculptural panels reveals their relief and surface detail.'),
 'CZnFSE4I0nw':('Rusted texture experiments','A studio film of experiments with rusted surface textures, evoking desert landscapes and cloud formations.'),
}
order={'DdL9Jx_ApkK':0,'Df2FuDyA9kQ':1,'CHteknEh9xT':2,'DKP1fsCOyux':3,'CZnFSE4I0nw':4}
posts=[];prepared=[]
for row in sorted(plan['clips'],key=lambda r:(order[r['shortcode']],r['part_number'])):
 code=row['shortcode'];title,description=descriptions[code];parts=row['part_count'];part=row['part_number']
 if parts>1:
  title+=' — part '+str(part)+' of '+str(parts)
  description+='\n\nPart '+str(part)+' of '+str(parts)+'. The complete original film is shared as a sequence of clips for Google.'
 caption=description+'\n\nFrom the Boldstone sculpture archive. Use Learn more to explore sculptures and commissions on our website.'
 key='INSTAGRAM-ARCHIVE-VIDEO-'+code+'-part-'+str(part)
 url='https://boldstonesculpture.com/?'+urlencode({'utm_source':'google_business_profile','utm_medium':'social','utm_campaign':'sculpture_archive_catchup_20261120','utm_content':code+'-'+str(part)})
 stream=next(s for s in row['delivery_metadata']['streams'] if s['codec_type']=='video')
 post={'post_key':key,'title':title,'alt_text':title,'media_path':row['delivery_media_path'],'sha256':row['delivery_sha256'],'video':{'duration':row['delivery_duration'],'width':stream['width'],'height':stream['height']},'targets':{'boldstone_google_business_profile':{'caption':caption,'purchase_url':url,'button_label':'Learn more'}}}
 posts.append(post)
 prepared.append({**row,'media_path':row['delivery_media_path'],'sha256':row['delivery_sha256'],'google_post_key':key,'google_caption':caption,'google_url':url,'google_button':'Learn more','title':title,'media_kind':'video'})
manifest={'schema_version':1,'batch_id':'google-social-catchup-20261120-history-video-part1','publish_authorized':True,'posts':posts}
atomic_json(folder/'prepared-posts.json',prepared);atomic_json(folder/'manifest.json',manifest)
jobs=video_settings.jobs(folder/'manifest.json');print(json.dumps({'posts':len(posts),'jobs':len(jobs),'config':str(config/'profiles.json')}))
