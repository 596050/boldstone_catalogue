"""Seal the verified standalone workbook after model review of all previews."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json

W=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
v=read(W/'validation.json');manifest=read(W/'input-manifest.json')
assert v['status']=='PASS_COMPLETE_SAVED_WORKBOOK_AND_SOURCE_RECONCILIATION'
target=Path(v['output']);assert sha(target)==v['sha256']
dates=read(W/'timestamp-text-receipt.json');links=read(W/'native-hyperlink-receipt.json')
assert dates['sha256']==v['sha256'] and dates['before_sha256']==links['saved_sha256']
assert links['hyperlinks']==v['native_hyperlinks']==43121
for item in manifest['inputs']:assert sha(item['path'])==item['sha256']
previews=read(W/'preview-manifest.json')+read(W/'saved-file-reopen-receipt.json')['previews']
assert len(previews)==28 and len({r['sheet'] for r in previews})==21
for r in previews:r['sha256']=sha(r['path'])
write(W/'visual-verification.json',{
 'status':'PASS_ALL_21_TABS_VISUALLY_REVIEWED',
 'reviewed_utc':datetime.now(timezone.utc).isoformat(),
 'workbook_sha256':v['sha256'],'previews':previews,
 'observations':[
  'Titles, identifiers, headers, statuses and link labels are readable in the bounded previews of every tab.',
  'Products specification and selling-detail columns retain labelled claims and estimates, GBP values and one-to-two-week lead times.',
  'Six historical source associations visibly have unselected status and historical-context wording.',
  'Overview shows 268 retained associations with explicit 262 current plus six historical explanation.',
  'Saved workbook reopened successfully; original UTC timestamp text is readable in both affected inventories.',
  'Raw exports retain full HTML and long text in cells; the compact raw view is intentionally expanded via the formula bar when needed.'
 ],
 'native_application_validation':'Not opened in Microsoft Excel; independently validated saved OOXML, recalculation in Artifact Tool, and read-only Artifact Tool reopen.'})
plan=read(W/'WORK_PLAN.json')
for step in plan['steps']:step['status']='complete'
plan['completed_utc']=datetime.now(timezone.utc).isoformat();plan['deliverable']=str(target)
write(W/'WORK_PLAN.json',plan)
inspection=target.with_name(target.name+'.inspect.ndjson')
if inspection.exists():inspection.replace(W/'final-export-inspection.ndjson')
data=read(W/'workbook-data.json')
hist=[r for t in data['tabs'] if t['name']=='Catalogue source links' for r in t['rows'] if r[7]=='Historical component context; not selected in current individual plan']
history_source=next(r for r in manifest['inputs'] if Path(r['path']).name=='complete-image-platform-register.sqlite')
receipt_files=['input-manifest.json','preparation-validation.json','authoring-receipt.json','native-hyperlink-receipt.json','timestamp-text-receipt.json','validation.json','saved-file-reopen-receipt.json','visual-verification.json','WORK_PLAN.json']
seal={
 'status':'COMPLETE_STANDALONE_SOURCE_CONSOLIDATION_WITH_EXPLICIT_MATCH_LIMITS',
 'sealed_utc':datetime.now(timezone.utc).isoformat(),
 'deliverable':{'path':str(target),'sha256':v['sha256'],'bytes':target.stat().st_size,'sheets':21},
 'counts':v['counts'],'validation_checks_passed':v['checks_passed'],
 'native_hyperlinks':v['native_hyperlinks'],'all_source_and_master_input_hashes_unchanged':True,
 'source_associations':{'latest_audit_rows':262,'historical_only_rows':6,'retained_union_rows':268,
    'historical_source':history_source,
    'historical_pairs':[{'product_id':r[1],'offer_ref':r[3],'original_relationship':r[14],'selected_for_individual_plan':False} for r in hist],
    'qualification':'Historical retention is not reapproval; absence from the latest audit is not rejection or deletion evidence.'},
 'scope':{
    'catalogue':'All 188 active options and six retired specification fields; qualifiers preserved.',
    'squarespace':'All 208 products and 376 variants from the available Physical export; 80 previously reviewed and 128 additional source products.',
    'shopify':'All 136 products and 160 variants across the available local export; 38-product wall subset remains labelled.',
    'dropbox':'All 6360 current files and 442 folders from the saved BOLDSTONE MASTER Wall Sculptures snapshot, plus 330 supplementary or historical file references.',
    'source_matching':'All 140 exact raw-SKU pairs are source-row evidence only; no new exact sculpture identity is asserted.'},
 'unresolved_records_retained':True,'new_identity_approvals':0,'canonical_writes':0,'platform_writes':0,
 'receipts':[{'path':str(W/name),'sha256':sha(W/name)} for name in receipt_files],
 'builders':[{'path':str(W/name),'sha256':sha(W/name)} for name in ['prepare.py','author.mjs','attach_links.py','restore_text_timestamps.py','verify.py','inspect_final.mjs','seal.py']]
}
write(W/'sealed-handoff.json',seal)
assert sha(target)==v['sha256']
print(json.dumps({'status':seal['status'],'output':str(target),'sha256':v['sha256'],'seal':str(W/'sealed-handoff.json'),'seal_sha256':sha(W/'sealed-handoff.json'),'checks_passed':v['checks_passed']},indent=2))
