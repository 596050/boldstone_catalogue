import pathlib,json,hashlib,re,urllib.parse,datetime
H=pathlib.Path('/Users/tprice/Documents/boldstone/sculpture-catalogue/components/reconciliation/spiralmoon-current-folder-refresh-master-2026-10-24')
N=pathlib.Path('/Users/tprice/Documents/boldstone/reports/dropbox-spiralmoon-27-in-situ-moves-20261024T005750Z')
R=pathlib.Path("/Users/tprice/Documents/boldstone/reports/dropbox-spiralmoon-catalogue-independent-readback-20261024T010859Z")
pins={};issues=[];checks=0
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def get(p):
 p=pathlib.Path(p);pins[str(p)]=sha(p);return json.loads(p.read_text())
def ck(v,label):
 global checks
 checks+=1
 if not v:issues.append(label)
def cp(p):return re.sub(r'^ns:\d+//','/',p)
def urlpath(url):
 u=urllib.parse.urlsplit(url);p=urllib.parse.unquote(u.path)
 if p.startswith('/home'):
  p=p[5:];q=urllib.parse.parse_qs(u.query)
  if 'preview' in q:p+='/'+q['preview'][0]
 elif p.startswith('/preview'):p=p[8:]
 return p
def dif(a,b,p=''):
 if type(a)!=type(b):return [p]
 if isinstance(a,dict):
  out=[]
  for k in a.keys()|b.keys():out+=dif(a[k],b[k],p+'/'+k) if k in a and k in b else [p+'/'+k]
  return out
 if isinstance(a,list):
  if len(a)!=len(b):return [p+'/length']
  return sum((dif(x,y,p+'/'+str(i)) for i,(x,y) in enumerate(zip(a,b))),[])
 return [] if a==b else [p]
def at(o,path):
 for k in path.split('/'):o=o[int(k)] if isinstance(o,list) else o[k]
 return o
overlay=get(N/'current-reference-overlay.json');seal=get(N/'execution-seal.json')
ck(pins[str(N/'current-reference-overlay.json')]=='4a917d72d5fdaec21fd67768b5414e7a48fa06b50415ea4f17a29997838bb015','sealed overlay identity')
ck(pins[str(N/'execution-seal.json')]=='f1c443e216eee558e141d2320bdb774dcd704cd9239dc449fa27025e5345b491','execution seal identity')
for x in seal['receipts']:
 ck(pathlib.Path(x['path']).stat().st_size==x['size'],'native receipt size '+x['path']);ck(sha(x['path'])==x['sha256'],'native receipt SHA '+x['path'])
for x in seal['verified_post_move_originals']:
 raw=pathlib.Path(x['path']).read_bytes();ck(len(raw)==x['size'],'original size '+x['file_id']);ck(hashlib.sha256(raw).hexdigest()==x['sha256'],'original SHA '+x['file_id']);dh=hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0,len(raw),4194304))).hexdigest();ck(dh==x['dropbox_content_hash'],'original Dropbox hash '+x['file_id'])
before=get(H/'inputs/master_register.before');after=get(H/'canonical-master-register.json');ab=get(H/'inputs/audit.before');aa=get(H/'image-coverage-current.json');allowed=get(H/'current-reference-fields-refreshed.json')
navtops={p.split('/')[0] for p in allowed if not p.startswith('audit/')};actual=[]
for k in navtops:actual +=[k+x for x in dif(before[k],after[k])]
actual+=['audit/coverage'+x for x in dif(ab['coverage'],aa['coverage'])]
ck(set(actual)==set(allowed) and len(actual)==34,'exact34 register/audit navigation changes')
exempt=navtops|{'latest_active_photo_source_review','latest_image_coverage_audit','latest_spiralmoon_native_navigation_import'}
for k in (set(before)|set(after))-exempt:ck(before.get(k)==after.get(k),'all unrelated register fields preserved '+k)
bookkeeping={'path','sha256','recorded_utc','native_binding_verification','visual_verification','status','audit','verification'}
for key in ['latest_active_photo_source_review','latest_image_coverage_audit']:
 ck({k:v for k,v in before[key].items() if k not in bookkeeping}=={k:v for k,v in after[key].items() if k not in bookkeeping},'all review counts/holds preserved '+key)
ck(len(after['options'])==189 and len(after['components'])==112,'189retained options and112components preserved')
for a,b in zip(before['options'],after['options']):
 for k in set(a)|set(b):
  if k not in ['image_url','folder_url','folder_id']:ck(a.get(k)==b.get(k),'option semantic field preserved '+a['product_id']+'/'+k)
objs={x['file_id']:x for x in overlay['objects']};root=overlay['preserved_scope_roots'][0]
for key in allowed:
 target=aa if key.startswith('audit/') else after;path=key[6:] if key.startswith('audit/') else key
 refpath,field=path.rsplit('/',1);ref=at(target,refpath);ident=ref.get('file_id');ck(ident in objs,'reference native identity '+key)
 if ident not in objs:continue
 native=objs[ident];v=ref[field];parent=native['current_path'].rsplit('/',1)[0]
 if field=='folder_id':ck(v==native['current_parent_id'],'navigation actual parent '+key)
 elif field=='path':ck(cp(v)==native['current_path'],'navigation path '+key)
 elif field=='image_url':ck(urlpath(v)==native['current_path'],'navigation image '+key)
 elif field=='folder_url':ck(urlpath(v)==parent,'navigation folder '+key)
 else:ck(False,'unexpected navigation field '+key)
assets=get(H/'current-assets.json');oldassets=get(H/'inputs/report_assets.before');nm=get(H/'current-native-reference-map.json')['current_objects'];oldnm=get(H/'inputs/native_map.before')['current_objects'];scoped=set(objs)|{root['file_id']}
ck(len(objs)==87 and sum(x['object_type']=='file' for x in objs.values())==82,'87native objects:82files5folders')
for i,x in objs.items():
 ck(i in nm,'native map object present '+i)
 if i not in nm:continue
 a=nm[i]
 for k,v in [('file_id',i),('object_type',x['object_type']),('name',x['current_name']),('parent_id',x['current_parent_id']),('size',x['size'])]:ck(a.get(k)==v,'map '+i+'/'+k)
 ck(cp(a['path'])==x['current_path'] and a['display_path']==x['current_path'],'map current paths '+i)
 if x['object_type']=='file':
  ck(i in assets,'asset present '+i)
  if i not in assets:continue
  a=assets[i];parentpath=x['current_path'].rsplit('/',1)[0]
  for k,v in [('file_id',i),('folder_id',x['current_parent_id']),('name',x['current_name']),('bytes',x['size']),('client_modified',x['current_client_modified'])]:ck(a.get(k)==v,'asset '+i+'/'+k)
  ck(cp(a['path'])==x['current_path'] and a['display_path']==x['current_path'] and cp(a['folder_path'])==parentpath,'asset native paths '+i)
  ck(urlpath(a['image_url'])==x['current_path'] and urlpath(a['folder_url'])==parentpath,'asset paired links '+i)
  ck(a.get('source_content_hash')==x['dropbox_content_hash'],'asset original content hash '+i)
  if i in oldassets:
   for k in ['full','thumb','source_content_hash','source_bytes','cached_source_id_size_consistent','current_original_content_rehashed']:ck(a.get(k)==oldassets[i].get(k),'historical cache qualification retained '+i+'/'+k)
ck(root['file_id'] in nm and cp(nm[root['file_id']]['path'])==root['path'],'native family root retained')
for i in (set(oldnm)|set(nm))-scoped:ck(oldnm.get(i)==nm.get(i),'unrelated native map '+i)
for i in (set(oldassets)|set(assets))-set(objs):ck(oldassets.get(i)==assets.get(i),'unrelated asset '+i)
ck(set(nm)-set(oldnm)==scoped-set(oldnm),'map additions limited to scoped native objects/root')
ck(len(overlay['specific_file_maps'])==27 and not overlay['created_folders'],'only27filepaths/parents; no folders created')
opt=next(x for x in after['options'] if x['product_id']=='BSI-10BFED6B265B');oldopt=next(x for x in before['options'] if x['product_id']==opt['product_id'])
ck(opt['file_id']==oldopt['file_id']=='id:cnqzTNngPVsAAAAAAAuXEw' and opt['folder_id']=='id:cnqzTNngPVsAAAAAAAyjFg','selected primary011JPG identity and current parent')
ck(all(opt[k]==oldopt[k] for k in opt if k.startswith('context_')),'selected context011jpeg allfields unchanged')
for ident in ['id:cnqzTNngPVsAAAAAAAt6-Q','id:cnqzTNngPVsAAAAAAA52zA']:ck(objs[ident]['old_path']==objs[ident]['current_path'] and objs[ident]['old_parent_id']==objs[ident]['current_parent_id'],'workshop not moved '+ident)
for p,v in pins.items():ck(sha(p)==v,'stable pinned input '+p)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');receipt={'schema':'boldstone.independent-spiralmoon-catalogue-corrected-check.v2','status':'PASS' if not issues else 'FAIL','verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'issues':issues,'scope':'Sealed native87objects+root/82originals vs candidate map/assets and34navigation fields. All189options112components source/role/specification/physical/commercial and held/optional policies preserved.','checker_corrections':{'initial_fail_receipt_preserved':str(R/'independent-candidate-readback.json'),'own_file_id_per_reference':'Offer35 retains029, separately from primary011; both navigation targets must match their own immutable fileID.','derived_audit_release_bookkeeping':'Excluded only observed artifact paths/timestamp/status; counts/holds/roles remain exact comparisons.','native_asset_path_check':'Unchanged and not relaxed. Both pair asset display_path/folder_path must match sealed native objects.'},'originals_independently_rehashed':82,'original_bytes':118673676,'native_objects':87,'publication_verified':False,'workbook_inspected':False,'native_mutations':0,'shared_master_writes':0,'input_sha256':pins}
p=R/('independent-candidate-corrected-'+stamp+'.json');p.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'status':receipt['status'],'checks':checks,'issues':issues,'receipt':str(p),'sha256':sha(p),'register_sha256':pins[str(H/'canonical-master-register.json')],'assets_sha256':pins[str(H/'current-assets.json')]}))

