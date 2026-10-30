"""Read one current photo task and its Master reference; performs no writes."""
import argparse,json
from pathlib import Path
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--option',default='BSI-3635E3DC3434');p.add_argument('--list',action='store_true');args=p.parse_args()
g=json.loads((H/'canonical-master-register.json').read_text());a=json.loads((H/'image-coverage-current.json').read_text());opts={x['product_id']:x for x in g['options']if x.get('counted_as_individual_option',True)}
state=json.loads((H/'guided-owner-review-state.json').read_text());held=set(state.get('held_in_situ_ids',[]));held.update(x['option_id']for x in state.get('owner_held_context_reviews',[])if x.get('role')=='In situ');deferred=set(state.get('deferred_individual_ids',[]));held_series=set(state.get('held_series_ids',[]))
for task in a['missing_pictures']:
 if task['role']=='In situ'and task['option_id']in held or task['role']=='Individual'and task['option_id']in deferred or task['role']=='Series'and task['option_id']in held_series:continue
 if task['status']!='Open'or not args.list and task['option_id']!=args.option:continue
 o=opts[task['option_id']];r=task['reference'];current={k:o.get(k)for k in ['image_url','folder_url','file_id','folder_id']}if o.get('file_id')else r
 result={'name':o['name'],'option_id':o['product_id'],'role':task['role'],'action':task['action'],'qualification':task['qualification'],'image':current.get('image_url'),'folder':current.get('folder_url'),'file_id':current.get('file_id'),'folder_id':current.get('folder_id'),'example_scope':'Current canonical individual identification reference; no context or series role is inferred.'}
 if r.get('file_id')!=current.get('file_id'):result['retained_task_source_reference']=r;result['qualification_scope']='Retained source finding; example navigation uses the current canonical primary.'
 print(json.dumps(result,ensure_ascii=False))
