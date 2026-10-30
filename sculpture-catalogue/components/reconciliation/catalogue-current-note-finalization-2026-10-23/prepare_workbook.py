"""Plan scoped notes, one optional requirement, and current report navigation."""
import importlib.util,json,posixpath
from pathlib import Path
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('reader',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v);w=v.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');proj=read(H/'projection-index.json');OLD=proj['old_output'];opts={x['product_id']:x for x in g['options']};coverage={x['option_id']:x for x in a['coverage']};changes={};links={}
def setcell(sn,c,value):
 assert c not in w['formulas'][sn]
 if w['values'][sn].get(c,'')!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':w['values'][sn].get(c,''),'value':value}
def link(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rr[x.get('{'+v.R+'}id')];links[(sn,c)]={'sheet':sn,'cell':c,'label':w['values'][sn].get(c,''),'target':u.replace(OLD,str(OUT))}
rows={x['product_id']:i for i,x in enumerate(g['options'],10)}
for oid in proj['b_option_ids']+proj['a_option_ids']:
 o=opts[oid];row=rows[oid];note=o.get('current_reference_note');text=note['text']if note else o['context_description'];role=note['role']if note else'In situ'
 old=w['values']['Photo Coverage'].get('L'+str(row),'');setcell('Photo Coverage','L'+str(row),'23 October current '+role+' clarification: '+text+'\nEarlier recorded role notes retained: '+old)
 old=w['values']['Master Catalogue'].get('V'+str(row),'');setcell('Master Catalogue','V'+str(row),old+'\n23 October current '+role+' reference: '+text)
oid=proj['optional_option_id'];row=rows[oid];c=coverage[oid];policy=c['series']['basis']
setcell('Photo Coverage','I'+str(row),c['series']['status']);setcell('Photo Coverage','V'+str(row),'Optional / no fixed set — owner-approved for this option only');setcell('Photo Coverage','U'+str(row),c['owner_review']);setcell('Photo Coverage','L'+str(row),'23 October current Series policy: '+policy+'\nEarlier role notes retained as history: '+w['values']['Photo Coverage']['L'+str(row)])
old=w['values']['Master Catalogue']['V'+str(row)];setcell('Master Catalogue','V'+str(row),'23 October current Series policy: '+policy+'\nEarlier evidence notes retained as history: '+old)
tr=next(i for i,t in enumerate(a['missing_pictures'],10)if t['option_id']==oid and t['role']=='Series');t=a['missing_pictures'][tr-10]
for col,key in [('E','action_type'),('F','action'),('L','qualification'),('M','owner_response'),('N','status')]:setcell('Missing Pictures',col+str(tr),t[key])
link('Master Catalogue','A3','187 active options;112 working component identities. Seven current source notes corrected; all Dropbox IDs and specifications preserved.22 context requests held;15 Series active, one held. One Series requirement is owner-optional.',str(OUT/'current-note-corrections.html'))
link('Photo Coverage','A3','177 complete individual,165 context and116 Series references.22 missing context roles held.16 required Series gaps:15 active and one held.55 Series optional. Frozen Fish legacy identity remains deferred.',str(OUT/'remaining-photograph-requests.html'))
link('Missing Pictures','A3','39 required diagnostic actions:22 held context,16 Series (15 active, one held), and one deferred individual identity. One owner-optional Series requirement removed; no new photograph verified.',str(OUT/'index.html'))
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):10,('Photo Coverage','D4'):165,('Photo Coverage','F4'):116,('Missing Pictures','B4'):38,('Missing Pictures','D4'):1,('Missing Pictures','F4'):55,('Master Catalogue','H4'):186,('Master Catalogue','B4'):187,('Master Catalogue','F4'):187}
plan={'cell_changes':list(changes.values()),'formula_changes':[{'sheet':sn,'cell':c,'before':w['formulas'][sn][c],'formula':w['formulas'][sn][c],'expected':value}for(sn,c),value in expected.items()],'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[],'table_appends':[],'new_sheets':{},'target_rows':[],'optional_action_row':tr,'expected_original_sheet_count':len(w['sheets']),'expected_formula_count':sum(map(len,w['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':value}for(sn,c),value in expected.items()],'baseline_ranges':[['Photo Coverage','I'+str(row)+':L'+str(row),'baseline-optional-role'],['Missing Pictures','E'+str(tr)+':N'+str(tr),'baseline-optional-task']],'preview_ranges':[['Photo Coverage','I'+str(row)+':L'+str(row),'01-optional-series-role'],['Missing Pictures','L'+str(tr)+':N'+str(tr),'02-optional-series-action'],['Photo Coverage','L33:L36','03-current-context-notes'],['Photo Coverage','L73:L73','04-current-egyptian-reference'],['Photo Coverage','L28:L28','05-current-bone-primary-note'],['Missing Pictures','A2:N5','06-action-summary']],'supplemental_preview_ranges':[['Photo Coverage','L191:L191','07-azure-room-display-note'],['Master Catalogue','A1:Y3','08-master-header']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
builder=(H/'author_workbook.mjs').read_text();start=builder.index('for(const z of p.target_rows.slice(0,2))');end=builder.index('wb.recalculate();',start)
builder=builder[:start]+"const optionalTask=wb.worksheets.getItem('Missing Pictures').getRange('N'+p.optional_action_row);\noptionalTask.values=[['Open']];eq(value('Missing Pictures','B4'),39,'Reopening optional Series responds in required summary');eq(value('Missing Pictures','F4'),54,'Reopening removes one optional action');\noptionalTask.values=[['Optional']];eq(value('Missing Pictures','B4'),38,'Restored owner policy removes mandatory action');eq(value('Missing Pictures','F4'),55,'Restored optional action count');\n"+builder[end:]
builder=builder.replace('RAKED_MOONPHASE_WORKSHOP_NAVIGATION_MASTER_EXPORTED','CURRENT_NOTE_FINALIZATION_MASTER_EXPORTED').replace('Same-ID arrangement/workshop links refreshed; one Series hold and exact-member Bronze exclusion recorded; all working fields and context holds retained','Seven current source notes and one exact owner Series policy imported; IDs, physical values, existing role bindings and all holds retained')
(H/'author_workbook.mjs').write_text(builder)
print(json.dumps({'status':'PLAN_READY','cell_changes':len(changes),'native_hyperlinks':len(links),'new_native_link_changes':0,'optional_row':row,'optional_action_row':tr,'notes_rows':[rows[x]for x in proj['b_option_ids']+proj['a_option_ids']]}))
