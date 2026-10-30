import json,hashlib,posixpath,collections
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def display(p):return '/'+p.split('//',1)[1]if p.startswith('ns:')else p
s=read(H/'scope.json');m=read(H/'input-manifest.json');objects={};oldpaths={};summaries=[];oldobjects={}
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
familymeta=read(H/'family-metadata-current.json')
for name,p in s['overlays'].items():
 o=read(p);live=read(H/'live'/f'{name}.json');assert not live['has_more'];entries=live['entries'];byid={x['file_id']:x for x in entries};root=familymeta[name]['folder'];rootid=root['id'];assert rootid==o['family']['file_id']
 folders={display(x['path']).casefold():x['file_id']for x in entries if x['object_type']=='folder'};folders[root['path_display'].casefold()]=rootid
 expected={x['file_id']:x for x in o['objects']};assert set(expected)-{rootid}==set(byid),(name,len(expected),len(byid))
 for fid,x in byid.items():
  e=expected[fid];assert x['name']==e['current_name']and display(x['path'])==display(e['current_path']),(name,fid)
  parent=folders[posixpath.dirname(display(x['path'])).casefold()];assert parent==e['current_parent_id'],fid
  if x['object_type']=='file':assert x.get('file',{}).get('size',0)==e['size'],fid
  objects[fid]={**x,'display_path':display(x['path']),'parent_id':parent}
  if e.get('old_path'):oldpaths[display(e['old_path']).casefold()]=fid
  oldpaths[display(e['current_path']).casefold()]=fid;oldobjects[fid]=e
 objects[rootid]={'file_id':rootid,'object_type':'folder','display_path':root['path_display'],'name':root['name'],'path_display':root['path_display']};oldpaths[root['path_display'].casefold()]=rootid
 summaries.append({'family':name,'native_objects_checked':len(entries)+1,'file_paths_changed':o['summary']['file_paths_changed'],'overlay_sha256':sha(p),'specific_file_overrides_verified':len(o.get('specific_file_maps',[]))})
before=read(H/'acanthus-native.json');after=read(H/'acanthus-native-after.json');assert not after['has_more'];assert len(after['entries'])==len(before['entries'])+3
bb={x['file_id']:x for x in before['entries']};ab={x['file_id']:x for x in after['entries']}
for fid,x in bb.items():assert ab[fid]==x,('unrelated Acanthus object changed',fid)
acroot=read(H/'acanthus-parent.json')['folder'];folders={display(x['path']).casefold():x['file_id']for x in after['entries']if x['object_type']=='folder'};folders[acroot['path_display'].casefold()]=acroot['id']
for fid,x in ab.items():objects[fid]={**x,'display_path':display(x['path']),'parent_id':folders[posixpath.dirname(display(x['path'])).casefold()]};oldpaths[display(x['path']).casefold()]=fid
objects[acroot['id']]={'file_id':acroot['id'],'object_type':'folder','display_path':acroot['path_display'],'name':acroot['name'],'path_display':acroot['path_display']};oldpaths[acroot['path_display'].casefold()]=acroot['id']
im=read(H/'image-and-parent-metadata-current.json');folders={x['folder']['path_display'].casefold():x['folder']['id']for x in im.values()if x['metadata_type']=='folder'}
for fid,d in im.items():
 x=d[d['metadata_type']];obj={'file_id':fid,'object_type':d['metadata_type'],'name':x['name'],'path_display':x['path_display'],'display_path':x['path_display'],'path':'ns:202238505/'+x['path_display']}
 if d['metadata_type']=='file':obj.update(file={'size':x.get('size',0)},parent_id=folders[posixpath.dirname(x['path_display']).casefold()],rev=x['rev'],client_modified=x.get('client_modified'))
 objects[fid]=obj;oldpaths[x['path_display'].casefold()]=fid
oldg=read(H/'inputs/master_register.before');olda=read(H/'inputs/audit.before')
def prior(z):
 if isinstance(z,list):
  for x in z:prior(x)
 elif isinstance(z,dict):
  fid=z.get('file_id');p=z.get('path')or z.get('path_display')
  if fid and p:oldpaths[display(p).casefold()]=fid
  for x in z.values():prior(x)
prior(oldg);prior(olda)
# Check approvals against the actual owner JSONL event, not only a lane summary.
checks=[];events=collections.defaultdict(list)
for name,p in s['approvals'].items():
 d=read(p);e=d.get('owner_instruction')or d.get('source_owner_event');assert e
 path=e.get('transcript_path',e.get('path'));expected=e.get('event_sha256',e.get('raw_sha256'));events[path].append((name,e,expected))
for p,rs in events.items():
 wanted={x[2]:x for x in rs};found={}
 with Path(p).open('rb')as f:
  for number,line in enumerate(f,1):
   candidates=[hashlib.sha256(line).hexdigest(),hashlib.sha256(line.rstrip(b'\r\n')).hexdigest()]
   for digest in candidates:
    if digest in wanted:
     name,e,_=wanted[digest];z=json.loads(line);payload=z['payload']
     if z['type']=='event_msg':assert payload['type']=='user_message';text=payload['message']
     else:assert z['type']=='response_item'and payload['role']=='user';text=''.join(c.get('text','')for c in payload['content'])
     assert text==e['text'];assert z['timestamp']==e.get('timestamp',z['timestamp']);found[digest]={'packet':name,'source_event_line':number,'event_sha256':digest,'owner_text_verified':True}
 assert set(found)==set(wanted),(p,list(set(wanted)-set(found)))
 checks.extend(found.values())
newparent=read(H/'restored-actual-parent-metadata.json')['folder'];assert newparent['id']=='id:cnqzTNngPVsAAAAAAA6Vng'
restores=[]
for name,fid in [('detail','id:cnqzTNngPVsAAAAAAAudqw'),('workshop','id:cnqzTNngPVsAAAAAAAuV6Q')]:
 r=read(H/f'acanthus-{name}-restore.json');x=r['file'];assert x['file_id']==fid;assert objects[fid]['parent_id']==newparent['id'];restores.append({'file_id':fid,'file_ID_preserved':True,'current_parent_id':newparent['id'],'historical_parent_id':'id:cnqzTNngPVsAAAAAAAyh4Q','current_path':x['path_display'],'current_rev':r['rev']})
write(H/'native-current-crosswalk.json',{'current_objects':objects,'old_path_to_id':oldpaths,'overlay_old_objects':oldobjects,'family_checks':summaries,'restored_sources':restores,'historical_Acanthus_parent_id':'id:cnqzTNngPVsAAAAAAAyh4Q','recreated_Acanthus_parent_id':newparent['id'],'file_restore_count':2,'root_native_folder_renames':0})
write(H/'evidence-verification.json',{'status':'PASS','overlays':summaries,'owner_events':checks,'originals':read(H/'download-verification.json'),'restored_sources':restores,'all_existing_Acanthus_objects_unchanged':True,'current_Acanthus_family_name':acroot['name'],'new_physical_verification':0})
evidence={}
for p in list((H/'live').glob('*.json'))+[H/n for n in ['family-metadata-current.json','image-and-parent-metadata-current.json','download-verification.json','evidence-verification.json','native-current-crosswalk.json']]:evidence[str(p)]={'sha256':sha(p)}
write(H/'evidence-manifest.json',evidence)
print(json.dumps({'status':'PASS','native_objects':len(objects),'owner_events_verified':len(checks),'overlay_families':len(summaries),'restored_same_file_ids':2,'recreated_parent_id':newparent['id']}))
