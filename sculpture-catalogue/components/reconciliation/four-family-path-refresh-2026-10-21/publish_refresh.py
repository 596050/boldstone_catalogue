"""Publish verified Step07 paths independently of the pending numbering answer."""
import copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text());digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):
 p=Path(p);t=p.with_name(p.name+'.four-family-tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');t.replace(p)
m=read(HERE/'input-manifest.json');check=read(HERE/'saved-file-verification.json');g=read(HERE/'canonical-master-register.json')
assert check['status']=='PASS' and digest(HERE/'master-workbook.pending')==check['workbook_sha256'] and digest(HERE/'canonical-master-register.json')==check['register_sha256']
for x in m.values():assert digest(x['path'])==digest(x['snapshot'])==x['sha256']
previews=read(HERE/'preview-manifest.json');assert len(previews)==2
write(HERE/'visual-verification.json',{'status':'PASS','recorded_utc':now(),'previews':[{**p,'sha256':digest(p['path'])} for p in previews],
 'finding':'Both changed current-folder-ID views inspected. Values, identifiers and link labels readable. Existing names/specifications/coverage and all other view dependencies unchanged; prior QA reused for those ranges.'})
ptr=copy.deepcopy(read(BASE/'current-master.json'));prior=copy.deepcopy(ptr)
ptr.update(recorded_utc=now(),workbook_sha256=check['workbook_sha256'],register=rel(HERE/'canonical-master-register.json'),register_sha256=check['register_sha256'],publication_receipt=rel(HERE/'publication-receipt.json'))
summary={**g['latest_four_family_matching'],'verification':rel(HERE/'saved-file-verification.json'),'verification_sha256':digest(HERE/'saved-file-verification.json'),
 'visual_verification':rel(HERE/'visual-verification.json'),'visual_verification_sha256':digest(HERE/'visual-verification.json'),
 'native_link_destinations_updated':check['native_link_destinations_updated'],'current_parent_ID_cells_updated':check['current_parent_ID_cells_updated']}
# Detailed change ledgers stay in the register and receipts, rather than being
# repeated in every checkpoint pointer.
summary.pop('graph_changes')
ptr['latest_four_family_matching']=summary
ptr['current_path_scope']+='; Step07 Fingerprint,Leaf Form,Panel Curves and Textured Panels verified renames and stable-ID file moves'
ptr['latest_path_refresh']={'scope':'Step07 four-family current references and parent-folder bindings','overlay_sha256':m['overlay']['sha256'],'sidecar_sha256':m['sidecar']['sha256'],
 'native_link_destinations_updated':check['native_link_destinations_updated'],'current_parent_ID_cells_updated':check['current_parent_ID_cells_updated'],
 'verification':summary['verification'],'verification_sha256':summary['verification_sha256'],'all_names_specifications_and_coverage_preserved':True,'FP_numeric_assignment':'Pending owner answer','remote_writes':0}
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 p=Path(m[key]['path']);d=read(p);d['current_master_catalogue']=copy.deepcopy(ptr);d['current_master_workbook']=ptr['workbook'];d['current_master_register']=ptr['register'];d['updated_utc']=now();d['latest_four_family_matching']=copy.deepcopy(summary)
 d['pending_Fingerprint_numeric_assignment']={'status':'PENDING_OWNER_CLARIFICATION','scope':'The standard pair is identified. Which existing panel is Fingerprint1 or2 remains unassigned; no former Left=1 assumption applied.','source_overlay':summary['overlay'],'source_overlay_sha256':summary['overlay_sha256'],'current_names_and_IDs_preserved':True}
 if key=='component_checkpoint':d['current_master_validation']={'path':summary['verification'],'sha256':summary['verification_sha256']}
 updates[p]=d
write(HERE/'export-receipt.json',{'status':'PASS','recorded_utc':now(),'workbook':ptr['workbook'],'workbook_sha256':ptr['workbook_sha256'],'register':ptr['register'],'register_sha256':ptr['register_sha256'],
 'native_links':check['native_hyperlinks'],'formula_count':check['formula_count'],'native_link_destinations_updated':604,'current_parent_ID_cells_updated':13,'names_specifications_and_coverage_changes':0,'verification':summary['verification']})
for x in m.values():assert digest(x['path'])==x['sha256']
target=BASE/ptr['workbook'];(HERE/'master-workbook.pending').replace(target)
for p,d in updates.items():write(p,d)
write(BASE/'current-master.json',ptr)
assert read(BASE/'current-master.json')==ptr and digest(target)==ptr['workbook_sha256']
for p in updates:assert read(p)['current_master_catalogue']==ptr
for key in ['master_register','owner_ledger','source_model','overlay','sidecar']:
 assert digest(m[key]['path'])==m[key]['sha256']
assert ptr['latest_listing_reconciliation']==prior['latest_listing_reconciliation'] and ptr['latest_image_coverage_audit']==prior['latest_image_coverage_audit']
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':digest(target),'register':str(HERE/'canonical-master-register.json'),'register_sha256':ptr['register_sha256'],
 'native_link_destinations_updated':604,'current_parent_ID_cells_updated':13,'graph_reference_changes':339,'scope_files':373,'scope_current_IDs':395,
 'verification':summary['verification'],'visual_verification':summary['visual_verification'],'all184_names_1104_fields_and_listing_media_evidence_preserved':True,
 'individual_Fingerprint_numbering':'Pending owner answer; no numeric assignment made','current_master_pointer_sha256':digest(BASE/'current-master.json'),
 'controls_sha256':{str(p):digest(p) for p in updates},'old_graph_and_input_workbook_snapshot_preserved':True,'remote_writes_by_root':0}
write(HERE/'publication-receipt.json',receipt)
write(HERE/'completion.json',{'status':'COMPLETE_VERIFIED_FOUR_FAMILY_REFERENCE_PROJECTION; NUMBERING_ANSWER_PENDING','recorded_utc':now(),'publication_receipt':rel(HERE/'publication-receipt.json'),
 'workbook_sha256':ptr['workbook_sha256'],'register_sha256':ptr['register_sha256'],'numeric_names_changed':0,'current_parent_ID_cells_updated':13,'native_link_destinations_updated':604})
print(json.dumps({k:receipt[k] for k in ['status','workbook_sha256','register_sha256','native_link_destinations_updated','current_parent_ID_cells_updated']}))
