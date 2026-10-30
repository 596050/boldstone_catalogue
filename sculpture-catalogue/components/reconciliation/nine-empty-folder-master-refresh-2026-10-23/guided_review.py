"""Read one current photo task and its Master reference; performs no writes."""
import argparse,json
from pathlib import Path
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--option',default='BSI-3635E3DC3434');p.add_argument('--list',action='store_true');args=p.parse_args()
g=json.loads((H/'canonical-master-register.json').read_text());a=json.loads((H/'image-coverage-current.json').read_text());opts={x['product_id']:x for x in g['options']if x.get('counted_as_individual_option',True)}
for task in a['missing_pictures']:
 if task['status']!='Open'or not args.list and task['option_id']!=args.option:continue
 o=opts[task['option_id']];r=task['reference'];print(json.dumps({'name':o['name'],'option_id':o['product_id'],'role':task['role'],'action':task['action'],'qualification':task['qualification'],'image':r.get('image_url')or o.get('image_url'),'folder':r.get('current_family_navigation_url')or r.get('folder_url')or o.get('folder_url'),'file_id':r.get('file_id'),'folder_id':r.get('folder_id')},ensure_ascii=False))
