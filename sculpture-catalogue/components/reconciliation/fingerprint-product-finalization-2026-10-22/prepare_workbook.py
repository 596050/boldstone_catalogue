"""Plan scoped row replacements, two appended options, and dependent range changes."""
import copy,importlib.util,json,math,posixpath,re
from pathlib import Path
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('n',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
b=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');packet=read(H/'inputs/product_packet.before');opts=read(H/'new-current-options.json');comps=read(H/'new-current-components.json');oldids=set(packet['legacy_disposition']['product_ids']);newids={x['product_id']for x in opts};FIELDS=['Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability'];changes={};formula_changes={};links={};heights={};new_values={};cleared=[]
def setcell(sn,c,v):
 before=b['values'][sn].get(c,'')
 if before!=v or c not in b['values'][sn]:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':v}
def formula(sn,c,f,expected):formula_changes[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn].get(c,''),'formula':f,'expected':expected}
for sn,z in b['sheets'].items():
 loc=z['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for h in z['root'].findall('.//'+n.q('hyperlink')):
  c=h.get('ref');links[(sn,c)]={'sheet':sn,'cell':c,'label':b['values'][sn].get(c,''),'target':'#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target')}
def linkcell(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
L=lambda u,label:{'label':label,'target':u}
def row(sn,r,values):
 for j,v in enumerate(values):
  c=n.column(j)+str(r)
  if isinstance(v,dict)and'target'in v:linkcell(sn,c,v['label'],v['target'])
  else:
   if c in b['formulas'][sn]:continue
   setcell(sn,c,v)
   if(sn,c)in links:del links[(sn,c)]
def findrow(sn,key):return next(int(re.search(r'\d+',c)[0])for c,v in b['values'][sn].items()if re.fullmatch('A[0-9]+',c)and v==key)
optrows={x['product_id']:i+10 for i,x in enumerate(g['options'])};specrows={x['product_id']:10+i*6 for i,x in enumerate(g['options'])}
for x in opts:
 oid=x['product_id'];r=optrows[oid];d=specrows[oid]
 values=[oid,x['name'],'Fingerprint',x['canonical_component_id'],*[x['master_fields'][f]['display']for f in FIELDS],6,'Six working fields recorded','Owner-selected current numbered component / finish',L(x['image_url'],'Original individual JPEG'),L(x['folder_url'],'Actual photo folder'),L("#'Specifications'!D"+str(d),'Six working fields'),x['file_id'],x['folder_id'],'Custom orientation available',L(x['context_image_url'],'Full arrangement'),L(x['context_folder_url'],'Actual group folder'),'Working size/depth/weight/material/supply remain proposals or estimates. Numeric price, actual stock/lead time, measured specifications and native individual offer remain unverified.','','New current individual option; exact Squarespace/Shopify variant not verified','\n'.join(x['source_scopes'])]
 row('Master Catalogue',r,values);heights[('Master Catalogue',r)]=156
 for j,f in enumerate(FIELDS):
  v=x['master_fields'][f];sr=d+j;row('Specifications',sr,[oid,x['name'],f,v['display'],v['state'],v['basis'],'\n'.join(v['source_scopes']),'',1,L(x['image_url'],'Original JPEG'),L(x['folder_url'],'Actual photo folder'),x['file_id'],x['folder_id'],'\n'.join(v['proposal_ids']),'',oid+'::'+f,1]);heights[('Specifications',sr)]=120
 for j,f in enumerate(FIELDS):
  key=f'$A{r}&"::{f}"';ff=f'=IF(COUNTIFS(\'Specifications\'!$P$10:$P$1125,{key},\'Specifications\'!$Q$10:$Q$1125,1)=1,INDEX(\'Specifications\'!$D$10:$D$1125,MATCH({key},\'Specifications\'!$P$10:$P$1125,0)),"Working detail missing, unaccepted or duplicated")';formula('Master Catalogue',n.column(j+4)+str(r),ff,x['master_fields'][f]['display'])
 formula('Master Catalogue','K'+str(r),f"=COUNTIFS('Specifications'!$A$10:$A$1125,A{r},'Specifications'!$Q$10:$Q$1125,1)",6);formula('Master Catalogue','L'+str(r),f'=IF(K{r}=6,"Six working fields recorded","Working details incomplete")','Six working fields recorded')
 cr=next(z for z in a['coverage']if z['option_id']==oid);p=cr['individual']['reference'];ins=cr['in_situ']['reference'];series=cr['series']['reference']
 row('Photo Coverage',r,[oid,x['name'],'Available',L(p['image_url'],'Original individual JPEG'),L(p['folder_url'],'Actual photo folder'),'Available',L(ins['image_url'],'Staged mounted-wall image'),L(ins['folder_url'],'Actual photo folder'),'Available',L(series['image_url'],'Full arrangement'),L(series['folder_url'],'Actual group folder'),'Complete standalone original JPEG; staged wall context; verified arrangement membership. No measured dimensions, hidden hardware or exact historical physical alias inferred.',p['file_id'],p['folder_id'],ins['file_id'],ins['folder_id'],series['file_id'],series['folder_id'],cr['scope'],cr['scene_origin'],cr['owner_review'],'Family / series relevant']);heights[('Photo Coverage',r)]=120
for i,x in enumerate(g['components'],10):
 if x['component_id']not in {z['component_id']for z in comps}:continue
 row('Components',i,[x['component_id'],x['name'],'Fingerprint',2,x['scope_note'],L(x['image_url'],'Original JPEG'),L(x['folder_url'],'Actual photo folder'),x['file_id'],x['folder_id'],'\n'.join(x['source_component_ids']),'\n'.join(x['retained_names'])]);heights[('Components',i)]=108;formula('Components','D'+str(i),f"=COUNTIFS('Master Catalogue'!$D$10:$D$195,A{i})",2)
# Rebase every dependent population/field bound; unrelated cached results are preserved.
for sn,fs in b['formulas'].items():
 for c,f in fs.items():
  new=f
  if sn in ['Master Catalogue','Specifications']:new=new.replace('$1113','$1125')
  if sn in ['Components','Gleneagles Folders','Lava Moon Folders']:new=new.replace('$193','$195')
  if sn in ['Master Catalogue','Photo Coverage','Listing Resolution']:new=re.sub(r'(:[A-Z]+)193\b',r'\g<1>195',new)
  if sn=='Master Catalogue'and c=='D4':new=new.replace('A120','A121')
  if new!=f and(sn,c)not in formula_changes:formula(sn,c,new,b['values'][sn][c])
for r in range(10,1126):formula('Specifications','Q'+str(r),f'=IF(AND(I{r}=1,COUNTBLANK(D{r})=0,COUNTIFS($P$10:$P$1125,P{r})=1),1,0)',1)
for c,v in [('B4',186),('D4',112),('F4',186),('H4',185)]:formula('Master Catalogue',c,formula_changes[('Master Catalogue',c)]['formula'],v)
for c,v in [('B4',164),('D4',125),('F4',115),('B5',22)]:
 if c in b['formulas']['Photo Coverage']:formula('Photo Coverage',c,formula_changes.get(('Photo Coverage',c),{}).get('formula',b['formulas']['Photo Coverage'][c]),v)
# The six legacy-scope picture rows move intact to history; current rows compact.
remaining_rows=[];remaining_heights=[]
for r in range(10,221):
 if b['values']['Missing Pictures'].get('B'+str(r))in oldids:continue
 vals=[]
 for j in range(14):
  c=n.column(j)+str(r);v=b['values']['Missing Pictures'].get(c,'');h=links.get(('Missing Pictures',c));vals.append(L(h['target'],v)if h else v)
 remaining_rows.append(vals);remaining_heights.append(float(next(z for z in b['sheets']['Missing Pictures']['root'].find(n.q('sheetData'))if z.get('r')==str(r)).get('ht',96)))
assert len(remaining_rows)==205
for key in list(links):
 if key[0]=='Missing Pictures'and int(re.search(r'\d+',key[1])[0])>=10:del links[key]
for i,vals in enumerate(remaining_rows,10):row('Missing Pictures',i,vals);heights[('Missing Pictures',i)]=remaining_heights[i-10]
for r in range(215,221):
 for j in range(14):setcell('Missing Pictures',n.column(j)+str(r),'')
formula('Missing Pictures','B4','=COUNTIFS(E10:E214,"Find / capture",N10:N214,"<>Resolved")',100);formula('Missing Pictures','D4','=COUNTIFS(E10:E214,"Verify existing image",N10:N214,"<>Resolved")',1);formula('Missing Pictures','F4','=COUNTIF(N10:N214,"Optional")',53)
# Current source-resolution and local draft views gain six unverified records.
reviews={x['product_id']:x for x in g['current_listing_resolution_details']['entries']}
for x in opts:
 oid=x['product_id'];r=optrows[oid];d=reviews[oid]['draft_listing'];row('Listing Resolution',r,[oid,x['name'],'New current option; platform verification pending',0,0,0,'','','','','','',d['proposed_sku'],'','','',x['current_listing_resolution']['next_action'],L(x['image_url'],'Original JPEG'),L(x['folder_url'],'Actual photo folder'),x['file_id'],x['folder_id'],'New owner-selected option; exact live individual variant and physical configuration are unverified.','','No prior exact individual record asserted']);heights[('Listing Resolution',r)]=132
for c in ['B4','D4','F4']:
 oldf=b['formulas']['Listing Resolution'][c];ff=re.sub(r'(:[A-Z]+)193\b',r'\g<1>195',oldf);expected=b['values']['Listing Resolution'][c]-(4 if c=='F4'else 0);formula('Listing Resolution',c,ff,expected)
formula('Listing Resolution','D5','=F4-COUNTIFS(F10:F195,1,D10:D195,1)-D4+COUNTIF(C10:C195,"New current option; platform verification pending")',102)
draft_rows=[];draft_heights=[]
for r in range(10,110):
 if b['values']['Draft Listings'].get('A'+str(r))in oldids:continue
 vals=[]
 for j in range(18):
  c=n.column(j)+str(r);v=b['values']['Draft Listings'].get(c,'');h=links.get(('Draft Listings',c));vals.append(L(h['target'],v)if h else v)
 draft_rows.append(vals);draft_heights.append(float(next(z for z in b['sheets']['Draft Listings']['root'].find(n.q('sheetData'))if z.get('r')==str(r)).get('ht',132)))
for x in opts:
 d=reviews[x['product_id']]['draft_listing'];draft_rows.append([x['product_id'],x['name'],'Individual option draft',d['proposed_sku'],d['proposed_product_group_id'],d['proposed_variant_reference'],x['sale_unit'],L("#'Specifications'!D"+str(specrows[x['product_id']]),'Six working fields'),L(x['image_url'],'Original individual JPEG'),L(x['folder_url'],'Actual photo folder'),x['file_id'],x['folder_id'],'New current option; platform verification pending','\n'.join(reviews[x['product_id']]['remaining_evidence_gaps']),d['activation_condition'],d['media_condition'],'Draft only; not created',''])
assert len(draft_rows)==102
for key in list(links):
 if key[0]=='Draft Listings'and int(re.search(r'\d+',key[1])[0])>=10:del links[key]
for r,vals in enumerate(draft_rows,10):row('Draft Listings',r,vals);heights[('Draft Listings',r)]=draft_heights[r-10]if r-10<len(draft_heights)else 156
formula('Draft Listings','B4','=COUNTIF(C10:C111,"Individual option draft")',99);formula('Draft Listings','D4','=COUNTIF(C10:C111,"Custom / unlisted pattern scope")',3)
# Connect the six formerly source-only rows to the new canonical records.
for x in opts:
 r=findrow('Fingerprint Current',x['source_inventory_id']);setcell('Fingerprint Current','A'+str(r),x['product_id']);formula('Fingerprint Current','B'+str(r),f"=VLOOKUP(A{r},'Master Catalogue'!$A$10:$Y$195,2,FALSE)",x['name']);setcell('Fingerprint Current','J'+str(r),'Historical directional comparison only; no exact physical alias');setcell('Fingerprint Current','K'+str(r),'Current record selected by owner');linkcell('Fingerprint Current','O'+str(r),'Six working fields; estimates labelled',"#'Specifications'!D"+str(specrows[x['product_id']]))
setcell('Fingerprint Current','A9','Current option ID');setcell('Fingerprint Current','A3','Three current owner-selected components, each in Cream and White. Six current option IDs link to Master Catalogue and Specifications. Older Left/Right offers are archived without an exact physical alias.');setcell('Fingerprint Current','E4','Legacy offers archived');formula('Fingerprint Current','F4',"=COUNTA('Fingerprint Folders'!A10:A13)",4)
setcell('Fingerprint Folders','A3','Four superseded Left/Right options remain here as history. They add no current sale options or active picture gaps. Current Fingerprint products are Concentric1/2/3 in Cream and White; exact historical physical aliases are not asserted.');setcell('Fingerprint Folders','C4','Current gaps from old offers');formula('Fingerprint Folders','D4','=COUNTIF(N10:N13,"Group only")',0)
for r in range(10,14):setcell('Fingerprint Folders','N'+str(r),'Superseded current offer');setcell('Fingerprint Folders','P'+str(r),'Archived by owner-selected current register. Exact prior record/specifications survive in Fingerprint History and the source register. No historical individual photo was found by this scope retirement.');linkcell('Fingerprint Folders','F'+str(r),'Archived current-offer scope',"#'Fingerprint History'!A9")
notes={'Components':'112 identified working catalogue components. Finish/size/build options are counted separately. Physical stock, mould count and whole-library unique design total remain unverified.','Photo Coverage':'186 current options. Fingerprint has six current records with standalone original JPEGs, staged wall context and full arrangements. Historical Left/Right actions are archived by scope; current individual gaps22, in situ61 and series18.','Missing Pictures':'205 current-source action rows, including101 required actions and53 optional series references. Six superseded Fingerprint action rows remain in history; this retirement does not claim photographs found for old records.','Source Mapping':'278 review rows and125 source component IDs retain historical dispositions. Their increments are source snapshots. Current186 options include owner-selected Fingerprint replacements; archived Left/Right targets do not add active offers.','Listing Resolution':'Current186 options. Prior native review remains a dated source snapshot for its surviving records; six new Fingerprint options await native verification.102 local draft/custom scopes are prepared; no platform execution.','Draft Listings':'99 proposed individual-option draft SKUs plus3 custom/unlisted Wall Circle scopes. Six new Fingerprint records are local proposals pending native lookup and commercial/physical checks. No listings or SKUs have been created.'}
for sn,text in notes.items():setcell(sn,'A3',text)
history_rows=[]
for x in read(H/'archived-records-and-actions.json')['options']:
 for f in FIELDS:
  v=x['master_fields'][f];arc=x['current_fingerprint_alias_review']['archived_primary_local_path'];history_rows.append([x['product_id'],x['name'],x['canonical_component_id'],f,v['display'],v['state'],v['basis'],'\n'.join(x['source_scopes']),L(arc,'Archived pair image'),x['file_id'],x['folder_id'],'Superseded current offer; exact prior record preserved',L(str((H/'archived-records-and-actions.json').resolve()),'Complete archived records and actions')])
new_sheet={'title':'Fingerprint superseded product records and working specifications','note':'Four prior Left/Right options and two component identities are retained as history. They add no current offers or active photograph gaps. Exact physical alias and Verdigris-to-Cream equivalence are not asserted.','headers':['Archived option ID','Earlier name','Earlier component ID','Specification','Earlier working description','Earlier review state','Earlier basis and qualifications','Original scopes','Archived source image','Historical file ID','Historical folder ID','Current disposition','Complete history'],'widths':[26,52,29,27,112,90,136,64,26,39,39,71,35],'rows':history_rows}
for (sn,c),x in changes.items():
 if(sn,c)in links:links[(sn,c)]['label']=x['value']
for key in list(changes):
 if key in formula_changes:del changes[key]
for sn in notes:heights[(sn,3)]=48
# New active records use explicit readable heights; original unrelated rows remain unchanged.
tables=[]
for sn,extra,columns in [('Master Catalogue',2,25),('Specifications',12,17),('Components',1,11),('Photo Coverage',2,22),('Listing Resolution',2,24),('Draft Listings',2,18)]:tables.append({'sheet':sn,'append_rows':extra,'columns':columns})
plan={'cell_changes':list(changes.values()),'formula_changes':list(formula_changes.values()),'hyperlinks':list(links.values()),'row_heights':[{'sheet':sn,'row':r,'height':v}for(sn,r),v in heights.items()],'table_appends':tables,'table_recreates':[{'sheet':'Missing Pictures','range':'A9:N214'},{'sheet':'Fingerprint Current','range':'A9:T15'}],'new_sheets':{'Fingerprint History':new_sheet},'new_sheet_count':1,'old_sheet_count':25,'baseline_ranges':[['Master Catalogue','A84:D87','baseline-fp-options'],['Master Catalogue','A2:H4','baseline-summary'],['Specifications','A454:F456','baseline-fp-specs']],'preview_ranges':[['Master Catalogue','A2:H4','01-current-counts'],['Master Catalogue','A84:D87','02-fp-current-options'],['Master Catalogue','A194:D195','03-appended-options'],['Specifications','A454:F456','04-qualified-working-fields'],['Fingerprint Current','A9:O11','05-current-canonical-links'],['Photo Coverage','A2:L4','06-current-photo-counts'],['Fingerprint History','A9:F12','07-preserved-history']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-ordered-current-option-ids.json',[x['product_id']for x in g['options']]);write(H/'expected-ordered-component-ids.json',[x['component_id']for x in g['components']])
print(json.dumps({'status':'WORKBOOK_PLAN_READY','cell_changes':len(changes),'formula_changes':len(formula_changes),'table_appends':len(tables),'new_history_rows':len(history_rows),'current_options':186,'current_components':112}))
