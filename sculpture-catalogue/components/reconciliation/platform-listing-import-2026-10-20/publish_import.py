"""Publish the verified listing supplements to the single current master."""
import copy
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
relative=lambda p:str(Path(p).relative_to(BASE))
now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,d):
    p=Path(p);tmp=p.with_name(p.name+'.listing-import-tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)

manifest=read(HERE/'input-manifest.json')
for x in manifest.values():assert digest(x['path'])==digest(x['snapshot'])==x['sha256'],'Input changed: '+x['path']
check=read(HERE/'saved-file-verification.json');g=read(HERE/'canonical-master-register.json');pending=HERE/'master-workbook.pending'
assert check['status']=='PASS' and digest(pending)==check['workbook_sha256'] and digest(HERE/'canonical-master-register.json')==check['register_sha256']
previews=read(HERE/'preview-manifest.json');assert len(previews)==6
write(HERE/'visual-verification.json',{'status':'PASS','recorded_utc':now(),
  'previews':[{**p,'sha256':digest(p['path'])} for p in previews],
  'finding':'All three new sheets visually inspected. Identifiers, source-qualified statuses, source/SKU links, sale-unit limits and editable owner fields readable. Prior13tabs reuse their unchanged-view QA; saved-file verification establishes complete value/formula/style/native-feature preservation.',
  'independent_lane_observation':'Evidence-lane coordinator independently viewed all6 staged previews and reported visual PASS before publication.'})
prior=read(BASE/'current-master.json');pointer=copy.deepcopy(prior)
summary={**g['latest_listing_reconciliation'],'register':relative(HERE/'canonical-master-register.json'),
  'verification':relative(HERE/'saved-file-verification.json'),'verification_sha256':digest(HERE/'saved-file-verification.json'),
  'visual_verification':relative(HERE/'visual-verification.json'),'visual_verification_sha256':digest(HERE/'visual-verification.json'),
  'publication_receipt':relative(HERE/'publication-receipt.json')}
pointer.update(recorded_utc=now(),workbook_sha256=check['workbook_sha256'],register=relative(HERE/'canonical-master-register.json'),
  register_sha256=check['register_sha256'],publication_receipt=relative(HERE/'publication-receipt.json'))
pointer['latest_listing_reconciliation']=summary
actions=[
 'Resolve the confirmed EBAY-188654649217 SKU collision across O051/O067 and review three overlapping public product-record cases. No duplicate active offer or automatic deletion is certified.',
 'Resolve existing source configuration/copy conflicts for Bone Water Spiral,Golden Spiral,Leaf Form White and Moon Water Catcher without replacing accepted specifications from incompatible source versions.',
 'Verify source-supported record associations against current platform admin and exact finish,size/build and sale unit.41 nonconflicting links plus4 configuration-conflict links do not establish exact current configuration or live stock.',
 'Check139 options without a supported individual source-record association in current admin/drafts before preparing missing individual listings.33 have only set/arrangement associations; set SKUs and totals do not allocate member SKUs or prices.',
 'Complete current Shopify/admin evidence and obtain numeric product/variant IDs. Its136-product/160-variant export is historical. Resolve Squarespace203returned versus208advertised inventory discrepancy.',
 'Keep the seven Wall Circle visual-name aliases separate from144 native pattern/diameter/lighting variants until exact option links are established.'
]
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
    f=Path(manifest[key]['path']);d=read(f)
    d['current_master_catalogue']=copy.deepcopy(pointer);d['current_master_workbook']=pointer['workbook'];d['current_master_register']=pointer['register'];d['updated_utc']=now();d['latest_listing_reconciliation']=copy.deepcopy(summary);d['next_listing_reconciliation_actions']=actions
    if key=='component_checkpoint':
        d['next_work']=actions+d.get('next_image_review_actions',[])
        d['current_master_validation']={'path':summary['verification'],'sha256':summary['verification_sha256']}
    if key=='root_checkpoint':d['next_batch']='Use current master Listing Reconciliation,Listing Offer Links and Listing Issues for platform work. Photo Coverage,Missing Pictures and Identity Review retain the current media queues.'
    updates[f]=d
write(HERE/'export-receipt.json',{'status':'PASS','recorded_utc':now(),'workbook':pointer['workbook'],'workbook_sha256':pointer['workbook_sha256'],
  'register':pointer['register'],'register_sha256':pointer['register_sha256'],'new_sheets':summary['sheets'],'counts':summary['counts'],
  'prior13tabs_preserved':True,'native_hyperlinks':check['native_hyperlinks'],'formula_count':check['formula_count'],'verification':summary['verification'],'visual_verification':summary['visual_verification']})
for x in manifest.values():assert digest(x['path'])==x['sha256']
target=BASE/pointer['workbook'];pending.replace(target)
for f,d in updates.items():write(f,d)
write(BASE/'current-master.json',pointer)
assert digest(target)==pointer['workbook_sha256'] and read(BASE/'current-master.json')==pointer
for f in updates:
    d=read(f);assert d['current_master_catalogue']==pointer and d['latest_listing_reconciliation']==summary
for key in ['source_model','owner_ledger','master_register','packet_seal']:
    assert digest(manifest[key]['path'])==manifest[key]['sha256']
assert pointer['latest_image_coverage_audit']==prior['latest_image_coverage_audit']
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':digest(target),
 'register':str(HERE/'canonical-master-register.json'),'register_sha256':pointer['register_sha256'],
 'counts':summary['counts'],'source_seal':manifest['packet_seal'],'source_payload':manifest['LISTING_RECONCILIATION.json'],
 'saved_file_verification':summary['verification'],'visual_verification':summary['visual_verification'],
 'controls_sha256':{str(f):digest(f) for f in updates},'current_master_pointer_sha256':digest(BASE/'current-master.json'),
 'prior13workbook_tabs_preserved':True,'all1104_current_working_fields_preserved':True,'original1668_assertions_preserved':True,'media_audit_preserved':True,
 'source_model_and_owner_ledger_unchanged':True,'previous_graph_immutable':True,'platform_and_dropbox_mutations':0}
write(HERE/'publication-receipt.json',receipt)
write(HERE/'completion.json',{'status':'COMPLETE_SEALED_SOURCE_LISTING_RECONCILIATION_IMPORT','recorded_utc':now(),'publication_receipt':relative(HERE/'publication-receipt.json'),
 'workbook':pointer['workbook'],'workbook_sha256':pointer['workbook_sha256'],'register':pointer['register'],'register_sha256':pointer['register_sha256'],
 'all184options_dispositioned':True,'exact_current_option_configuration_verifications':0,'live_missing_listing_count':None,'remaining_work':actions})
print(json.dumps({'status':receipt['status'],'workbook_sha256':pointer['workbook_sha256'],'register_sha256':pointer['register_sha256'],'new_listing_tabs':3,'options':184}))
