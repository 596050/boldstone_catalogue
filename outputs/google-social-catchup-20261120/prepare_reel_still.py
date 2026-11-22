"""An explicit still-and-source-link adaptation for a reel with no downloadable public video."""
import json,sys
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest
from settings import Settings
r=json.loads((OUT/'legacy-photo-review-index.json').read_text())[26];assert r['shortcode']=='CtKq5zGIKCQ'
assert digest(Path(r['media_path']).read_bytes())==r['sha256']
assert digest(Path(r['evidence_path']).read_bytes())==r['evidence_sha256']
caption='Surface study — archive reel still\n\nA still from a Boldstone studio reel, showing copper-brown, rust and turquoise surface colours and textures.\n\nWatch the original reel on Instagram:\nhttps://www.instagram.com/reel/CtKq5zGIKCQ/\n\nFrom the Boldstone sculpture archive (2023). Use Learn more to explore sculptures and commissions on our website.'
url='https://boldstonesculpture.com/?utm_source=google_business_profile&utm_medium=social&utm_campaign=sculpture_archive_catchup_20261120&utm_content=CtKq5zGIKCQ'
key='INSTAGRAM-ARCHIVE-CtKq5zGIKCQ-still';title='Surface study — archive reel still'
folder=OUT/'history-reel-still';folder.mkdir(exist_ok=True);assert not (folder/'manifest.json').exists()
manifest={'schema_version':1,'batch_id':'google-social-catchup-20261120-history-reel-still','publish_authorized':True,'posts':[{'post_key':key,'title':title,'alt_text':title,'media_path':r['media_path'],'sha256':r['sha256'],'targets':{'boldstone_google_business_profile':{'caption':caption,'purchase_url':url,'button_label':'Learn more'}}}]}
prepared={**r,'google_post_key':key,'delivery_media_path':r['media_path'],'delivery_sha256':r['sha256'],'google_caption':caption,'google_url':url,'google_button':'Learn more','title':title,'adaptation':'Explicit archive reel still with original video permalink; public Instagram embed has Watch on Instagram instead of a video source'}
atomic_json(folder/'prepared-posts.json',[prepared]);atomic_json(folder/'manifest.json',manifest);print('Validated jobs',len(Settings().jobs(folder/'manifest.json')))
