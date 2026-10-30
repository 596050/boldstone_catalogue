import collections,csv,hashlib,json
from pathlib import Path
from urllib.parse import quote
from datetime import datetime,timezone
P=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
root=read(P/'fresh-wall-root-metadata.json')['folder'];scope='ns:202238505//BOLDSTONE MASTER/Products/01 Wall Sculptures'
inventory=read(P/'fresh-complete-native-inventory.json');entries=[e for page in inventory['pages'] for e in page['entries']]
assert inventory['pagination_complete'] and not inventory['pages'][-1]['has_more'] and len(entries)==6801
folders={e['path'].casefold():e for e in entries if e['object_type']=='folder'}
assert len(folders)==441 and root['path_display']=='/BOLDSTONE MASTER/Products/01 Wall Sculptures'
display_cache={scope.casefold():root['path_display']}
def display(path):
 key=path.casefold()
 if key in display_cache:return display_cache[key]
 e=folders[key];value=display(path.rsplit('/',1)[0])+'/'+e['name'];display_cache[key]=value;return value
def home(path):return 'https://www.dropbox.com/home'+quote(path,safe='/')
objects={root['id']:{'file_id':root['id'],'object_type':'folder','name':root['name'],'path':scope,'display_path':root['path_display'],'folder_url':home(root['path_display']),'parent_id':None,'source':'fresh scoped root metadata'}}
rows=[]
for e in entries:
 parent=e['path'].rsplit('/',1)[0]
 parent_id=root['id'] if parent.casefold()==scope.casefold() else folders[parent.casefold()]['file_id']
 actual_display=display(e['path']) if e['object_type']=='folder' else display(parent)+'/'+e['name']
 parts=actual_display[len(root['path_display'])+1:].split('/')
 obj={'file_id':e['file_id'],'object_type':e['object_type'],'name':e['name'],'path':e['path'],'display_path':actual_display,'parent_id':parent_id,'family':parts[0],'client_modified':e.get('client_modified'),'modified_time':e.get('modified_time')}
 if e['object_type']=='file':
  obj.update(size=e['file']['size'],folder_id=parent_id,folder_path=display(parent),folder_url=home(display(parent)),image_url=home(display(parent))+'?preview='+quote(e['name'],safe=''),native_metadata_verified_utc=inventory['completed_utc'])
  rows.append(obj)
 else:obj['folder_url']=home(actual_display)
 assert e['file_id'] not in objects;objects[e['file_id']]=obj
assert len(rows)==6360 and len(objects)==6802 and all(r['folder_id'] in objects for r in rows)
write('complete-current-native-object-map.json',objects)
write('all-current-6360-image-folder-links.json',rows)
with (P/'all-current-6360-image-folder-links.tsv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['family','file_id','name','folder_id','folder_path','folder_url','image_url','size'],delimiter='\t',extrasaction='ignore');w.writeheader();w.writerows(rows)
base=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue');pointer=read(base/'current-master.json');reg=read(base/pointer['register']);selected=[];missing=[]
inactive=[];sentinels=[]
for o in reg['options']:
 if o.get('active_catalogue_option') is False:
  inactive.append({'product_id':o['product_id'],'name':o['name'],'catalogue_status':o.get('catalogue_status')});continue
 for prefix in ['', 'context_']:
  fid=o.get(prefix+'file_id')
  if not fid:continue
  if not fid.startswith('id:'):
   sentinels.append({'product_id':o['product_id'],'role':prefix or 'primary','value':fid});continue
  item={'product_id':o['product_id'],'option_name':o['name'],'role':prefix or 'primary','file_id':fid,'recorded_folder_id':o.get(prefix+'folder_id')}
  if fid in objects and objects[fid]['object_type']=='file':
   r=objects[fid];item.update(current_actual_folder_id=r['folder_id'],current_folder_url=r['folder_url'],current_image_url=r['image_url'],same_recorded_parent=item['recorded_folder_id']==r['folder_id']);selected.append(item)
  else:missing.append(item)
write('selected-option-native-reference-readback.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'register_path':pointer['register'],'register_sha256':pointer['register_sha256'],'active_options_checked':sum(o.get('active_catalogue_option') is not False for o in reg['options']),'retired_options_excluded_from_current_scope':inactive,'non_native_sentinel_values_not_treated_as_file_IDs':sentinels,'verified_current_occurrences':selected,'not_present_in_current_scoped_inventory':missing,'no_missing_reference_restored_or_replaced':True,'canonical_writes':0})
prior=read(Path('/Users/tprice/Documents/boldstone/reports/dropbox-wall-only-deco-dune-ripple-review-20261024T204816Z/combined-thirty-eight-family-current-image-folder-links.json'));deltas=[]
for r in prior:
 if r['file_id'] not in objects:continue
 now=objects[r['file_id']]
 if r['folder_id']!=now['folder_id'] or r['folder_url']!=now['folder_url'] or r['image_url']!=now['image_url']:
  deltas.append({'file_id':r['file_id'],'previous':{k:r[k] for k in ['family','folder_id','folder_url','image_url']},'current':{k:now[k] for k in ['family','folder_id','folder_url','image_url']},'actual_parent_changed':r['folder_id']!=now['folder_id']})
write('prior38-current-link-differences.json',deltas)
summary={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'COMPLETE_CURRENT_NATIVE_LINK_INVENTORY','current_images':6360,'current_folders':441,'family_roots':60,'current_objects_including_root':6802,'current_parent_links_verified':len(entries),'selected_primary_and_context_occurrences_current':len(selected),'selected_occurrences_not_in_current_scope':missing,'selected_parent_disagreements':[x for x in selected if not x['same_recorded_parent']],'prior38_link_differences':len(deltas),'prior38_actual_parent_differences':sum(d['actual_parent_changed'] for d in deltas),'scope':root['path_display'],'native_writes':0,'canonical_writes':0,'visual_roles_and_product_associations_not_inferred_from_paths':True}
write('current-link-inventory-validation.json',summary);print(json.dumps(summary,indent=2))
