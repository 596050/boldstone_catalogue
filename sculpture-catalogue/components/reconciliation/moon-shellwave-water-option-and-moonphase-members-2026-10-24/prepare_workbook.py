"""Append one current option and six fields; retain all historical source tabs."""
import copy,importlib.util,json,posixpath,re
from pathlib import Path
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name;read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);w=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');proj=read(H/'projection-index.json');OLD=proj['old_output'];o=g['options'][-1];oid=o['product_id'];r=198;d=1138;last=1143;cov=a['coverage'][-1];ref=cov['individual']['reference'];entry=read(H/'new-option-listing-entry.json');draft=entry['draft_listing'];changes={};forms={};links={};heights={};bounds={'Master Catalogue':197,'Specifications':1137,'Photo Coverage':197,'Listing Resolution':197,'Draft Listings':113,'Selling Details':197}
def value(sn,c,v):
 assert c not in w['formulas'][sn]
 before=w['values'][sn].get(c,'')
 if before!=v or int(re.search(r'\d+',c)[0])>bounds.get(sn,10**9):changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':v}
def formula(sn,c,f,expected):forms[(sn,c)]={'sheet':sn,'cell':c,'before':w['formulas'][sn].get(c,''),'formula':f,'expected':expected}
def link(sn,c,label,target):value(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
L=lambda target,label:{'target':target,'label':label}
def row(sn,r,values):
 for i,v in enumerate(values):
  c=n.column(i)+str(r)
  if isinstance(v,dict):link(sn,c,v['label'],v['target'])
  else:value(sn,c,v);links.pop((sn,c),None)
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rels={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rels[x.get('{'+n.R+'}id')];links[(sn,c)]={'sheet':sn,'cell':c,'label':w['values'][sn].get(c,''),'target':u.replace(OLD,str(OUT))}
image=L(ref['image_url'],'Whole water-scene group reference');folder=L(ref['folder_url'],'Actual containing folder');limits=o['source_scope_notes'];fields=list(o['master_fields'])
row('Master Catalogue',r,[oid,o['name'],o['family'],o['canonical_component_id'],*['']*6,6,'Six working fields recorded',o['identity_basis'],image,folder,L("#'Specifications'!D1138",'Six qualified working fields'),o['file_id'],o['folder_id'],o['orientation_options'],image,folder,limits,'','New current option; exact Squarespace/Shopify build and SKU unverified','\n'.join(o['source_scopes'])])
for j,f in enumerate(fields):
 z=o['master_fields'][f];rr=d+j;row('Specifications',rr,[oid,o['name'],f,z['display'],z['state'],z['basis'],'\n'.join(z['source_scopes']),'',1,image,folder,o['file_id'],o['folder_id'],'\n'.join(z['proposal_ids']),'',oid+'::'+f,'']);heights[('Specifications',rr)]=180;formula('Specifications','Q'+str(rr),f'=IF(AND(I{rr}=1,COUNTBLANK(D{rr})=0,COUNTIFS($P$10:$P$1143,P{rr})=1),1,0)',1)
 key=f'$A{r}&"::{f}"';formula('Master Catalogue',n.column(j+4)+str(r),f'=IF(COUNTIFS(\'Specifications\'!$P$10:$P$1143,{key},\'Specifications\'!$Q$10:$Q$1143,1)=1,INDEX(\'Specifications\'!$D$10:$D$1143,MATCH({key},\'Specifications\'!$P$10:$P$1143,0)),"Working detail missing, unaccepted or duplicated")',z['display'])
formula('Master Catalogue','K198',"=COUNTIFS('Specifications'!$A$10:$A$1143,A198,'Specifications'!$Q$10:$Q$1143,1)",6);formula('Master Catalogue','L198','=IF(K198=6,"Six working fields recorded","Working details incomplete")','Six working fields recorded')
row('Photo Coverage',r,[oid,o['name'],cov['individual']['status'],image,folder,cov['in_situ']['status'],image,folder,cov['series']['status'],image,folder,'\n'.join(cov[k]['basis']for k in ['individual','in_situ','series']),ref['file_id'],ref['folder_id'],ref['file_id'],ref['folder_id'],ref['file_id'],ref['folder_id'],cov['scope'],cov['scene_origin'],cov['owner_review'],'Family / series relevant — qualified whole-scene source'])
row('Listing Resolution',r,[oid,o['name'],'New current option; platform verification pending',0,0,0,'','','','','','',draft['proposed_sku'],'','','',entry['next_action'],image,folder,ref['file_id'],ref['folder_id'],limits,'','New owner-approved water-build catalogue option; no native individual offer asserted'])
row('Draft Listings',114,[oid,o['name'],'Individual option draft',draft['proposed_sku'],draft['proposed_product_group_id'],draft['proposed_variant_reference'],o['sale_unit'],L("#'Specifications'!D1138",'Six qualified working fields'),image,folder,ref['file_id'],ref['folder_id'],'New current option; platform verification pending','\n'.join(entry['remaining_evidence_gaps']),draft['activation_condition'],draft['media_condition'],'Draft only; not created',''])
row('Selling Details',r,[oid,o['name'],'','','estimate','per individual panel','','','',o['master_fields']['Individual price']['basis'],o['selling_details']['included_or_excluded_scope'],image,folder,ref['file_id'],ref['folder_id'],'Working catalogue only; no native listing-readiness upgrade','Estimated panel price only; made-to-order1–2weeks is owner policy; exact water configuration and stock unverified.'])
for c,ix,f in [('C',9,'Individual price'),('D',10,'Availability')]:formula('Selling Details',c+'198',f"=VLOOKUP($A198,'Master Catalogue'!$A$10:$Y$198,{ix},FALSE)",o['master_fields'][f]['display'])
formula('Selling Details','G198','=IF(ISNUMBER(SEARCH("1–2 weeks",D198)),"1–2 weeks",IF(ISNUMBER(SEARCH("1 week",D198)),"1 week","Check source policy"))','1–2 weeks')
task=a['missing_pictures'][-1];row('Missing Pictures',219,[task['priority'],oid,o['name'],'Individual',task['action_type'],task['action'],image,folder,ref['file_id'],ref['folder_id'],task['scope'],task['qualification'],task['owner_response'],task['status']]);heights[('Missing Pictures',219)]=210
for sn in ['Master Catalogue','Photo Coverage','Listing Resolution','Selling Details']:heights[(sn,r)]=240
heights[('Draft Listings',114)]=240
# Current ranges extend by one option/six fields. Dated source-value tabs remain unchanged.
for sn,fs in w['formulas'].items():
 for c,f in fs.items():
  ff=re.sub(r'(:\$?[A-Z]+)(\$?)197\b',lambda z:z.group(1)+z.group(2)+'198',f);ff=re.sub(r'(:\$?[A-Z]+)(\$?)1137\b',lambda z:z.group(1)+z.group(2)+'1143',ff)
  if sn=='Draft Listings':ff=ff.replace(':C113',':C114')
  if ff!=f:formula(sn,c,ff,w['values'][sn][c])
componentrow=next(i for i,c in enumerate(g['components'],10)if c['component_id']=='BC-MSW-MOON');forms[('Components','D'+str(componentrow))]['expected']=3
arrrow=next(int(c[1:])for c,v in w['values']['Sets and Context'].items()if re.fullmatch('A\\d+',c)and v==proj['arrangement_reference_id']);membernames=[next(x for x in g['options']if x['product_id']==i)['name']for i in proj['member_option_ids']]
value('Sets and Context','D'+str(arrrow),'Owner-confirmed existing White designs: '+'; '.join(membernames));value('Sets and Context','G'+str(arrrow),w['values']['Sets and Context'].get('G'+str(arrrow),'')+'\n24 October: owner confirms MP1–MP4 White membership only. Quantities, positions, water-ready build and fountain sale unit remain unconfirmed.');heights[('Sets and Context',arrrow)]=210
for ident in proj['member_option_ids']:
 rr=next(i for i,x in enumerate(g['options'],10)if x['product_id']==ident);value('Master Catalogue','V'+str(rr),w['values']['Master Catalogue'].get('V'+str(rr),'')+'\n24 October: owner-confirmed named White design member of REF-MOONPHASE-WATER-FEATURE-WHITE-01. No position, quantity, same physical cast or water-ready build inferred.');heights[('Master Catalogue',rr)]=max(210,float(next(x.get('ht','0')for x in w['sheets']['Master Catalogue']['root'].find(n.q('sheetData'))if int(x.get('r'))==rr)))
expected={('Master Catalogue','B4'):188,('Master Catalogue','F4'):188,('Master Catalogue','H4'):187,('Photo Coverage','B4'):177,('Photo Coverage','D4'):166,('Photo Coverage','F4'):117,('Photo Coverage','B5'):11,('Missing Pictures','B4'):39,('Missing Pictures','D4'):1,('Missing Pictures','F4'):55,('Listing Resolution','D5'):104,('Draft Listings','B4'):101,('Selling Details','B4'):188,('Selling Details','D4'):187,('Selling Details','F4'):187}
for k,v in expected.items():
 if k in forms:forms[k]['expected']=v
 else:formula(*k,w['formulas'][k[0]][k[1]],v)
for k in list(changes):
 if k in forms:changes.pop(k)
headers={'Master Catalogue':'188 active options;112 working component identities. Moon and Shellwave2 White Water Feature added as a separate individual water-build option; MP1–MP4 White arrangement memberships confirmed. Estimates and all prior holds retained.','Photo Coverage':'188 active options.177 complete individual images;11 technical gaps including9 owner-accepted group references, one deferred Frozen Fish identity and one new water-build individual-photo requirement.166 context and117 Series references are qualified;22 context gaps held.','Missing Pictures':'40 diagnostic actions:22 held context,16 Series (15 active, one held), one deferred Frozen Fish identity and one new water-build individual photograph requirement. No existing image gap closed.','Selling Details':'188 active options:187 estimated prices and one specific owner price. New White Water Feature panel estimate£750; pump, basin, pipework and installation quoted separately.','Listing Resolution':'188 active catalogue options. One new individual Water Feature build awaits authenticated platform review; source snapshots retain their dated scope. No platform writes.','Draft Listings':'101 proposed individual-option drafts and3 custom/unlisted Wall Circle scopes. One retained retired draft stays historical. No native product or SKU created.'}
for sn,text in headers.items():link(sn,'A3',text,str(OUT/('water-products-and-memberships.html'if sn=='Master Catalogue'else'remaining-photograph-requests.html'if sn in ['Photo Coverage','Missing Pictures']else'selling-details.html'if sn=='Selling Details'else'water-products-and-memberships.html')))
for k,v in changes.items():
 if k in links:links[k]['label']=v['value']
appends=[{'sheet':sn,'old_last':oldlast,'rows':num,'columns':cols}for sn,oldlast,num,cols in [('Master Catalogue',197,1,25),('Specifications',1137,6,17),('Photo Coverage',197,1,22),('Listing Resolution',197,1,24),('Draft Listings',113,1,18),('Selling Details',197,1,17)]]
def blocks(items,kind):
 groups={};out=[]
 for x in items:groups.setdefault((x['sheet'],re.match('[A-Z]+',x['cell'])[0]),[]).append(x)
 for(sn,col),items in groups.items():
  items.sort(key=lambda x:int(x['cell'][len(col):]));run=[]
  def emit():
   if run:out.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],kind:[[x['value'if kind=='values'else'formula']]for x in run]})
  for x in items:
   if run and int(x['cell'][len(col):])!=int(run[-1]['cell'][len(col):])+1:emit();run=[]
   run.append(x)
  emit()
 return out
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':blocks(changes.values(),'values'),'formula_blocks':blocks(forms.values(),'formulas'),'hyperlinks':list(links.values()),'row_heights':[{'sheet':sn,'row':rr,'height':h}for(sn,rr),h in heights.items()],'table_appends':appends,'new_sheets':{},'target_rows':[],'expected_original_sheet_count':28,'expected_formula_count':3407,'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'new_option_row':r,'first_spec_row':d,'last_spec_row':last,'price_spec_row':1142,'member_arrangement_row':arrrow,'baseline_ranges':[['Master Catalogue','A195:D197','baseline-option-tail'],['Sets and Context','A'+str(arrrow)+':G'+str(arrrow),'baseline-water-membership']],'preview_ranges':[['Master Catalogue','A198:D198','01-new-option-identity'],['Specifications','C1138:F1140','02-new-physical-estimates'],['Specifications','C1141:F1143','03-new-fixing-price-policy'],['Photo Coverage','A198:L198','04-qualified-group-source-roles'],['Selling Details','A198:G198','05-new-selling-detail'],['Sets and Context','A'+str(arrrow)+':G'+str(arrrow),'06-moonphase-membership']],'supplemental_preview_ranges':[['Master Catalogue','A2:J4','07-current-population-summary'],['Photo Coverage','L198:V198','08-new-photo-role-qualifications'],['Missing Pictures','E219:N219','09-new-individual-source-gap']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','new_option_id':oid,'value_edits':len(changes),'formula_edits':len(forms),'formula_count':3407,'hyperlinks':len(links),'table_appends':6,'arrangement_row':arrrow}))
