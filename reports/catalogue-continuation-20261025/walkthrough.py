"""Display each current work item with image and containing-folder links."""
from pathlib import Path
import argparse
import hashlib
import json
H=Path(__file__).resolve().parent
arg=argparse.ArgumentParser();arg.add_argument('--item',type=int,default=3);a=arg.parse_args()
p=json.loads((H/'progress.json').read_text())
b=H.parents[1]/'sculpture-catalogue'
current=json.loads((b/'current-master.json').read_text())
assert current['register_sha256']==p['register_sha256'],'Catalogue data changed; refresh this review before proceeding.'
assert hashlib.sha256((b/current['register']).read_bytes()).hexdigest()==p['register_sha256']
assert 1<=a.item<=len(p['items'])
x=p['items'][a.item-1]
print('ITEM '+str(x['number'])+': '+x['title']+'\n'+x['status']+'\n'+x['detail'])
for r in x['references']:
 print('\n'+r['name']+' / '+r['product_id'])
 print('Image: '+r['image_url']+'\nContaining folder: '+r['folder_url'])
 print('Stable file ID: '+r['file_id']+'\nActual folder ID: '+r['folder_id'])
if x.get('source_image'):print('Retained Squarespace source image: '+x['source_image'])
if x.get('question'):print('Pending question: '+x['question'])
for k,v in x.get('working_details',{}).items():print(k+': '+v)
if x.get('review'):print('Review: '+x['review'])
print('\nNo canonical, local app review, Dropbox or platform change by this walkthrough.')
