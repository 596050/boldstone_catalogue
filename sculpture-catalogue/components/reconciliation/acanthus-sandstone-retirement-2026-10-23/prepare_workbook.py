import importlib.util,json,posixpath,re
from pathlib import Path
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v);b=v.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');oid='BSI-C41824131174';oldout=str(Path(read(H/'input-manifest.json')['master_register']['path']).parent).replace('/components/reconciliation/','/outputs/');out=B/'outputs'/H.name;changes={};forms={};links={}
def cell(sn,c,val):
 before=b['values'][sn].get(c,'')
 if before!=val:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':val}
def formula(sn,c,text,expected):forms[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn][c],'formula':text,'expected':expected}
def fcache(sn,c,expected):formula(sn,c,b['formulas'][sn][c],expected)
def reroute(u):
 if not isinstance(u,str):return u
 return u.replace(oldout,str(out)).replace('Current_Individual_Options_188.csv','Current_Individual_Options_187.csv').replace('Physical_Verification_Input_188_Options.csv','Physical_Verification_Input_187_Options.csv').replace('Specification_Verification_Checklist_1128_Fields.csv','Specification_Verification_Checklist_1122_Fields.csv').replace('Separate_Individual_Photographs_Required_1.csv','Separate_Individual_Photographs_Required_0.csv')
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rs[x.get('{'+v.R+'}id')];links[(sn,c)]={'sheet':sn,'cell':c,'label':b['values'][sn].get(c,''),'target':reroute(u)}
reason='Owner23October2026: Sandstone does not exist anymore. Retired from the current catalogue; no photo, measurement, offer or draft-creation task. Identity, source records and prior specifications retained as history.'
for c,val in {'A3':'187 active individual options across112 component identities;188 historical option rows retained, including one owner-retired Acanthus Sandstone finish.','A4':'Active individual option records','A6':'Counts exclude retired finishes and unbounded custom requests. Acanthus One Leaf Left — Sandstone is retained for history only. All current Frozen Fish stay70cm high ×15cm wide.','I16':'Retired — historical price only','J16':'Retired — no longer exists','L16':'Retired','V16':reason}.items():cell('Master Catalogue',c,val)
formula('Master Catalogue','B4','=COUNTIFS(A10:A197,"<>",L10:L197,"<>Retired")',187);fcache('Master Catalogue','F4',187);fcache('Master Catalogue','K16',0)
for row in range(46,52):
 cell('Specifications','E'+str(row),'Retired');old=b['formulas']['Specifications']['Q'+str(row)];formula('Specifications','Q'+str(row),old.replace('AND(',f'AND(E{row}<>"Retired",',1),0)
for c in ['C16','F16','I16']:cell('Photo Coverage',c,'Retired / not applicable')
cell('Photo Coverage','L16',reason);cell('Photo Coverage','A3','187 active options;177 complete individual references and10 technical gaps, including9 owner-accepted reference exceptions plus one deferred Frozen Fish identity. Current gaps:49 in situ and17 series. Retired Sandstone requires no photographs.')
formula('Photo Coverage','B5','=COUNTIFS(A10:A197,"<>",C10:C197,"<>Retired / not applicable")-B4',10)
for i,x in enumerate(a['missing_pictures'],10):
 if x['option_id']==oid:
  for col,val in {'F':'No action — owner-retired option.','L':reason,'M':'Sandstone does not exist anymore','N':'Retired / not applicable'}.items():cell('Missing Pictures',col+str(i),val)
cell('Missing Pictures','A3','208 retained action rows:67 required open actions,54 optional,84 resolved and3 retired. Current gaps:one deferred individual/identity entry,49 in situ and17 series. No active Sandstone tasks.')
formula('Missing Pictures','B4','=COUNTIFS(E10:E217,"Find / capture",N10:N217,"Open")',66)
componentrow=next(int(c[1:])for c,z in b['values']['Components'].items()if re.fullmatch('A[0-9]+',c)and z=='BC-AC-ONE');component=next(x for x in g['components']if x['component_id']=='BC-AC-ONE');cell('Components','D'+str(componentrow),'\n'.join(component['option_names']));cell('Components','E'+str(componentrow),'Two current finish options. Sandstone retired by owner23October2026; identity and historical names retained.')
for c,val in {'C16':'Retired','Q16':'None — owner-retired; do not create an offer.','V16':reason,'W16':'Owner: Sandstone does not exist anymore.'}.items():cell('Listing Resolution',c,val)
formula('Listing Resolution','D5',b['formulas']['Listing Resolution']['D5']+'-COUNTIFS(C10:C197,"Retired")',103)
for c,val in {'C16':'Retired option — historical associations retained','L16':'None — owner-retired; no platform creation task.','V16':'Owner: Sandstone does not exist anymore.'}.items():cell('Listing Reconciliation',c,val)
for c,val in {'C12':'Retired option — historical issue','D12':'No action — do not create a listing for the retired finish.','N12':reason,'O12':'Sandstone does not exist anymore','P12':'Retired / not applicable'}.items():cell('Listing Issues',c,val)
formula('Listing Issues','B4','=COUNTIFS(P10:P174,"<>Resolved",P10:P174,"<>Retired / not applicable")',164)
for c,val in {'C12':'Retired option','N12':'None — owner-retired.','O12':'Do not create or activate this retired draft.','P12':reason,'Q12':'Retired — do not create','R12':'Sandstone does not exist anymore','A3':'100 active individual-option drafts and3 custom/unlisted Wall Circle scopes. One owner-retired Sandstone draft remains for history only. No platform listings created.'}.items():cell('Draft Listings',c,val)
fcache('Draft Listings','B4',100)
for c,val in {'A3':'187 active selling-detail records; one retired Sandstone history row retained. Accepted working prices and owner policies for other options are unchanged.','C16':'Retired — historical price only','D16':'Retired — no longer exists','E16':'Retired','G16':'Retired','J16':reason,'P16':'Retired — no current offer','Q16':reason}.items():cell('Selling Details',c,val)
formula('Selling Details','B4','=COUNTIFS(A10:A197,"<>",E10:E197,"<>Retired")',187);fcache('Selling Details','D4',186);fcache('Selling Details','F4',186)
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
previews=[['Master Catalogue','I16:M16','01-retired-option'],['Master Catalogue','A4:H4','02-active-counts'],['Photo Coverage','A4:F5','03-photo-counts'],['Missing Pictures','L13:N13','04-retired-photo-action'],['Specifications','C46:I46','05-retained-specification'],['Selling Details','C16:G16','06-no-current-offer'],['Draft Listings','N12:R12','07-retired-draft']]
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[],'table_appends':[],'new_sheets':{},'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':x['sheet'],'cell':x['cell'],'value':x['expected']}for x in forms.values()],'baseline_ranges':[['Master Catalogue','I16:M16','baseline-option'],['Master Catalogue','A4:H4','baseline-counts']],'preview_ranges':previews}
(H/'workbook-edit-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n');(H/'expected-edit.json').write_text(json.dumps({'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]},ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'RETIREMENT_PLAN_READY','changed_cells':len(changes),'formula_cache_or_rule_entries':len(forms),'links':len(links)}))
