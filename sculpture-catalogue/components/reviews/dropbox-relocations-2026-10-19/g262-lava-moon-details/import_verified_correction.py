"""Apply the verified family reassignment without inferring a sculpture identity."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rel=lambda p:str(p.relative_to(ROOT))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temp.replace(path)


def main():
    output=HERE/'shared-catalogue-correction.json'
    assert not output.exists()
    reserve=read(HERE/'exclusive-write-reservation.json')
    manifest=read(HERE/'peer-source/move-manifest.json')
    execution=read(HERE/'peer-source/execution-receipt.json')
    source=read(HERE/'peer-source/catalogue-correction.json')
    owner=read(HERE/'peer-source/owner-instruction.json')
    originals=read(HERE/'independent-current-originals.json')
    metadata={x['request_id']:x for x in read(HERE/'current-metadata.json')['entries']}
    links={x['file_name']:x for x in read(HERE/'current-links.json')['results']}
    sharing=read(HERE/'current-shared-links.json')
    assert owner['text']==source['owner_text']==reserve['authority']['text']
    assert owner['line']==23694 and sha(HERE/'peer-source/owner-instruction.json')==manifest['source_instruction_sha256']
    assert source['owner_confirmed_family']=='Lava Moon' and not source['Keep_given']
    assert source['physical_specifications_confirmed_by_this_correction']==[] and source['Luciano_PDF_unchanged_and_not_reassigned']
    assert execution['all_file_and_folder_ids_preserved'] and execution['all_original_file_bytes_preserved']
    assert not execution['pending_remote_jobs'] and execution['shared_write_locks_released']
    assert originals['status']=='PASS' and originals['total_bytes']==1405297 and len(originals['entries'])==3
    expected={x['file_id']:x for x in manifest['files']}
    folder_id=manifest['folder']['folder_id']
    folder=metadata[folder_id]['folder']
    assert folder['id']=='id:cnqzTNngPVsAAAAAAAyi6w' and folder['path_display']==manifest['folder']['destination_path']
    current_assets=[]
    for item in originals['entries']:
        old=expected[item['file_id']]
        assert item['sha256']==old['sha256'] and item['content_hash']==old['content_hash']
        assert sha(Path(item['local_path']))==old['sha256']
        file=metadata[item['file_id']]['file']
        assert file['id']==item['file_id'] and file['path_display']==old['destination_path'] and file['size']==old['size']
        current_assets.append({'file_id':file['id'],'folder_id':folder_id,'name':file['name'],'path_display':file['path_display'],
            'rev':file['rev'],'size':file['size'],'sha256':item['sha256'],'content_hash':item['content_hash'],
            'source_path_before_move':old['source_path'],'image_link':links[file['id']]['copy_link_url']})
    assert len(sharing['entries'])==4 and all(not x['result']['has_more'] for x in sharing['entries'])
    current_link_entries=[link for row in sharing['entries'] for link in row['result']['links']]
    assert len(current_link_entries)==4 and all(x['audience']=='no_one' and x['access_level']=='view' for x in current_link_entries)
    paths={'user':ROOT/'components/reviews/user_classifications.json','progress':ROOT/'components/reviews/specification_review_progress.json',
        'walkthrough':ROOT/'components/reviews/walkthrough_checkpoint.json','component':ROOT/'components/checkpoint.json','root':ROOT/'checkpoint.json'}
    docs={k:read(path) for k,path in paths.items()}
    before=copy.deepcopy(docs)
    hashes={k:sha(path) for k,path in paths.items()}
    u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component'])
    assert docs['root']['current_component_review']==c and cp['current_component_id']=='BC-MCP-4' and not cp['current_answer_recorded']
    protected={str(path):sha(path) for path in [ROOT/cp['current_review_record'],ROOT/cp['register_workbook'],ROOT/'components/evidence/component_register.json']}
    now=datetime.now(timezone.utc).isoformat()
    record={'schema':'boldstone.verified-owner-asset-family-correction.v1','decision_id':'G262:OWNER_LAVA_MOON_DETAILS:MASTER',
        'source_decision_id':'G262:OWNER_FAMILY_CORRECTION:2026-10-19T09:47:40.555Z','recorded_utc':now,
        'status':'VERIFIED_MOVE_AND_MASTER_FAMILY_REASSIGNMENT_APPLIED','source_owner_session':reserve['authority']['source_owner_session'],
        'user_statement':owner['text'],'authoritative_user_evidence':reserve['authority'],'group_ref':'G262','folder_id':folder_id,
        'previous_folder_path':manifest['folder']['source_path'],'current_folder_path':folder['path_display'],
        'folder_link':links[folder_id]['copy_link_url'],'current_file_ids':[x['file_id'] for x in current_assets],
        'current_assets':current_assets,'owner_confirmed_family':'Lava Moon',
        'previous_component_associations_withdrawn':['BC-LUCIANO-1','BC-LUCIANO-2','BC-LUCIANO-3'],
        'current_specific_component_ids':[],'exact_component_position_design_finish':'UNCONFIRMED',
        'depiction_role':'Detail photographs only','independent_Luciano_project_PDF_reassigned':False,
        'identity_Keep_inferred':False,'physical_specs_verified':False,'new_specification_approval_inferred':False,
        'source_execution_receipt':rel(HERE/'peer-source/execution-receipt.json'),
        'source_execution_receipt_sha256':sha(HERE/'peer-source/execution-receipt.json'),
        'independent_current_originals':rel(HERE/'independent-current-originals.json'),
        'all_folder_and_file_IDs_preserved':True,'all1405297_original_bytes_preserved':True,
        'sharing_observation':{'peer_direct_links_at_execution':0,'root_after_preview_direct_links':4,
            'current_audience':'no_one','current_access_level':'view','all4_scoped_link_listings_complete':True,
            'peer_zero_link_snapshot_is_not_claimed_as_current':True,'full_sharing_or_exact_link_state_unchanged_claimed':False},
        'workbook_export_pending':True,'live_platform_records_changed':False}
    for item in current_assets:
        assert item['file_id'] not in p['asset_assignment_overrides']
        p['asset_assignment_overrides'][item['file_id']]={'source':'EXACT_OWNER_FAMILY_CORRECTION;VERIFIED_REMOTE_RELOCATION',
            'correction_record':rel(output),'group_ref':'G262','family':'Lava Moon','component_ids':[],
            'removed_component_ids':record['previous_component_associations_withdrawn'],'exact_component_and_finish_confirmed':False,
            'role':'Detail only','file_id':item['file_id'],'folder_id':folder_id,'path_display':item['path_display'],
            'rev':item['rev'],'bytes':item['size'],'sha256':item['sha256'],'content_hash':item['content_hash'],
            'image_link':item['image_link'],'folder_link':record['folder_link'],'physical_specs_verified':False}
    p.setdefault('catalogue_group_overrides',{})['G262']={'source_group_ref':'G262','current_family':'Lava Moon',
        'current_folder_id':folder_id,'current_name':'Lava Moon Details','current_folder_path':folder['path_display'],
        'active_component_ids':[],'withdrawn_component_ids':record['previous_component_associations_withdrawn'],
        'current_assets':current_assets,'correction_record':rel(output),'role':'Detail only; exact panel/finish unassigned',
        'independent_Luciano_PDF_unchanged':True}
    u.setdefault('asset_family_correction_decisions',[]).append(record|{'approval_record':rel(output)})
    p['family_review_progress']['Lava Moon']['additional_owner_reassigned_detail_group']=copy.deepcopy(p['catalogue_group_overrides']['G262'])
    c['family_review_supplements']['Lava Moon']['additional_owner_reassigned_detail_group']=copy.deepcopy(p['catalogue_group_overrides']['G262'])
    for item in cp['parallel_owner_reviews']:
        if item['component_id'] in record['previous_component_associations_withdrawn']:
            item.update({'source_detail_folder_correction':rel(output),'excluded_active_detail_file_ids':record['current_file_ids'],
                'independent_Luciano_project_PDF_remains_source':True,'no_identity_Keep_from_folder_correction':True})
    reservations=cp['dropbox_write_reservations']
    match=[x for x in reservations if x['reservation_id']==reserve['reservation_id']]
    assert len(match)==1
    match[0].update({'status':'VERIFIED_REMOTE_MOVE;MASTER_CORRECTION_APPLIED;RESERVATION_RELEASED',
        'verified_correction_record':rel(output),'released_utc':now})
    cp['updated_utc']=now
    c.update({'dropbox_write_reservations':copy.deepcopy(reservations),'parallel_owner_reviews':copy.deepcopy(cp['parallel_owner_reviews']),
        'latest_owner_asset_family_correction':rel(output),'updated_utc':now})
    p['updated_utc']=u['updated_utc']=now
    docs['root']['current_component_review']=copy.deepcopy(c)
    docs['root']['updated_utc']=now
    assert all(cp[k]==v for k,v in before['walkthrough'].items() if k.startswith('current_') or k in ['proposed_name','answer_state','question_scope','next_review_after_keep','parallel_import_holds'])
    assert p['reviews']==before['progress']['reviews'] and p['offer_photo_bindings']==before['progress']['offer_photo_bindings']
    for k in ['identity_confirmation_counts','specification_approval_counts','dimension_confirmation_counts']:
        assert u[k]==before['user'][k]
    assert all(sha(path)==hashes[k] for k,path in paths.items()) and all(sha(Path(path))==digest for path,digest in protected.items())
    write(HERE/'before-shared-correction.json',{'recorded_utc':now,'files':{rel(paths[k]):v for k,v in before.items()},'protected_sha256':protected})
    write(output,record)
    for key,path in paths.items():
        write(path,docs[key])
        assert read(path)==docs[key]
    write(HERE/'independent-shared-readback.json',{'status':'PASS','checked_utc':now,'root_component_mirror':read(paths['root'])['current_component_review']==read(paths['component']),
        'all3_active_asset_overrides_point_to_Lava_Moon':all(read(paths['progress'])['asset_assignment_overrides'][x['file_id']]['family']=='Lava Moon' for x in current_assets),
        'no_Luciano_PDF_or_specific_Lava_panel_or_specification_transfer':True,'current_Concave_question_preserved':True,
        'prior_identity_and_specification_counts_unchanged':True,'receipt_sha256':sha(output)})
    print(json.dumps({'status':record['status'],'files':3,'original_bytes_verified':1405297,'new_specific_sculpture_matches':0,
        'receipt':str(output),'receipt_sha256':sha(output),'current_Concave_question_preserved':True}))


if __name__=='__main__':
    main()
