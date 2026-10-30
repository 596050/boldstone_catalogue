import json,importlib.util,collections,posixpath,re,math
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');cross=read(H/'native-current-crosswalk.json');objects=cross['current_objects'];oldpaths=cross['old_path_to_id'];result=read(H/'preparation-verification.json');full=set(result['complete_individual_images_added']);accepted=set(result['owner_accepted_qualified_reference_exceptions']);specids=set(result['working_spec_confirmation_options']);restored={x['file_id']for x in cross['restored_sources']};changes={};links={};forms={};heights={}
OUT=B/'outputs/approved-images-folder-refresh-2026-10-23'
archive_names={objects[f]['name']:f for f in restored}
def setcell(sn,c,v):
 if c in b['formulas'][sn]:return
 before=b['values'][sn].get(c,'')
 if before!=v:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':v}
def linkcell(sn,c,label,target):
 setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
def protected(sn,c):return sn=='Source Specifications'and re.fullmatch(r'[MN]\d+',c)or sn=='Fingerprint History'or sn=='Moonphases and Dune'and re.fullmatch(r'I\d+',c)
def urlid(u):
 if not isinstance(u,str):return None
 if u.startswith('/')and Path(u).name in archive_names:return archive_names[Path(u).name]
 if not u.startswith('https://www.dropbox.com/'):return None
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):
   p=p[len(route):];name=parse_qs(z.query).get('preview',[''])[0];return oldpaths.get((p+('/'+name if name else '')).casefold())
 return None
def currenturl(u):
 fid=urlid(u)
 if fid==cross['historical_Acanthus_parent_id']:fid=cross['recreated_Acanthus_parent_id']
 if fid not in objects:return u
 x=objects[fid];return'https://www.dropbox.com/'+('preview'if x['object_type']=='file'else'home')+quote(x['display_path'],safe='/')
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rs[x.get('{'+n.R+'}id')].get('Target');target=u if protected(sn,c)else currenturl(u);label=b['values'][sn].get(c,'')
  if not protected(sn,c)and urlid(u)in restored:label='Restored original image';setcell(sn,c,label)
  links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
 for c,v in b['values'][sn].items():
  if not protected(sn,c)and isinstance(v,str)and v.startswith('https://www.dropbox.com/')and currenturl(v)!=v:setcell(sn,c,currenturl(v))
# Every current reference updates its actual containing folder as well as its file URL.
pairs={'Specifications':[('J','K','L','M')],'Components':[('F','G','H','I')],'Master Catalogue':[('N','O','Q','R')],'Photo Coverage':[('D','E','M','N'),('G','H','O','P'),('J','K','Q','R')],'Missing Pictures':[('G','H','I','J')],'Identity Review':[('G','H','I','J'),('L','M','O','P')],'Listing Reconciliation':[('M','N','O','P')],'Listing Offer Links':[('R','S','T','U')],'Listing Issues':[('J','K','L','M')],'Listing Resolution':[('R','S','T','U')],'Draft Listings':[('I','J','K','L')],'Selling Details':[('L','M','N','O')]}
for sn,cols in pairs.items():
 for im,folder,fc,pc in cols:
  for c,fid in b['values'][sn].items():
   if re.fullmatch(fc+r'\d+',c)and int(c[len(fc):])>=10 and fid in objects and objects[fid]['object_type']=='file':
    r=c[len(fc):];x=objects[fid];setcell(sn,pc+r,x['parent_id']);linkcell(sn,im+r,'Restored original image'if fid in restored else links.get((sn,im+r),{}).get('label',b['values'][sn].get(im+r,'Image')),'https://www.dropbox.com/preview'+quote(x['display_path'],safe='/'));linkcell(sn,folder+r,'Containing folder','https://www.dropbox.com/home'+quote(posixpath.dirname(x['display_path']),safe='/'))
# Preserve historical Source Specifications IDs, while refreshing its explicitly current H/I links.
for c,fid in b['values']['Source Specifications'].items():
 if re.fullmatch(r'J\d+',c)and fid in objects and objects[fid]['object_type']=='file':
  r=c[1:];x=objects[fid];linkcell('Source Specifications','H'+r,'Current image','https://www.dropbox.com/preview'+quote(x['display_path'],safe='/'));linkcell('Source Specifications','I'+r,'Current containing folder','https://www.dropbox.com/home'+quote(posixpath.dirname(x['display_path']),safe='/'))
cov={x['option_id']:x for x in a['coverage']};ids={x['product_id']:i+10 for i,x in enumerate(g['options'])}
for x in g['options']:
 oid=x['product_id'];r=ids[oid];cr=cov[oid]
 if oid in full:
  primary=cr['individual']['reference']
  for sn,ic,fc,fidc,pidc in [('Master Catalogue','N','O','Q','R'),('Photo Coverage','D','E','M','N'),('Selling Details','L','M','N','O'),('Listing Resolution','R','S','T','U'),('Draft Listings','I','J','K','L')]:
   rr=next((int(c[1:])for c,v in b['values'][sn].items()if re.fullmatch(r'A\d+',c)and v==oid),None)
   if rr is not None:
    linkcell(sn,ic+str(rr),'Owner-approved complete individual image',primary['image_url']);linkcell(sn,fc+str(rr),'Containing folder',primary['folder_url']);setcell(sn,fidc+str(rr),primary['file_id']);setcell(sn,pidc+str(rr),primary['folder_id'])
  for rr in range((r-10)*6+10,(r-10)*6+16):
   linkcell('Specifications','J'+str(rr),'Owner-approved complete individual image',primary['image_url']);linkcell('Specifications','K'+str(rr),'Containing folder',primary['folder_url']);setcell('Specifications','L'+str(rr),primary['file_id']);setcell('Specifications','M'+str(rr),primary['folder_id'])
  setcell('Photo Coverage','C'+str(r),'Available');setcell('Photo Coverage','L'+str(r),cr['individual']['basis']);setcell('Photo Coverage','T'+str(r),cr['scene_origin']);setcell('Photo Coverage','U'+str(r),cr['owner_review']);setcell('Master Catalogue','V'+str(r),'Owner-approved complete individual listing image. Creation origin and exact cast unverified; existing context-photo and physical-specification checks retain their own scope.');heights[('Photo Coverage',r)]=180
  for sn in ['Gleneagles Folders','Lava Moon Folders']:
   rr=next((int(c[1:])for c,v in b['values'][sn].items()if re.fullmatch(r'A\d+',c)and v==oid),None)
   if rr is not None:
    linkcell(sn,'F'+str(rr),'Owner-approved individual PNG',primary['image_url']);setcell(sn,'P'+str(rr),'Owner explicitly accepts this complete individual listing image23October2026. Creation origin remains unconfirmed. The prior group example and its actual containing folder remain context. Physical details retain their existing qualifications.');forms[(sn,'N'+str(rr))]={'sheet':sn,'cell':'N'+str(rr),'before':b['formulas'][sn]['N'+str(rr)],'formula':b['formulas'][sn]['N'+str(rr)],'expected':'Available'}
 if oid in accepted:
  approval=x['owner_accepted_listing_references'];text='Owner accepts existing listing reference; technical '+cr['individual']['status']+' retained. '+('White image is DESIGN ONLY; Beige pair shows LEFT finish.'if oid=='BSI-95ECE169007F'else'White image is DESIGN ONLY; Beige pair shows RIGHT finish.'if oid=='BSI-6C2DDC69FB83'else'Whole group photograph retained; component position unchanged.');setcell('Photo Coverage','L'+str(r),text);linkcell('Photo Coverage','U'+str(r),'Accepted qualified references',str(OUT/'accepted-listing-references.html')+'#'+oid);setcell('Master Catalogue','V'+str(r),text);heights[('Photo Coverage',r)]=156
 if oid in specids:
  for j,(f,v)in enumerate(x['master_fields'].items()):
   rr=(r-10)*6+10+j;setcell('Specifications','E'+str(rr),v['state']);setcell('Specifications','F'+str(rr),v['basis']);heights[('Specifications',rr)]=max(156,min(390,18+13*math.ceil(len(v['basis'])/95)))
 if oid=='BSI-C41824131174':
  setcell('Master Catalogue','V'+str(r),'Sandstone detail and workshop-group originals restored by original file ID; containing folder recreated with new ID. Detail-only individual coverage remains. Actual measurements, weight, material recipe and fitted hardware pending.');setcell('Photo Coverage','L'+str(r),'Original detail/workshop image links restored. Workshop positions remain Sandstone BACK CENTRE and Pewter BACK RIGHT. Detail-only coverage remains; no new full individual photograph or in-situ image verified.');heights[('Photo Coverage',r)]=156
for r,x in enumerate(a['missing_pictures'],10):
 prior=read(H/'inputs/audit.before')['missing_pictures'][r-10]
 if x==prior:continue
 ref=x['reference'];values=[x['priority'],x['option_id'],x['name'],x['role'],x['action_type'],x['action'],'Available reference','Containing folder',ref['file_id'],ref['folder_id'],x['scope'],x['qualification'],x.get('owner_response',''),x['status']]
 for j,v in enumerate(values):setcell('Missing Pictures',n.column(j)+str(r),v)
 linkcell('Missing Pictures','G'+str(r),'Available reference',ref['image_url']);linkcell('Missing Pictures','H'+str(r),'Containing folder',ref['folder_url']);heights[('Missing Pictures',r)]=max(132,min(300,18+13*math.ceil(len(x['qualification'])/95)))
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):11,('Missing Pictures','B4'):86}
expected[('Missing Pictures','D4')]=1
for sn in ['Gleneagles Folders','Lava Moon Folders']:expected[(sn,'D4')]=0
for key,value in expected.items():forms[key]={'sheet':key[0],'cell':key[1],'before':b['formulas'][key[0]][key[1]],'formula':b['formulas'][key[0]][key[1]],'expected':value}
notes={'Master Catalogue':'188 current individual options across112 working component identities. Seven complete listing images and five scoped reference exceptions imported. Current folder links and Acanthus originals refreshed; qualified specifications retained.','Photo Coverage':'177 complete individual references. Eleven technical individual/identity gaps remain: five accepted group/combined references plus six outstanding entries. Outstanding: five separate photographs and one deferred Frozen Fish identity.63 in situ and18 series gaps.','Missing Pictures':'208 action rows:87 open required actions,54 optional and67 resolved. Seven complete images and five owner-accepted reference exceptions close12 individual review tasks; technical image roles remain separately labelled.'}
notes['Gleneagles Folders']='Four complete numbered White PNGs explicitly accepted for individual listing use. Existing group photographs remain context. Photographic/generated creation origin and exact physical cast remain unverified.'
notes['Lava Moon Folders']='Three complete White PNGs explicitly accepted for individual listing use. Existing group photographs remain context. Sandstone review decisions after this frozen import remain queued separately; creation origin and physical details retain their qualifications.'
for sn,text in notes.items():setcell(sn,'A3',text);heights[(sn,3)]=66
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
def blocks(items,kind):
 groups=collections.defaultdict(list);out=[]
 for x in items:groups[(x['sheet'],re.match('[A-Z]+',x['cell'])[0])].append(x)
 for(sn,col),xs in groups.items():
  run=[]
  for x in sorted(xs,key=lambda v:int(v['cell'][len(col):])):
   if run and int(x['cell'][len(col):])!=int(run[-1]['cell'][len(col):])+1:out.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],kind:[[z['value'if kind=='values'else'formula']]for z in run]});run=[]
   run.append(x)
  if run:out.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],kind:[[z['value'if kind=='values'else'formula']]for z in run]})
 return out
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':blocks(changes.values(),'values'),'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[{'sheet':sn,'row':r,'height':v}for(sn,r),v in heights.items()],'table_appends':[],'new_sheets':{},'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'baseline_ranges':[['Photo Coverage','A2:L5','baseline-photo-summary'],['Specifications','C'+str((ids['BSI-86E6AEA0EB98']-10)*6+10)+':F'+str((ids['BSI-86E6AEA0EB98']-10)*6+11),'baseline-fish-specs']],'preview_ranges':[['Photo Coverage','A2:L5','01-current-photo-summary'],['Photo Coverage','A'+str(ids['BSI-53239DE28BCA'])+':L'+str(ids['BSI-53239DE28BCA']),'02-approved-gleneagles'],['Specifications','C'+str((ids['BSI-86E6AEA0EB98']-10)*6+10)+':F'+str((ids['BSI-86E6AEA0EB98']-10)*6+11),'03-fish-qualified-spec-acceptance'],['Missing Pictures','A2:N4','04-current-actions'],['Photo Coverage','A'+str(ids['BSI-95ECE169007F'])+':L'+str(ids['BSI-95ECE169007F']),'05-raked-qualified-references']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
print(json.dumps({'status':'PLAN_READY','changed_cells':len(changes),'links':len(links),'summary_caches':plan['summary_expected'],'formulas_unchanged':plan['expected_formula_count']}))
