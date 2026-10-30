"""Publish the verified current master and preserve checkpoint history."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
relative=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):
    p=Path(p);tmp=p.with_name(p.name+'.image-audit-tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)

manifest=read(HERE/'input-manifest.json')
for x in manifest.values():assert digest(x['path'])==digest(x['snapshot'])==x['sha256'],'Source/control changed before publication: '+x['path']
audit=read(HERE/'image-coverage-audit.json');g=read(HERE/'canonical-master-register.json');check=read(HERE/'saved-file-verification.json')
pending=HERE/'master-workbook.pending'
assert check['status']=='PASS'
assert digest(pending)==check['workbook_sha256']
assert digest(HERE/'canonical-master-register.json')==check['register_sha256']
assert digest(HERE/'image-coverage-audit.json')==check['audit_sha256']
previews=read(HERE/'preview-manifest.json')
assert len(previews)==11 and all(Path(x['path']).is_file() for x in previews)
visual={'status':'PASS','recorded_utc':now(),'reviewed_previews':[{**p,'sha256':digest(p['path'])} for p in previews],
        'findings':'All four new tabs and affected original reference views inspected. Headings, counts, hyperlinks, stable IDs, qualifiers and editable owner fields are readable. Original unrelated views reuse the prior unchanged-content visual QA.',
        'saved_native_feature_verification':relative(HERE/'saved-file-verification.json')}
write(HERE/'visual-verification.json',visual)
prior=read(BASE/'current-master.json');pointer=copy.deepcopy(prior)
summary={'status':'COMPLETE_BOUNDED_EVIDENCE_AUDIT','recorded_utc':now(),'audit':relative(HERE/'image-coverage-audit.json'),
         'audit_sha256':digest(HERE/'image-coverage-audit.json'),'counts':audit['counts'],'coverage_sheet':'Photo Coverage','actions_sheet':'Missing Pictures',
         'identity_sheet':'Identity Review','native_pattern_sheet':'Wall Circle Sources','source_scope':audit['method'],'identity_guard':audit['identity_guard'],
         'verification':relative(HERE/'saved-file-verification.json'),'verification_sha256':digest(HERE/'saved-file-verification.json'),
         'visual_verification':relative(HERE/'visual-verification.json'),'visual_verification_sha256':digest(HERE/'visual-verification.json')}
pointer.update(recorded_utc=now(),workbook_sha256=check['workbook_sha256'],register=relative(HERE/'canonical-master-register.json'),
               register_sha256=check['register_sha256'],publication_receipt=relative(HERE/'publication-receipt.json'))
pointer['latest_image_coverage_audit']=summary
pointer['current_path_scope']+='; completed Chelsea/Moon Ripple consolidation and latest same-ID Moon Fishwave folder-name readback'
pointer['latest_path_refresh']={'scope':'Current native references projected through fresh root inventory and completed Step05 overlay; later same-ID Moon Fishwave folder name observed',
   'verification':relative(HERE/'saved-file-verification.json'),'verification_sha256':digest(HERE/'saved-file-verification.json'),
   'overlay_sha256':'aa6e04c96d93820ee0d83aa889d3c98d7305963fd396a251255d6d066d01e156','remote_writes':0,'identity_and_specification_values_preserved':True}
policy={'schema':'boldstone.group-photograph-review-policy.v2','recorded_utc':now(),
   'owner_instruction_exact':'Continue with these: 1. Resolve image and identity gaps. Start with Frozen Fish Long’s missing exact photograph, Cup Ring’s missing isolated photograph, Wall Circle’s variant identities, and components shown only in groups. 2. Complete photograph coverage. Record individual, in situ and series images for each option, producing a precise missing-picture list.',
   'policy':'Resume visual comparison and candidate component-position mapping for group-only sources. Preserve existing approved identities. Unbound photographic positions stay outside the 184 current sale options until their exact identity, finish, size/build and sale unit are established.',
   'supersedes_for_current_task':'Earlier prospective deferral of group component identification. Original owner instructions and prior dispositions remain preserved as history.',
   'new_owner_name_or_specification_approval_recorded':False,'identity_review':summary['identity_sheet'],'audit':summary['audit']}
next_actions=[
 'Confirm Frozen Fish Long geometry relationship and locate its exact 100 × 22 cm photograph; current related White solo image is unbound to Long.',
 'Find or photograph the complete White Cup Ring alone; its full form is currently bound only in a White pair.',
 'Check four strong Wall Circle pattern-alias candidates and resolve the three remaining circular visual-name aliases without assigning diameter, lighting or exact SKU from appearance.',
 'Use Identity Review for unbound group positions and repeated/rotated designs. Candidate positions create no additional component count.',
 'Use Missing Pictures: 27 individual-view actions,66 room/garden views with no verified image,28 room/garden candidate checks,27 series views with no verified image and10 series candidate checks.53 family views are optional.',
 'Verify actual component measurements/material/hardware and exact current platform-offer links separately from working specifications and image-role coverage.'
]
updates={};controls_before={}
for i,f in enumerate(['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json'],1):
    source=BASE/f;data=read(source);snapshot=HERE/'inputs'/f'publication-control-{i}.before';snapshot.write_bytes(source.read_bytes());controls_before[f]={'path':str(source),'snapshot':str(snapshot),'sha256':digest(source)}
    data['current_master_catalogue']=copy.deepcopy(pointer);data['current_master_workbook']=pointer['workbook'];data['current_master_register']=pointer['register'];data['latest_image_coverage_audit']=copy.deepcopy(summary);data['updated_utc']=now()
    if f!='checkpoint.json':
        data['current_group_photo_review_policy']=copy.deepcopy(policy)
        if isinstance(data.get('group_photo_review_policy'),dict):data['group_photo_review_policy']['superseded_for_current_image_task_by']='current_group_photo_review_policy'
        data['next_image_review_actions']=next_actions
    if f=='components/checkpoint.json':
        data['next_work']=next_actions
        data['current_master_validation']={'path':summary['verification'],'sha256':summary['verification_sha256']}
    if f=='checkpoint.json':data['next_batch']='Use the current master Photo Coverage, Missing Pictures and Identity Review tabs; remaining image gaps and exact platform/specification evidence retain their separate scopes.'
    updates[f]=data
write(HERE/'publication-control-inputs.json',controls_before)
write(HERE/'export-receipt.json',{'status':'PASS','recorded_utc':now(),'workbook':pointer['workbook'],'workbook_sha256':check['workbook_sha256'],
      'register':pointer['register'],'register_sha256':pointer['register_sha256'],'new_sheets':['Photo Coverage','Missing Pictures','Identity Review','Wall Circle Sources'],
      'counts':audit['counts'],'native_hyperlinks':check['native_hyperlinks'],'formula_count':check['formula_count'],'saved_file_verification':summary['verification'],'visual_verification':summary['visual_verification']})
# Gate again immediately before replacing current controls. All mutation is local.
for x in manifest.values():assert digest(x['path'])==x['sha256']
for x in controls_before.values():assert digest(x['path'])==x['sha256']
target=BASE/pointer['workbook'];pending.replace(target)
for f,data in updates.items():write(BASE/f,data)
write(BASE/'current-master.json',pointer)
assert digest(target)==pointer['workbook_sha256']
assert read(BASE/'current-master.json')==pointer
for f in updates:
    d=read(BASE/f);assert d['current_master_catalogue']==pointer and d['latest_image_coverage_audit']==summary
assert digest(manifest['owner_ledger']['path'])==manifest['owner_ledger']['sha256']
assert digest(manifest['source_model']['path'])==manifest['source_model']['sha256']
assert digest(manifest['master_register']['path'])==manifest['master_register']['sha256']
assert read(manifest['master_register']['snapshot'])['original_review_specification_assertions']==g['original_review_specification_assertions']
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':digest(target),
  'register':str(HERE/'canonical-master-register.json'),'register_sha256':pointer['register_sha256'],'audit':summary['audit'],'audit_sha256':summary['audit_sha256'],
  'saved_file_verification':summary['verification'],'visual_verification':summary['visual_verification'],'controls':{f:digest(BASE/f) for f in updates},
  'current_master_pointer_sha256':digest(BASE/'current-master.json'),'original_workbook_snapshot':manifest['master_workbook']['snapshot'],
  'counts':audit['counts'],'source_model_and_owner_approval_ledger_unchanged':True,'previous_graph_immutable':True,'dropbox_and_platform_writes':0,
  'pending_owner_question':'Frozen Fish Long geometry/size relationship; optional asynchronous question has not been answered in this task.'}
write(HERE/'publication-receipt.json',receipt)
write(HERE/'completion.json',{'status':'COMPLETE_BOUNDED_IMAGE_AUDIT_AND_CURRENT_MASTER_PUBLICATION','recorded_utc':now(),'publication_receipt':relative(HERE/'publication-receipt.json'),
  'workbook':pointer['workbook'],'workbook_sha256':pointer['workbook_sha256'],'counts':audit['counts'],'remaining_work':next_actions,
  'all_exact_image_identity_gaps_resolved':False,'all6671_files_individually_classified':False,'all184_options_evaluated_for_each_photo_role':True})
print(json.dumps({'status':receipt['status'],'workbook_sha256':receipt['workbook_sha256'],'individual_full_views':157,'individual_photo_gaps':27,'in_situ_available':90,'new_tabs':4}))
