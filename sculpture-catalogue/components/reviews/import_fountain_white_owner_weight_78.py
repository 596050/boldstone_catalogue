"""Apply one owner weight selection after its six-field working approval."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from import_moonphase_silver_working_specs_62 import ROOT, PATHS, read, sha, rel, write
from import_source_followups_24_25 import canonical_messages

HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch78'
SOURCE = ROOT / 'components/parallel-reviews/fountain-palm-egyptian-white-working-specs-2026-10-20/owner-weight-15kg'
CID, VID = 'BC-FOUNTAIN-EG', 'FOUNTAIN-EG-WHITE'

def main():
    docs = {k: read(v) for k,v in PATHS.items()}
    if (HERE/'import-receipt.json').exists():
        assert docs['progress']['reviews'][CID]['owner_stated_weight_kg'] == 15
        print(json.dumps({'batch':78,'status':'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'}));return
    before=copy.deepcopy(docs);guards={k:sha(v) for k,v in PATHS.items()};files=[]
    def freeze(path,digest):
        path=Path(path);assert sha(path)==digest,str(path);dest=HERE/'sources'/(digest+path.suffix);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert sha(dest)==digest
        else:dest.write_bytes(path.read_bytes())
        item={'source':str(path),'snapshot':rel(dest),'sha256':digest}
        if item not in files:files.append(item)
    package_path=SOURCE/'IMPORT_PACKAGE.json';freeze(package_path,'a9d1ec4a704f110c9156f06c220ef3ee6372176f8146bb5e7ff4be68e4e073e1');pkg=read(package_path)
    for key in ['decision','current_weight_overlay','manifest','requires_prior_working_approval_package']:freeze(pkg[key]['path'],pkg[key]['sha256'])
    for item in read(pkg['manifest']['path'])['files']:freeze(item['path'],item['sha256'])
    decision=read(pkg['decision']['path']);overlay=read(pkg['current_weight_overlay']['path'])
    evidence=[decision['preceding_assistant_context'],decision['owner_evidence']];messages=canonical_messages([x|{'transcript':x['transcript_path']} for x in evidence],pkg['source_owner_session'])
    assert [x['line'] for x in messages]==[18744,18751] and messages[-1]['text']=='15 kg' and 'Fountain Palm Egyptian — White' in messages[0]['text'] and messages[-1]['immediately_preceding_assistant']['line']==18744
    u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component']);node=p['reviews'][CID]
    assert docs['root']['current_component_review']==c and cp['last_parallel_import']['batch']==77 and node['all_six_working_specification_fields_accepted']
    weight=copy.deepcopy(node['accepted_working_specifications']['weight']);weight.pop('proposal_id');assert weight==decision['before_weight'] and overlay['current_weight']==decision['current_weight']
    assert decision['owner_weight_kg']==15 and not decision['actual_weighing_independently_verified'] and not decision['outstanding_catalogue_weight_conflict']
    protected={str(path):sha(path) for path in [ROOT/cp['register_workbook'],ROOT/cp['current_review_record'],ROOT/'components/evidence/component_register.json',ROOT.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']};now=datetime.now(timezone.utc).isoformat();approval=rel(HERE/'owner-weight.json')
    decision.update({'owner_stated_weight_kg':15,'user_statement':'15 kg','authoritative_user_evidence':messages[-1],'verified_assistant_context_evidence':messages[0],'approval_record':approval,'imported_utc':now,'shared_master_import_performed':True,'measurement_method':'UNCONFIRMED','independently_weighed':False,'actual_measured_weight_kg':None})
    assert not any(x.get('decision_id')==decision['decision_id'] for x in u.get('weight_decisions',[]));u.setdefault('weight_decisions',[]).append(decision)
    u['weight_confirmation_counts']={'components':len({x['component_id'] for x in u['weight_decisions']}),'individual_weight_decisions':len(u['weight_decisions']),'counts_scope':'Scoped owner weight statements, separate from whole-specification approvals and physical stock counts.'}
    current=copy.deepcopy(overlay['current_weight']);current['proposal_id']=VID+':WEIGHT';current['owner_weight_confirmation']=approval
    node['accepted_working_specifications']['weight']=current
    node.update({'owner_stated_weight_kg':15,'owner_weight_confirmation':approval,'weight_measurement_method':'UNCONFIRMED','actual_measured_weight_kg':None,'actual_weighing_independently_verified':False,'outstanding_catalogue_weight_conflict':False,'owner_catalogue_weight_selection_resolves_source_conflict':True,'historical_weight_source_values_retained':True,'specification_status_display':'Six working specifications accepted;15kg owner-stated, historical sources and unknowns retained','scope':'Exactly Fountain Palm Egyptian — White. All six working fields remain accepted. Owner selects15kg for this individual panel; earlier16kg draft is retained as historical source, no longer a pending catalogue weight choice. Weighing method is unrecorded and no independent physical mass verification is claimed. Listing100x50x6,AC730 hypothesis,fixing hardware/load,900GBP retail versus625dated trade,MTO stock/lead and exact platform applicability retain their prior scoped evidence. Other finishes and original source dictionaries are unchanged.'})
    p.setdefault('pending_specification_checks',{})[VID+'-OWNER-WEIGHT-15KG']={'owner_answer_recorded':True,'approval_record':approval,'owner_stated_weight_kg':15,'outstanding_catalogue_weight_conflict':False,'independent_weighing_verified':False}
    summary={'batch':78,'recorded_utc':now,'receipt':rel(HERE/'import-receipt.json'),'scope_kind':'EXACT_WHITE_OWNER_WEIGHT15KG_ONLY;16KG_HISTORICAL','component_id':CID,'size_finish_variant_id':VID,'new_owner_weight_confirmation_events':1,'new_working_specification_approvals':0,'new_accepted_working_proposal_groups':0,'new_physically_verified_specification_groups':0,'new_name_approvals':0,'new_owner_policy_events':0,'new_registered_BC_component_ids':[],'root_new_private_original_downloads':0,'remote_mutations':0,'workbook_export_pending':True}
    cp['parallel_import_queue'].append({'scope_kind':summary['scope_kind'],'receipt':rel(package_path),'receipt_sha256':sha(package_path),'approval_imported':True,'import_receipt':summary['receipt'],'status':'OWNER15KG_RECORDED;16KG_SOURCE_HISTORY_RETAINED;NO_SIX_FIELD_REPLAY'});c['parallel_import_queue']=copy.deepcopy(cp['parallel_import_queue'])
    for target,key in [(p,'latest_parallel_import'),(cp,'last_parallel_import'),(c,'last_parallel_import')]:target[key]=copy.deepcopy(summary)
    for doc in docs.values():doc['updated_utc']=now
    docs['root']['current_component_review']=copy.deepcopy(c)
    assert u['specification_approval_counts']==before['user']['specification_approval_counts'] and all(cp[k]==v for k,v in before['walkthrough'].items() if k.startswith('current_'))
    assert node['specification_proposals']==before['progress']['reviews'][CID]['specification_proposals'] and all(sha(PATHS[k])==v for k,v in guards.items()) and all(sha(path)==v for path,v in protected.items())
    write(HERE/'before-import.json',before);write(HERE/'owner-weight.json',decision);write(HERE/'current-weight-overlay.json',current);write(HERE/'source-manifest.json',{'files':files,'verified_messages':messages})
    for k,path in PATHS.items():write(path,docs[k])
    write(HERE/'import-receipt.json',{'status':'APPLIED;INDEPENDENT_READBACK_REQUIRED','summary':summary,'decision_id':decision['decision_id'],'protected_sha256':protected,'shared_after_sha256':{k:sha(v) for k,v in PATHS.items()}})
    print(json.dumps({'batch':78,'status':'APPLIED','owner_stated_weight_kg':15,'historical_draft_kg':16,'independently_weighed':False,'accepted_working_groups_unchanged':136}))

if __name__=='__main__':main()
