"""Import exact scoped Keeps and an arrangement; preserve the active owner question."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / 'components/reviews'
sys.path.insert(0,str(ROOT / 'components/scripts'))
from review_decision_counts import identity_counts, specification_counts
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temp.replace(path)


def apply(number):
    here = REVIEWS / f'parallel-import-2026-10-19-batch{number}'
    manifest = read(here / 'source-manifest.json')
    receipt_path = here / 'import-receipt.json'
    paths = {'user':REVIEWS/'user_classifications.json','progress':REVIEWS/'specification_review_progress.json',
        'walkthrough':REVIEWS/'walkthrough_checkpoint.json','component':ROOT/'components/checkpoint.json','root':ROOT/'checkpoint.json'}
    docs = {k:read(path) for k,path in paths.items()}
    if receipt_path.exists():
        ids = [x.get('source_decision_id') for values in docs['user'].values() if isinstance(values,list) for x in values if isinstance(x,dict)]
        assert all(ids.count(d['source_decision_id'])==1 for d in manifest['decisions'])
        print(json.dumps({'batch':number,'status':'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'}))
        return
    for entry in manifest['files']:
        f=ROOT/entry['snapshot']
        assert sha(f)==entry['sha256'] and f.stat().st_size==entry['bytes']
    current=read(here/'current-reference-check.json')
    heads={x['request_id']:x for x in current['metadata']}

    def reference(primary,folder,image_url=None,folder_url=None):
        file,fol=heads[primary['file_id']]['file'],heads[folder['folder_id']]['folder']
        assert file['rev']==primary['rev'] and file['size']==primary['size']
        assert file['path_display']==primary['path_display'] and fol['path_display']==folder['path_display']
        assert file['path_display'].rsplit('/',1)[0]==fol['path_display']
        reviewed_file_path=primary.get('reviewed_path_display',primary['path_display'])
        reviewed_folder_path=folder.get('reviewed_path_display',folder['path_display'])
        case_variation=file['path_display']!=reviewed_file_path or fol['path_display']!=reviewed_folder_path
        assert file['path_display'].casefold()==reviewed_file_path.casefold() and fol['path_display'].casefold()==reviewed_folder_path.casefold()
        return {'file_id':file['id'],'folder_id':fol['id'],'file_path':file['path_display'],'folder_path':fol['path_display'],
            'rev':file['rev'],'bytes':file['size'],'sha256':primary['sha256'],'dropbox_content_hash':primary['content_hash'],
            'checked_utc':current['checked_utc'],'changed_since_owner_card':case_variation,
            'reference_change_scope':'DISPLAYED_PATH_CASE_ONLY;SAME_FILE_ID_REV_SIZE_CONTENT_HASH' if case_variation else None,
            'reviewed_file_path':reviewed_file_path,'reviewed_folder_path':reviewed_folder_path,
            'image_url':image_url or primary['open_in_dropbox_url'],'folder_url':folder_url or folder['open_in_dropbox_url'],
            'source_image_limits':primary.get('selection_reason',primary.get('role'))}

    before=copy.deepcopy(docs)
    hashes={k:sha(path) for k,path in paths.items()}
    u,p,cp,c=(docs[k] for k in ['user','progress','walkthrough','component'])
    assert docs['root']['current_component_review']==c
    assert cp['current_component_id']=='BC-MCP-4' and cp['review_decision_mode']=='DEPICTED_DESIGN_ALIAS_RELATIONSHIP_ONLY'
    assert not cp['current_answer_recorded']
    assert cp['parallel_import_holds']['Moonphases']['old_five_design_import_allowed'] is False
    protected={str(path):sha(path) for path in [ROOT/'components/evidence/component_register.json',ROOT/cp['register_workbook'],
        ROOT/cp['current_review_record'],ROOT/cp['last_identity_approval'],ROOT/'components/reviews/concave-moon-review-2026-10-17/specification-approval.json']}
    affected={d['component_id'] for d in manifest['decisions']}
    allowed_existing=set(manifest.get('allow_existing_component_ids',[]))
    assert allowed_existing <= affected
    assert not any(cid in p['reviews'] and cid not in allowed_existing for cid in affected)
    now=datetime.now(timezone.utc).isoformat()
    outputs=[]
    imported=[]
    targets=[]
    resolutions=[]
    new_targets=0
    existing_ids={x.get('source_decision_id') for values in u.values() if isinstance(values,list) for x in values if isinstance(x,dict)}

    def save(suffix,value,ledger=None):
        output=here/'decisions'/suffix
        assert not output.exists()
        outputs.append((output,value))
        if ledger:
            u.setdefault(ledger,[]).append(value|{'approval_record':rel(output)})
        return rel(output)

    for d in manifest['decisions']:
        assert d['source_decision_id'] not in existing_ids
        a=read(ROOT/d['receipt_snapshot'])
        card=read(ROOT/d['working_entry'])
        ref=reference(d['primary_expected'],d['folder_expected'],d['image_url'],d['folder_url'])
        cid,vid=d['component_id'],d['variant_id']
        build=d['scope_kind']=='build_variant_identity'
        proposals=copy.deepcopy(card['specification_review_items'])
        for item in proposals:
            item.update({'field':item.get('field',item['group']),'display':item.get('display',item.get('proposal')),
                'owner_approved':False,'physical_specs_verified':False})
        assert len(proposals)==6 and not a['fully_confirmed_specification_groups']
        decision={'schema_version':1,'decision_id':cid+':'+vid+':identity:keep','component_id':cid,
            ('build_variant_id' if build else 'size_finish_variant_id'):vid,'canonical_name':d['name'],'confirmed_name':d['name'],
            'source_configuration_id':card.get('source_configuration_id'),'recorded_utc':d['authoritative_owner_evidence']['timestamp'],
            'imported_utc':now,'review_number':d['review_number'],'action':'keep','user_statement':d['authoritative_owner_evidence']['text'],
            'status':'USER CONFIRMED DEPICTED NAME AND SCOPED IDENTITY; INCOMPLETE SPECIFICATIONS RETAINED',
            'identity_confirmed':True,'identity_scope':a['identity_scope'],'scope':a['scope_note'],
            'source_owner_session':d['owner_session'],'source_decision_id':d['source_decision_id'],
            'source_receipt_snapshot':d['receipt_snapshot'],'source_receipt_sha256':d['receipt_sha256'],
            'proposal_source':d['pre_answer_review'],'proposal_source_sha256':d['pre_answer_review_sha256'],
            'latest_working_entry_snapshot':d['working_entry'],'latest_working_entry_sha256':d['working_entry_sha256'],
            'authoritative_user_evidence':d['authoritative_owner_evidence'],'preceding_assistant_card_evidence':d['preceding_review_card_evidence'],
            'specifications_approved':False,'proposals_approved':False,'approved_proposal_ids':[],
            'confirmed_fields':['Working component/finish/build name','Depicted identity within source scope'],
            'not_confirmed':[x['field'] for x in proposals],'physical_specs_verified':False,'physical_manufacture_confirmed':False,
            'primary_file_id':ref['file_id'],'primary_folder_id':ref['folder_id'],'current_dropbox_reference':ref,
            'image_link':ref['image_url'],'folder_link':ref['folder_url'],'remote_files_changed':False,
            'live_platform_records_changed':False,'workbook_status':'Unchanged; local review overlay for later export.'}
        for extra in ['depicted_component_position','additional_source_references','photo_reference_scope']:
            if extra in d:
                decision[extra]=copy.deepcopy(d[extra])
        output=save(cid+'/'+vid+'/identity-approval.json',decision,'build_variant_identity_decisions' if build else 'size_finish_variant_decisions')
        target={'canonical_name':d['name'],'identity_confirmed':True,('build_variant_id' if build else 'size_finish_variant_id'):vid,
            'identity_approval':output,'review_record':d['pre_answer_review'],'latest_working_entry':d['working_entry'],
            'specification_proposals':proposals,'specifications_approved':False,'proposals_approved':False,'physical_specs_verified':False,
            'primary_image_id':ref['file_id'],'primary_folder_id':ref['folder_id'],'current_dropbox_reference':ref,
            'scope':a['scope_note'],'identity_scope':a['identity_scope'],'platform_mapping':copy.deepcopy(card['platform_mapping']),
            'photo_selection_review':copy.deepcopy(card.get('photo_selection_review')),'production_status':copy.deepcopy(card.get('production_status')),
            'missing_photographs':copy.deepcopy(card['missing_photographs']),'missing_specifications':copy.deepcopy(card['missing_specifications']),
            'complete_source_review_snapshot':d['working_entry'],'workbook_contains_import':False}
        for extra in ['depicted_component_position','additional_source_references','photo_reference_scope']:
            if extra in d:
                target[extra]=copy.deepcopy(d[extra])
        if d['owner_confirmed_fields']:
            assert cid=='BC-LAVA-CORNER' and len(d['owner_confirmed_fields'])==1
            field=d['owner_confirmed_fields'][0]
            assert field['width_cm']==field['height_cm']==30 and not field['measured_existing_specimen']
            assert field['source_exact_text']=='Make the panel into 30cm' and not field['applies_to_other_Moonshell_Lava_components']
            size={'schema_version':1,'decision_id':cid+':'+vid+':owner-directed-square-face-target',
                'source_decision_id':d['source_decision_id']+':face-target','source_instruction_decision_id':d['source_decision_id'],
                'component_id':cid,'size_finish_variant_id':vid,'recorded_utc':d['authoritative_owner_evidence']['timestamp'],
                'imported_utc':now,'user_statement':d['authoritative_owner_evidence']['text'],'authoritative_user_evidence':d['authoritative_owner_evidence'],
                'scope_kind':'OWNER_DIRECTED_TARGET_FACE_SIZE','target_face_dimensions_cm':{'width':30,'height':30},
                'interpretation':'30cm interpreted as a square face target from the depicted square panel; owner did not type a second axis.',
                'actual_existing_face_dimensions_cm':None,'actual_depth_cm':None,'existing_cast_measured':False,
                'production_feasibility_verified':False,'other_specifications_approved':False,'physical_specs_verified':False,
                'source_receipt_snapshot':d['receipt_snapshot'],'source_receipt_sha256':d['receipt_sha256']}
            size_path=save(cid+'/'+vid+'/owner-size-target.json',size,'design_size_target_decisions')
            target.update({'owner_face_size_target_cm':{'width':30,'height':30},'owner_size_target_approval':size_path,
                'current_cast_dimensions_measured':False,'size_target_is_existing_measured_specification':False})
            dim=next(x for x in proposals if x['group']=='dimensions_and_depth')
            dim.update({'owner_partial_instruction_recorded':True,'owner_approved_target_face_dimensions_cm':{'width':30,'height':30},
                'owner_confirmed_subfields':['face_size_target'],'current_cast_measured':False})
            new_targets+=1
        parent=p['reviews'].setdefault(cid,{'identity_confirmed':False,'specifications_approved':False,'physical_specs_verified':False,
            'scope':'Named individual configurations approved below; no blanket all-finish or stock approval.'})
        variants=parent.setdefault('build_variants' if build else 'size_finish_variants',{})
        assert vid not in variants, 'Refuse to replace an existing variant'
        variants[vid]=target
        cp['pending_specification_reviews'].append({'component_id':cid,('build_variant_id' if build else 'size_finish_variant_id'):vid,
            'canonical_name':d['name'],'identity_approved':True,'specifications_approved':False,'pending_fields':[x['field'] for x in proposals],
            'review_record':d['working_entry'],'identity_approval':output,'image_link':ref['image_url'],'folder_link':ref['folder_url'],
            'partial_owner_face_target_only':cid=='BC-LAVA-CORNER'})
        imported.append({'component_id':cid,'variant_id':vid,'scope_kind':d['scope_kind'],'name':d['name'],'approval':output,'source_decision_id':d['source_decision_id']})
        targets.append(target)
    arrangement_outputs=[]
    for item in manifest['arrangements']:
        a=read(ROOT/item['snapshot'])
        ref=reference(item['primary_expected'],item['folder_expected'])
        aid=a['arrangement_id']
        members=[{'component_id':x['component_id'],'working_name':x['working_name'],'position':x['position'],
            'source_position_reference_id':x['wall_position_reference'],'owner_membership_confirmed':True,'position_owner_stated':False,
            'position_basis':a['position_basis']} for x in a['members']]
        record={'schema_version':1,'decision_id':a['decision_id']+':master-membership','source_decision_id':a['decision_id'],
            'arrangement_id':aid,'canonical_name':a['working_arrangement_name'],'recorded_utc':item['owner']['timestamp'],'imported_utc':now,
            'source_owner_session':a['owner_session'],'user_statement':item['owner']['text'],'authoritative_user_evidence':item['owner'],
            'preceding_assistant_card_evidence':item['preceding_card'],'members':members,'owner_combined_membership_confirmed':True,
            'positions_owner_stated':False,'position_basis':a['position_basis'],'current_dropbox_reference':ref,
            'primary_file_id':ref['file_id'],'primary_folder_id':ref['folder_id'],'additional_same_arrangement_file_id':a['additional_same_arrangement_image']['file_id'],
            'same_measured_size_confirmed':False,'same_actual_cast_or_mould_confirmed':False,'specifications_approved':False,
            'physical_specs_verified':False,'additional_product_or_stock_created':False,'source_receipt_snapshot':item['snapshot']}
        ar=save('arrangements/'+aid+'/membership.json',record,'arrangement_membership_decisions')
        p.setdefault('arrangement_component_bindings',{})[aid]=record|{'approval_record':ar}
        for snap in manifest['position_resolution_snapshots']:
            r=read(ROOT/snap)
            cid,canonical=r['component_id'],r['target_component_id']
            relation={'schema_version':1,'decision_id':r['component_id']+':reference:'+canonical,
                'source_decision_id':a['decision_id']+':'+cid+':position-reference','source_instruction_decision_id':a['decision_id'],
                'recorded_utc':item['owner']['timestamp'],'imported_utc':now,'component_id':cid,'canonical_component_id':canonical,
                'canonical_size_finish_variant_id':'MLAVA-1-WHITE' if canonical=='BC-MLAVA-1' else 'MLAVA-2-WHITE',
                'relationship':'POSITION_REFERENCE_IN_OWNER_CONFIRMED_COMBINED_ARRANGEMENT','status':'RESOLVED_REFERENCE;NO_ADDITIONAL_PRODUCT',
                'user_statement':item['owner']['text'],'authoritative_user_evidence':item['owner'],'arrangement_id':aid,
                'owner_combined_membership_confirmed':True,'position':r['position'],'position_owner_stated':False,'position_basis':r['position_basis'],
                'same_physical_cast_confirmed':False,'same_mould_confirmed':False,'specifications_approved':False,'approved_proposal_ids':[],
                'physical_specs_verified':False,'new_independent_product_created':False,'source_receipt_snapshot':snap,
                'current_dropbox_reference':ref,'primary_file_id':ref['file_id'],'primary_folder_id':ref['folder_id'],'arrangement_approval':ar}
            rp=save('arrangements/'+aid+'/'+cid+'-reference.json',relation,'component_identity_relationship_decisions')
            assert cid not in p['reviews']
            p['reviews'][cid]={'status':'RESOLVED_POSITION_REFERENCE_NO_ADDITIONAL_PRODUCT','canonical_component_id':canonical,
                'relationship_approval':rp,'owner_combined_membership_confirmed':True,'position_owner_stated':False,
                'identity_confirmed':False,'specifications_approved':False,'specification_proposals':[],'physical_specs_verified':False,
                'same_cast_mould_and_dimensions_verified':False,'arrangement_id':aid}
            resolutions.append({'source_component_id':cid,'canonical_component_id':canonical,'approval':rp})
        arrangement_outputs.append(ar)
    u['identity_confirmation_counts']=identity_counts(u)
    u['specification_approval_counts']=specification_counts(u)
    assert u['specification_approval_counts']==before['user']['specification_approval_counts']
    assert u['dimension_confirmation_counts']==before['user']['dimension_confirmation_counts']
    new_identity_scope_components=manifest.get('expected_new_identity_scope_components',len(affected))
    assert u['identity_confirmation_counts']['components_with_any_identity_scope']==before['user']['identity_confirmation_counts']['components_with_any_identity_scope']+new_identity_scope_components
    summary={'recorded_utc':now,'receipt':rel(receipt_path),'batch':number,'component_ids':sorted(affected),'canonical_identity_receipts':len(imported),
        'new_finish_names':sum(x['scope_kind']=='size_finish_variant' for x in imported),'new_build_names':sum(x['scope_kind']=='build_variant_identity' for x in imported),
        'new_identity_scope_components':new_identity_scope_components,
        'owner_directed_size_targets':new_targets,'new_complete_specification_approvals':0,'wholly_unconfirmed_specification_groups':len(imported)*6-new_targets,
        'partial_specification_groups':new_targets,'owner_confirmed_arrangements':len(arrangement_outputs),'resolved_position_references':len(resolutions),
        'additional_products_from_arrangement_positions':0,'current_Concave_MCP4_question_preserved':True,'Moonphases_four_design_hold_preserved':True,
        'workbook_export_pending':True,'physical_specs_verified':False,'remote_mutations':0}
    family=manifest.get('family', 'Crater / Fishwave / Ring' if number==9 else 'Moonshell Lava and Corner')
    supplement={'import_receipt':rel(receipt_path),'source_manifest':rel(here/'source-manifest.json'),'source_package_sha256':manifest['source_package_sha256'],
        'import_constraints':manifest['import_constraints'],'outstanding_followups':manifest['outstanding_followups'],
        'root_refreshed_primary_and_containing_folder_heads':len(current['metadata']),'root_selected_originals_viewed_in_contact_sheet':True,
        'whole_library_or_whole_family_root_live_reaudit_claimed':False,'reference_total_is_physical_inventory':False,'summary':summary}
    c['family_review_supplements'][family]=copy.deepcopy(supplement)
    p.setdefault('parallel_family_evidence',{})[family]=copy.deepcopy(supplement)
    p['family_review_progress'][family]={'status':'SCOPED_NAMES_IMPORTED;INCOMPLETE_FIELDS_AND_PHOTO_GAPS_RETAINED',
        'specifications_complete':False,'physical_specs_verified':False,'reference_total_is_sculpture_count':False,'supplement':copy.deepcopy(supplement)}
    existing_queue=next((x for x in cp['parallel_import_queue'] if x['receipt']==manifest['source_package']),None)
    queue={'scope_kind':'SEALED_REVIEW_IMPORT_PACKAGE','receipt':manifest['source_package'],'receipt_sha256':manifest['source_package_sha256'],
        'frozen_package_snapshot':manifest['source_package_snapshot'],'source_owner_session':manifest['decisions'][0]['owner_session'],
        'status':'APPLIED_AND_VERIFIED;EXACT_SCOPES_AND_GAPS_RETAINED','approval_imported':True,'source_manifest':rel(here/'source-manifest.json'),
        'import_receipt':rel(receipt_path),'imported_utc':now,'new_specification_approval_inferred':False}
    if existing_queue is None:
        cp['parallel_import_queue'].append(queue)
    else:
        assert not existing_queue['approval_imported']
        existing_queue.update(queue)
    for item in cp['parallel_owner_reviews']:
        if item['component_id'] in affected or item['component_id'] in {x['source_component_id'] for x in resolutions}:
            item.update({'status':'SCOPED CANONICAL NAMES OR EXISTING-COMPONENT REFERENCES IMPORTED;GAPS RETAINED','import_receipt':rel(receipt_path)})
    cp['last_parallel_import']=copy.deepcopy(summary)
    cp['next_serialized_parallel_import']={'status':'APPLIED_AND_VERIFIED','receipt':rel(receipt_path),'source_package':manifest['source_package'],'completed_utc':now}
    cp['completed_serialized_parallel_import']=copy.deepcopy(cp['next_serialized_parallel_import'])
    cp['updated_utc']=now
    p['latest_parallel_import']=copy.deepcopy(summary)
    c.update({'parallel_import_queue':copy.deepcopy(cp['parallel_import_queue']),'parallel_owner_reviews':copy.deepcopy(cp['parallel_owner_reviews']),
        'last_parallel_import':copy.deepcopy(summary),'updated_utc':now})
    counts=u['identity_confirmation_counts']
    c['interactive_review_state'].update({'explicit_identity_confirmations':counts['component_designs'],
        'explicit_size_finish_variant_names_confirmed':counts['explicit_size_finish_variant_names'],
        'explicit_build_variant_decisions':counts['explicit_build_variant_decisions'],'components_with_any_identity_scope':counts['components_with_any_identity_scope']})
    u['updated_utc']=p['updated_utc']=now
    docs['root']['current_component_review']=copy.deepcopy(c)
    docs['root']['updated_utc']=now
    for k,v in before['walkthrough'].items():
        if k.startswith('current_') or k in ['proposed_name','answer_state','question_scope','next_review_after_keep','parallel_import_holds']:
            assert cp[k]==v,k
    for k,v in before['user'].items():
        if isinstance(v,list):
            assert u[k][:len(v)]==v,k
    for cid,prior in before['progress']['reviews'].items():
        if cid not in allowed_existing:
            assert p['reviews'][cid]==prior
        else:
            for key,value in prior.items():
                if key in ['build_variants','size_finish_variants']:
                    assert all(p['reviews'][cid][key][vid]==variant for vid,variant in value.items())
                else:
                    assert p['reviews'][cid][key]==value
    assert p['offer_photo_bindings']==before['progress']['offer_photo_bindings']
    assert all(sha(path)==hashes[k] for k,path in paths.items()) and all(sha(Path(path))==digest for path,digest in protected.items())
    write(here/'before-import.json',{'recorded_utc':now,'files':{rel(paths[k]):v for k,v in before.items()},'protected_sha256':protected})
    for path,value in outputs:
        write(path,value)
    for key,path in paths.items():
        write(path,docs[key])
        assert read(path)==docs[key]
    result={'status':'APPLIED_AND_VERIFIED',**summary,'imported':imported,'arrangement_approvals':arrangement_outputs,'resolved_positions':resolutions,
        'identity_counts':counts,'specification_counts':u['specification_approval_counts'],'source_files_frozen':len(manifest['files']),
        'transcript_messages_verified':len(manifest['verified_messages']),'protected_sha256':protected}
    write(receipt_path,result)
    event={'event_id':f'parallel-import:batch{number}:2026-10-19','event':'SCOPED_OWNER_REVIEW_PACKET_IMPORTED','recorded_utc':now,'receipt':rel(receipt_path),
        'new_specification_approval_inferred':False,'physical_specs_verified':False}
    for path in [REVIEWS/'identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event,ensure_ascii=False)+'\n')
    print(json.dumps({'status':result['status'],**summary,'identity_counts':counts}))


if __name__=='__main__':
    for batch in [9,10]:
        apply(batch)
