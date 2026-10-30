"""Align the physical audit's recorded scope with the existing 188-option checklist."""
import copy,csv,hashlib,html,json,shutil
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert not(H/'canonical-master-register.json').exists()
p=read(B/'current-master.json');assert p['register_sha256']=='53e6656a589708f2ff8f420a2050d9c8db7e2d6e7baf9d267fd6385aedbfe1cb'
OLD=(B/p['register']).parent;r=read(OLD/'report-verification.json');oldout=Path(r['output_directory']);F=B/'components/parallel-reviews/physical-audit-scope-consistency-20261024/sealed-handoff.json';assert sha(F)=='6862ea9ea8aa3cb98a07ec65282daf405e2e41fe71d22edee563bfeb5c76997e'
finding=read(F)
for f in finding['files']:assert sha(f['path'])==f['sha256']
(H/'inputs').mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
files={'pointer':B/'current-master.json','master_register':B/p['register'],'workbook':B/p['workbook'],'legacy_ledger':OLD/'physical-source-audit.json','current_csv':oldout/'Physical_Source_Audit_752_Field_Groups.csv','physical_input':oldout/'Physical_Verification_Input_188_Options.csv','review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','finding_seal':F}
m={}
for k,f in files.items():
 snap=H/'inputs'/(k+'.before');shutil.copy2(f,snap);m[k]={'path':str(f),'snapshot':str(snap),'sha256':sha(f)}
write(H/'input-manifest.json',m)
for name in ['image-coverage-current.json','current-native-reference-map.json','current-assets.json','photo-review-queue.json','guided-owner-review-state.json','pending-followups.json','original-verification.json','photo-source-review.json','working-entry-owner-provenance-sidecar.json','guided_review.py','specification_review.py','verify_workbook.py']:shutil.copy2(OLD/name,H/name)
g=read(files['master_register']);ledger=read(files['legacy_ledger']);assert len(ledger['options'])==187 and len(ledger['field_rows'])==748
o=next(o for o in g['options']if o['product_id']=='BSI-C3AA3700F7DA');assert o['product_id']not in {x['option_id']for x in ledger['options']}
with files['current_csv'].open(encoding='utf-8-sig',newline='')as f:rows=list(csv.DictReader(f))
with files['physical_input'].open(encoding='utf-8-sig',newline='')as f:inputs=list(csv.DictReader(f))
assert len(rows)==752 and len(inputs)==188
newrows=[row for row in rows if row['option_id']==o['product_id']];assert len(newrows)==4
image={k:o[k]for k in ['file_id','folder_id','image_url','folder_url']};fields=[]
for row in newrows:
 f=row['field'];v=o['master_fields'][f];assert row['working_detail']==v['display']and row['source_assertions']=='0'and row['new_physical_verification']=='False'and v['physical_verification']==0
 fields.append({'option_id':o['product_id'],'name':o['name'],'component_id':o['canonical_component_id'],'field':f,'current_working_detail':v['display'],'recorded_state':v['state'],'recorded_basis':v['basis'],'verification_outcome':'QUALIFIED_ESTIMATE_OR_COMPARATOR; NOT_PHYSICALLY_VERIFIED','physically_verified':False,'new_measurement_or_hardware_evidence':False,'source_assertions':[],'source_assertions_count':0,'working_source_references':copy.deepcopy(v.get('source_references',[])),'requires_object_specific_evidence':row['physical_evidence_needed'],'image_reference':image,'source_scope_limit':'Existing qualified master/checklist projection reviewed; zero independent water-build source assertions and no new physical or hardware evidence. Whole-group image is an owner-approved listing reference only.'})
ledger['options'].append({'option_id':o['product_id'],'name':o['name'],'image_reference':image,'physical_fields':fields,'complete_physical_verification':False});ledger['field_rows'].extend(fields)
summary=copy.deepcopy(ledger['summary']);summary.update(status='ALL_188_ACTIVE_OPTIONS_PHYSICAL_WORKING_FIELDS_REVIEWED_MEASUREMENTS_STILL_REQUIRED',recorded_utc=now(),active_options_reviewed=188,physical_field_groups_reviewed=752,physical_input_rows_checked=188,verification_outcomes=dict(Counter(x['verification_outcome']for x in ledger['field_rows'])),ledger=str(H/'physical-source-audit.json'),input_checklist=str(files['physical_input']),new_physical_verifications=0,accepted_working_fields_changed=0,new_qualified_comparator_field_groups_reviewed=4,new_independent_physical_source_assertions=0)
ledger['summary']=summary;ledger['scope_alignment_provenance']={'legacy_187_option_ledger':m['legacy_ledger'],'existing_188_option_csv':m['current_csv'],'four_new_rows_option_id':o['product_id'],'historical_source_assertions_retained':684,'source_reference_history_unchanged':True,'existing187_records_unchanged':True,'current_navigation_basis':'Use current-master option and native-map references for navigation; original187 recorded image references remain dated evidence.'};write(H/'physical-source-audit.json',ledger)
summary['ledger_sha256']=sha(H/'physical-source-audit.json');summary['review']=str(OUT/'physical-ledger-alignment.html');g['latest_physical_source_audit']=copy.deepcopy(summary)
g['latest_physical_audit_scope_alignment']={'recorded_utc':now(),'previous_scope_options':187,'previous_scope_fields':748,'current_scope_options':188,'current_scope_fields':752,'added_qualified_comparator_fields':4,'new_source_assertions':0,'new_physical_verifications':0,'finding_seal':str(F),'finding_seal_sha256':sha(F)}
write(H/'canonical-master-register.json',g)
esc=lambda v:html.escape(str(v),quote=True)
table=''.join('<tr><th>'+esc(v['field'])+'</th><td>'+esc(v['current_working_detail'])+'</td></tr>'for v in fields)
page='<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Physical specification audit scope</title><style>body{font:17px Arial;line-height:1.5;max-width:960px;margin:40px auto;padding:0 20px;color:#202020}table{border-collapse:collapse;width:100%}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #ddd}th{width:22%}</style></head><body><h1>Physical specification audit scope</h1><p>The structured ledger now covers188 active options and752 physical field groups, matching the existing checklist. The187 earlier records and684 source assertions are preserved. Four existing Moon and Shellwave2 water-build estimates have been added with zero independent water-build assertions and zero new physical verifications.</p><h2>'+esc(o['name'])+'</h2><p><a href="'+esc(o['image_url'])+'">Owner-approved whole-group image</a> · <a href="'+esc(o['folder_url'])+'">Containing folder</a></p><p>Whole-group listing reference. The sale unit remains one panel. The photograph does not verify the water-build material, dimensions, weight, mounting or waterproofing.</p><table>'+table+'</table><p><a href="'+esc(str(oldout/'specifications-to-verify.html'))+'">All188 options and their image/folder links</a></p></body></html>'
pagepath=OUT/'physical-ledger-alignment.html';pagepath.write_text(page)
r['register_sha256']=sha(H/'canonical-master-register.json');r['pages'].append({'path':str(pagepath),'sha256':sha(pagepath),'cards':0});r['recorded_utc']=now();r['metadata_only_alignment']={'workbook_bytes_changed':False,'previous_ledger_scope':[187,748],'current_ledger_scope':[188,752],'new_physical_verifications':0};write(H/'report-verification.json',r)
write(H/'WORK_STATE.json',{'status':'CANDIDATE_METADATA_ONLY','workbook_authoring':False,'new_physical_verifications':0})
print(json.dumps({'status':'READY_FOR_READBACK','register_sha256':sha(H/'canonical-master-register.json'),'ledger_sha256':sha(H/'physical-source-audit.json'),'workbook_sha256':p['workbook_sha256'],'active_options':188,'physical_field_groups':752,'new_independent_source_assertions':0,'new_physical_verifications':0}))
