"""Import exact MS1 six-field working acceptance, retaining source conflicts and photos."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages
from import_moonphase_silver_working_specs_62 import ROOT, PATHS, read, sha, rel, write, specification_counts

HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch68'
SOURCE = ROOT / 'components/parallel-reviews/moonspiral-one-white-working-specs-2026-10-20/owner-working-specs-keep'
CID, VID = 'BC-MS-1', 'MS1-WHITE'

def main():
    docs = {key: read(path) for key, path in PATHS.items()}
    if (HERE / 'import-receipt.json').exists():
        assert docs['progress']['reviews'][CID]['size_finish_variants'][VID]['all_six_working_specification_fields_accepted']
        print(json.dumps({'batch':68,'status':'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    before, guards = copy.deepcopy(docs), {key:sha(path) for key,path in PATHS.items()}; files=[]
    def freeze(path,digest):
        path=Path(path); assert sha(path)==digest
        dest=HERE/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert sha(dest)==digest
        else:dest.write_bytes(path.read_bytes())
        files.append({'source':str(path),'snapshot':rel(dest),'sha256':digest});return rel(dest)
    package_path=SOURCE/'IMPORT_PACKAGE.json';digest='2a8da8cce5007bf25450607e6ce2dc303aa9edaff038d92624d0f00d6a218794';freeze(package_path,digest);package=read(package_path)
    freeze(package['manifest']['path'],package['manifest']['sha256'])
    for item in read(package['manifest']['path'])['files']:freeze(item['path'],item['sha256'])
    assert sha(package['decision']['path'])=='9f6c300e4bd06ae1ec7271c7ffbb138b98e1fc79bc413ffdae439a873c0af0b3'
    decision=read(package['decision']['path']);messages=canonical_messages([item|{'transcript':item['transcript_path']} for item in [decision['preceding_review_card_evidence'],decision['authoritative_user_evidence']]],package['source_owner_session'])
    assert [item['line'] for item in messages]==[28295,28329]
    assert messages[-1]['text']=='Keep these six working specifications for Moonspiral One — White (MS1), with the source conflicts, proposals'
    assert '__005.JPG' in messages[0]['text'] and 'source conflicts, proposals and unknowns' in messages[0]['text']
    u,p,cp,c=(docs[key] for key in ['user','progress','walkthrough','component']);node=p['reviews'][CID]['size_finish_variants'][VID]
    assert docs['root']['current_component_review']==c and cp['last_parallel_import']['batch']==67 and node['identity_confirmed'] and not node['proposals_approved']
    assert node['specification_proposals']==decision['source_specification_proposals_retained'] and len(node['specification_proposals'])==6
    assert decision['source_specifications_retained']==read(decision['source_review_before_answer']['path'])['specifications']
    metadata=read(HERE/'current-reference-check.json')['metadata'];head,folder=metadata[0]['file'],metadata[1]['folder'];ref=node['current_dropbox_reference']
    assert head['id']==ref['file_id'] and head['rev']==ref['rev'] and head['size']==ref['bytes'] and head['path_display']==ref['file_path'] and folder['id']==ref['folder_id'] and folder['path_display']==ref['folder_path']
    binding_ref=read(decision['source_review_before_answer']['path'])['image_evidence'];freeze(binding_ref['path'],binding_ref['sha256']);binding=read(binding_ref['path'])
    for item in binding['sources']:freeze(item['cached_preview']['path'],item['cached_preview']['sha256'])
    assert not binding['original_bytes_verified_this_turn'] and node['photo_coverage']['original_bytes_rehashed_this_context_review'] is False
    assert sha(package['context_output_update']['path'])=='c52ea62415aa982eba1c9e2730c22e0fcfa92d0d76af763cecbd64a5e8481478'
    freeze(HERE/'current-reference-check.json',sha(HERE/'current-reference-check.json'))
    protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/cp['current_review_record'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now=datetime.now(timezone.utc).isoformat();approval=rel(HERE/'working-specification-approval.json');fields=decision['approved_field_groups'];assert len(fields)==6 and set(fields)==set(decision['specifications'])
    scoped_ids=[VID+':'+field.upper() for field in fields]
    decision.update({'source_approved_proposal_ids':copy.deepcopy(decision['approved_proposal_ids']),'approved_proposal_ids':scoped_ids,'approval_record':approval,'imported_utc':now,'authoritative_user_evidence':messages[-1],'verified_review_card_evidence':messages[0],'shared_master_import_performed':True,'existing_context_import_retained':rel(ROOT/'components/reviews/parallel-import-2026-10-19-batch67/context-evidence.json'),'context_evidence_reimported':False})
    assert not any(item.get('decision_id')==decision['decision_id'] for item in u['size_finish_variant_specification_decisions'])
    u['size_finish_variant_specification_decisions'].append(decision);u['specification_approval_counts']=specification_counts(u)
    assert u['specification_approval_counts']['proposal_groups']==before['user']['specification_approval_counts']['proposal_groups']+6==100
    accepted=copy.deepcopy(decision['specifications'])
    for field,item in accepted.items():item['proposal_id']=VID+':'+field.upper()
    node.update({'specifications_approved':True,'proposals_approved':True,'owner_estimates_accepted':True,'source_claims_accepted_as_working':True,'all_six_working_specification_fields_accepted':True,'approved_proposal_ids':scoped_ids,'specification_approval':approval,'working_specifications_approval_scope':'EXACT_FINISH_ALL_SIX_WORKING_VALUES','accepted_working_specifications':accepted,'source_specification_proposals_retained_unchanged':True,'physical_specs_verified':False,'actual_stock_verified':False,'fully_confirmed_specification_groups':[],'physical_weight_conflict_resolved':False,'current_public_selling_price_verified':False,'specification_status_display':'Six working specifications accepted; source conflicts, proposals and unknowns retained','scope':decision['scope']+' Existing thumbnail-only context evidence67, prior name and stable image/folder IDs retained; exact cast and scene provenance unverified. Historical source_values flags remain source snapshots, separate from this working approval.'})
    p.setdefault('pending_specification_checks',{})[VID+'-WORKING-SPECS-01']={'owner_answer_recorded':True,'approval_record':approval,'working_values_accepted':True,'actual_specification_fields_pending':fields,'physical_specs_verified':False,'weight_conflict_resolved':False}
    c['interactive_review_state']['approved_proposal_groups']=100
    summary={'batch':68,'recorded_utc':now,'receipt':rel(HERE/'import-receipt.json'),'scope_kind':'EXACT_MS1_WHITE_SIX_WORKING_FIELDS_WITH_SOURCE_CONFLICTS','component_id':CID,'size_finish_variant_id':VID,'new_working_specification_approvals':1,'new_accepted_working_proposal_groups':6,'new_physically_verified_specification_groups':0,'new_name_approvals':0,'new_owner_policy_events':0,'new_registered_BC_component_ids':[],'context_evidence_reimported':False,'root_new_private_original_downloads':0,'remote_mutations':0,'workbook_export_pending':True}
    cp['parallel_import_queue'].append({'scope_kind':summary['scope_kind'],'receipt':rel(package_path),'receipt_sha256':digest,'approval_imported':True,'import_receipt':summary['receipt'],'status':'SIX_WORKING_FIELDS_ACCEPTED;SOURCE_CONFLICTS_PROPOSALS_AND_UNKNOWNS_RETAINED;ACTUAL_DETAILS_UNVERIFIED'})
    c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
    for target,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:target[key]=copy.deepcopy(summary)
    for doc in docs.values():doc['updated_utc']=now
    docs['root']['current_component_review']=copy.deepcopy(c)
    assert node['specification_proposals']==before['progress']['reviews'][CID]['size_finish_variants'][VID]['specification_proposals'] and node['photo_coverage']==before['progress']['reviews'][CID]['size_finish_variants'][VID]['photo_coverage']
    assert all(cp[key]==value for key,value in before['walkthrough'].items() if key.startswith('current_')) and all(sha(PATHS[key])==value for key,value in guards.items()) and all(sha(path)==value for path,value in protected.items())
    write(HERE/'before-import.json',before);write(HERE/'working-specification-approval.json',decision);write(HERE/'accepted-working-review.json',node);write(HERE/'source-manifest.json',{'files':files,'verified_messages':messages,'root_visual_evidence_kind':'THUMBNAILS_ONLY_NO_ORIGINAL_BYTE_VERIFICATION'})
    for key,path in PATHS.items():write(path,docs[key])
    write(HERE/'import-receipt.json',{'status':'APPLIED;INDEPENDENT_READBACK_REQUIRED','summary':summary,'decision_id':decision['decision_id'],'protected_sha256':protected,'shared_after_sha256':{key:sha(path) for key,path in PATHS.items()}})
    print(json.dumps({'batch':68,'status':'APPLIED','accepted_working_field_groups':100,'weight_conflict_resolved':False,'context_unchanged':True,'root_count_question_preserved':True}))

if __name__=='__main__':main()
