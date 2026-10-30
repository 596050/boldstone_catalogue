from pathlib import Path,PurePosixPath
from collections import Counter
from datetime import datetime,timezone
from zipfile import ZipFile
from io import BytesIO
import json,hashlib,xml.etree.ElementTree as ET,sys
b=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue');j=b/'components/parallel-reviews/remaining-photo-sources-and-bordered-import-20261023T200049Z';ws=json.loads((j/'verification-workspace.json').read_text());v=Path(ws['private_verification_workspace']);old=Path(ws['baseline_workbook'])
S='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}';R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}';P='{http://schemas.openxmlformats.org/package/2006/relationships}'
def sha(data):return hashlib.sha256(data).hexdigest()
def loadbook(data):
 z=ZipFile(BytesIO(data));assert z.testzip() is None
 ss=[]
 if 'xl/sharedStrings.xml' in z.namelist():ss=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(S+'si')]
 rel={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))};wb=ET.fromstring(z.read('xl/workbook.xml'));sheets={};forms={};linkcount=0
 for sh in wb.find(S+'sheets'):
  name=sh.attrib['name'];target=rel[sh.attrib[R+'id']];path=target.lstrip('/') if target.startswith('/') else 'xl/'+target;root=ET.fromstring(z.read(path));cells={};links={};relationships={};relp=str(PurePosixPath(path).parent/'_rels'/(PurePosixPath(path).name+'.rels'))
  if relp in z.namelist():relationships={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read(relp))}
  for c in root.findall('.//'+S+'sheetData/'+S+'row/'+S+'c'):
   cell=c.attrib['r'];typ=c.attrib.get('t');value=c.find(S+'v');text=value.text if value is not None else None
   if typ=='s':text=ss[int(text)] if text is not None else ''
   elif typ=='inlineStr':text=''.join(c.find(S+'is').itertext()) if c.find(S+'is') is not None else ''
   f=c.find(S+'f');formula=f.text if f is not None else None
   if formula is not None:forms[(name,cell)]=formula
   cells[cell]={'value':text or '', 'formula':formula,'style':c.attrib.get('s','0')}
  h=root.find(S+'hyperlinks')
  if h is not None:
   for x in h:
    links[x.attrib['ref']]=relationships.get(x.attrib.get(R+'id')) or '#'+x.attrib.get('location','');linkcount+=1
  sheets[name]={'cells':cells,'links':links}
 return {'sheets':sheets,'formulas':forms,'hyperlinks':linkcount}
ptrbytes=(b/'current-master.json').read_bytes();ptr=json.loads(ptrbytes);assert ptr['workbook_sha256']!=sha(old.read_bytes()),'No newer workbook has been published'
source=b/ptr['workbook'];data=source.read_bytes();assert sha(data)==ptr['workbook_sha256'];snapshot=v/'final-published-catalogue.xlsx';assert not snapshot.exists();snapshot.write_bytes(data)
before=loadbook(old.read_bytes());after=loadbook(data);checks=[]
def ck(label,condition,**details):
 checks.append({'label':label,'pass':bool(condition),**details})
 if not condition:raise AssertionError(label+str(details))
ck('Published hash bound to immutable verification snapshot',sha(snapshot.read_bytes())==ptr['workbook_sha256'])
ck('All28 sheet names/order preserved',list(before['sheets'])==list(after['sheets']) and len(after['sheets'])==28)
ck('All3390 formula texts/cell locations preserved',before['formulas']==after['formulas'] and len(after['formulas'])==3390)
for name in ['Specifications','Selling Details']:
 ck(name+' all original cell values/styles/formulas preserved',before['sheets'][name]['cells']==after['sheets'][name]['cells'],cell_count=len(before['sheets'][name]['cells']))
 ck(name+' all hyperlinks preserved',before['sheets'][name]['links']==after['sheets'][name]['links'],hyperlink_count=len(before['sheets'][name]['links']))
base=json.loads((j/'baseline-pointer.json').read_text());base_reg=json.loads((b/base['register']).read_text());new_regp=b/ptr['register'];new_reg=json.loads(new_regp.read_text());ck('Current canonical register hash matches pointer',sha(new_regp.read_bytes())==ptr['register_sha256'])
o1={x['product_id']:x for x in base_reg['options']};o2={x['product_id']:x for x in new_reg['options']};ck('All188 retained options and187active IDs preserved',o1.keys()==o2.keys() and len(o2)==188 and base_reg['active_option_ids']==new_reg['active_option_ids'])
for field in ['name','specifications','master_fields','selling_details','file_id','folder_id','physical_specifications_verified','platform_publication_performed']:
 ck('All188 option '+field+' preserved',all(x.get(field)==o2[k].get(field) for k,x in o1.items()))
a1=json.loads(Path(base_reg['latest_image_coverage_audit']['path']).read_text());a2=json.loads(Path(new_reg['latest_image_coverage_audit']['path']).read_text());c1={x['option_id']:x for x in a1['coverage']};c2={x['option_id']:x for x in a2['coverage']};targets={'BSI-65A93033A200':'id:cnqzTNngPVsAAAAAAAylEw','BSI-4515726BBC18':'id:cnqzTNngPVsAAAAAAAylEw','BSI-207102CFD25C':'id:cnqzTNngPVsAAAAAAAsR7A','BSI-2418C8B43415':'id:cnqzTNngPVsAAAAAAAsH_A'}
for role in ['individual','series']:
 def binding(x):return {'status':x['status'],'file_id':(x.get('reference') or {}).get('file_id'),'folder_id':(x.get('reference') or {}).get('folder_id')}
 ck('All188 '+role+' status/file/actual-parent bindings preserved',all(binding(c1[k][role])==binding(c2[k][role]) for k in c1))
changed=[k for k in c1 if c1[k]['in_situ']!=c2[k]['in_situ']];ck('Exactly four qualified context role changes',set(changed)==set(targets),changed_option_ids=changed)
for oid,fid in targets.items():ck(oid+' correct qualified display source and status',c2[oid]['in_situ']['status']=='Available' and c2[oid]['in_situ']['reference']['file_id']==fid)
for oid in targets:
 role=c2[oid]['in_situ'];reference=role['reference'];ck(oid+' display qualification and evidence limits retained',role['qualified_display_only'] is True and role['explicit_owner_image_role_approval'] is False and role['scene_authenticity_verified'] is False and role['physical_cast_or_size_certified'] is False and reference['whole_original_only'] is True and bool(role['display_qualification']))
counts=a2['counts'];ck('Final required action count40',counts['required_picture_actions']==40);ck('Final context165available/22gaps and17series gaps',counts['in_situ_statuses']=={'Available':165,'No verified image':22} and counts['series_statuses']['No verified image']==17)
brief=json.loads((j/'remaining-photograph-requests-final.json').read_text());held={'BSI-9299D69FEF08','BSI-AF88EAA8EBC0','BSI-04D6E8690F30','BSI-22DA74B2107E','BSI-C87B4CF945C7','BSI-1B20DCA291BB','BSI-67B24409A253','BSI-65520F070145'}
expected_requests={k for k,x in c2.items() if k in new_reg['active_option_ids'] and k not in held and (x['in_situ']['status']=='No verified image' or x['series']['status']=='No verified image')}
ck('Final29-option photograph brief exactly matches published active residual queue',expected_requests=={x['option_id'] for x in brief['requests']} and len(expected_requests)==29)
ck('Final29-option photograph brief retains exact published individual references',all(x['existing_individual_reference']['file_id']==o2[x['option_id']]['file_id'] for x in brief['requests']))
# Build public Artifact API checks on saved formula caches, roles, labels and actual parent IDs.
plan={'workbookPath':str(snapshot),'expectedSha256':sha(data),'reportPath':str(v/'artifact-final-readback.json'),'cells':[]}
def add(sheet,cell,expected,label):plan['cells'].append({'sheet':sheet,'cell':cell,'expected':expected,'label':label})
for sheet,cell,expected,label in [('Master Catalogue','B4',187,'activeoptions'),('Master Catalogue','D4',112,'components'),('Master Catalogue','F4',187,'sixworkingfields'),('Photo Coverage','B4',177,'individualfullviews'),('Photo Coverage','D4',165,'qualifiedcontextreferences'),('Photo Coverage','F4',116,'seriesreferences'),('Missing Pictures','B4',39,'findorcapture'),('Missing Pictures','D4',1,'legacyidentity'),('Missing Pictures','F4',54,'optionalimages'),('Selling Details','B4',187,'sellingrecords'),('Selling Details','D4',186,'workingprices'),('Selling Details','F4',186,'standardleadtime'),('Selling Details','H4',1,'oneweekexception')]:add(sheet,cell,expected,label)
photo=after['sheets']['Photo Coverage']['cells'];rowmap={x['value']:cell[1:] for cell,x in photo.items() if cell.startswith('A') and x['value'].startswith('BSI-')}
for oid,fid in targets.items():
 row=rowmap[oid];ref=c2[oid]['in_situ']['reference'];add('Photo Coverage','F'+row,'Available',oid+' contextstatus');add('Photo Coverage','O'+row,fid,oid+' file');add('Photo Coverage','P'+row,ref['folder_id'],oid+' actualparent');add('Photo Coverage','G'+row,photo['G'+row]['value'],oid+' qualifiedlabel');add('Photo Coverage','M'+row,o1[oid]['file_id'],oid+' originalprimary')
row=rowmap['BSI-3635E3DC3434'];add('Photo Coverage','C'+row,'Available','Pewterindividualalreadyavailable');add('Photo Coverage','F'+row,'No verified image','Pewtercontextstillmissing');add('Photo Coverage','I'+row,'No verified image','Pewterseriesstillmissing');add('Photo Coverage','M'+row,'id:cnqzTNngPVsAAAAAAA6VmA','Pewteracceptedprimary')
(v/'artifact-final-read-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
report={'schema':'boldstone.independent-final-catalogue-readonly-qa.v1','recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_XML_AND_CANONICAL_PRESERVATION_PUBLIC_ARTIFACT_READBACK_PENDING','pointer_sha256':sha(ptrbytes),'workbook':str(source),'workbook_sha256':sha(data),'register':str(new_regp),'register_sha256':sha(new_regp.read_bytes()),'checks':checks,'check_count':len(checks),'sheets':len(after['sheets']),'formulas':len(after['formulas']),'hyperlinks':after['hyperlinks'],'artifact_read_plan':str(v/'artifact-final-read-plan.json'),'workbook_modified_or_exported':False,'native_or_platform_writes':0}
(v/'final-xml-and-canonical-readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'checks':len(checks),'workbook_sha256':sha(data),'artifact_plan_cells':len(plan['cells']),'private_workspace':str(v)}))
