"""Stage the exact owner identity answers without transferring specifications."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from align_current_state import align

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p,x: Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not (H/'artifact-authoring-receipt.json').exists(), 'Workbook authoring freezes this import scope'
assert sha(B/'current-master.json') == '70dc1eb626e6d975b2edb2202ac0bb64a5d02eb51dcc87324697e8992df6b2b8'
p = read(B/'current-master.json')
paths = {'pointer':B/'current-master.json','master_register':B/p['register'],'master_workbook':B/p['workbook'],
    'coverage':B/p['latest_image_coverage_audit']['audit'],'group_projection':B/p['current_working_design_group_projection']['path'],
    'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json',
    'checkpoint':B/'checkpoint.json'}
(H/'inputs').mkdir(exist_ok=True)
manifest = {}
for key,path in paths.items():
    snapshot = H/'inputs'/(key+'.before')
    if not snapshot.exists():
        shutil.copy2(path,snapshot)
    assert sha(path) == sha(snapshot),key
    manifest[key] = {'path':str(path),'snapshot':str(snapshot),'sha256':sha(path)}
write(H/'input-manifest.json',manifest)
g = read(paths['master_register'])
before = copy.deepcopy(g)
audit = read(paths['coverage'])
audit_before = copy.deepcopy(audit)
options = {o['product_id']:o for o in g['options']}
legacy_id = 'BSI-04D6E8690F30'
current_id = 'BSI-FE10273D3655'
packets = []
source = B/'components/parallel-reviews/held-identities-terminal-review-20261025-B'
allowed_ids = {'LEGACY-FFL1-FFS2-RELIEF','WC-03-PATTERN','WC-06-PATTERN','WC-07-PATTERN'}
for seal_path in sorted(source.glob('answer-*/sealed-owner-answer.json')):
    seal = read(seal_path)
    assert seal['decision_id'] in allowed_ids
    for member in seal['files']:
        assert sha(member['path']) == member['sha256']
    answer = read(seal_path.parent/'owner-answer.json')
    assert answer['decision_id'] == seal['decision_id']
    assert answer['owner_message_provenance']['role'] == 'user'
    assert answer['owner_message_provenance']['thread_id'] == '01a13fe6-495b-7253-b923-31823b4cbca8'
    assert sha(answer['source_review']['path']) == answer['source_review']['sha256']
    packets.append({'seal':str(seal_path),'seal_sha256':sha(seal_path),'answer_path':str(seal_path.parent/'owner-answer.json'),
        'answer_sha256':sha(seal_path.parent/'owner-answer.json'),'answer':answer})
assert packets and len({x['answer']['decision_id'] for x in packets}) == len(packets)
field_wording_changes = []
for packet in packets:
    answer = packet['answer']
    decision = answer['decision_id']
    provenance = {k:packet[k] for k in ['seal','seal_sha256','answer_path','answer_sha256']}
    provenance.update(decision_id=decision,owner_answer_verbatim=answer['owner_answer_verbatim'],
        owner_message_provenance=answer['owner_message_provenance'])
    relationship = answer['accepted_relationship']
    if decision == 'LEGACY-FFL1-FFS2-RELIEF':
        assert answer['owner_answer_verbatim'] == 'Same design' and relationship['same_relief_design']
        legacy,current = options[legacy_id],options[current_id]
        assert legacy['master_fields'] == answer['source_legacy_fields_snapshot']
        assert legacy['canonical_component_id'] is None and current['canonical_component_id'] == 'BC-FFS-2'
        resolution = {**provenance,'status':'OWNER_CONFIRMED_SAME_RELIEF_DESIGN','same_design_as_option_id':current_id,
            'working_design_group_id':'BC-FFS-2','current_primary_photo_binding_changed':False,
            'scope':'Relief design relationship only. Historical source codes, option records and physical/commercial qualifications remain separate.'}
        legacy['owner_identity_resolution_history'] = {'before_identity_basis':legacy['identity_basis'],
            'before_count_class':legacy['count_class'],'before_record_type':legacy['record_type'],
            'before_master_fields':copy.deepcopy(legacy['master_fields'])}
        legacy.update(canonical_component_id='BC-FFS-2',record_type='LEGACY_NAMED_WORKING_OPTION_DESIGN_RELATIONSHIP_RESOLVED',
            identity_basis='Owner confirmed FFL1 and FFS2 are the same relief design. Historical FFL1 source code and separate working option retained; no new mould, specimen, SKU or exact variant claim.',
            count_class='Owner-confirmed existing FFS2 relief design; legacy source option retained',
            current_owner_identity_resolution=resolution,
            owner_confirmed_design_reference={k:current[k] for k in ['product_id','name','file_id','folder_id','image_url','folder_url']})
        legacy['owner_confirmed_design_reference']['reference_scope'] = 'Shared relief-design reference; no separate legacy cast photograph or exact historical size certified'
        legacy['photo_coverage']['individual'] = 'Shared design reference'
        legacy['selling_details']['identity_deferred'] = False
        legacy['selling_details']['customer_listing_readiness_changed'] = False
        replacements = {
            'Weight':'Approximately 4–6 kg — provisional comparison with 70 × 15 cm White Frozen Fish; actual cast weight remains unverified.',
            'Individual price':'£262.50 per individual panel — estimated price. Conditional on the 70 × 15 cm configuration; exact current platform offer remains unverified.',
            'Availability':'Made to order; lead time 1–2 weeks — owner instruction, 22 October 2026.'}
        for field,value in replacements.items():
            old = copy.deepcopy(legacy['master_fields'][field])
            legacy['master_fields'][field]['display'] = value
            if field == 'Individual price':
                legacy['master_fields'][field]['basis'] = old['basis'].replace('Legacy FFL1/FFS2 identity stays deferred and this row is not made sell-ready.',
                    'The owner confirms the FFL1/FFS2 relief relationship; this does not verify the exact current platform offer or make a new listing.')
            field_wording_changes.append({'option_id':legacy_id,'field':field,'before':old,'after':copy.deepcopy(legacy['master_fields'][field]),
                'numeric_value_or_physical_verification_changed':False})
        current['current_owner_legacy_design_relationship'] = {**provenance,'same_design_as_legacy_option_id':legacy_id,
            'scope':'Same relief only; no finish, specification or offer transfer.'}
        align(legacy,resolution,answer['recorded_utc'])
        edge = {**provenance,'edge_id':decision,'relationship':'OWNER_CONFIRMED_LEGACY_SAME_RELIEF_DESIGN',
            'owner_confirmed_option_ids':[legacy_id,current_id],'retained_component_ids':['BC-FFS-2'],
            'legacy_source_design_code':'BC-FFL-1','working_design_group_id':'BC-FFS-2',
            'previously_counted_identified_component_delta':0,'working_design_group_count_delta':0,
            'no_physical_mould_cast_or_specification_transfer':True}
        g['current_owner_design_equivalence_edges'].append(edge)
        projection = g['current_working_design_group_projection']
        projection['direct_owner_relationships'] += 1
        projection.setdefault('legacy_source_design_code_to_existing_working_group',{})['BC-FFL-1'] = 'BC-FFS-2'
        group = next(x for x in projection['groups'] if x['working_design_group_id'] == 'BC-FFS-2')
        group['active_option_ids'].append(legacy_id)
        group['owner_directly_confirmed_option_ids'] = [legacy_id,current_id]
        group['grouping_basis'] = 'Existing FFS2 component; owner confirms the separately retained legacy FFL1 source option uses the same relief design. No extra counted group.'
        component = next(x for x in g['components'] if x['component_id'] == 'BC-FFS-2')
        component['option_ids'].append(legacy_id)
        component['option_names'].append(legacy['name'])
        component['option_count'] += 1
        component['scope_note'] = group['grouping_basis']
        component.setdefault('legacy_source_design_relationships',[]).append(resolution)
        g['summary'].update(individual_options_on_identified_components=181,unresolved_legacy_frozen_fish_identity_records=0,
            owner_confirmed_design_equivalence_relationships=3)
        cov = next(x for x in audit['coverage'] if x['option_id'] == legacy_id)
        cov['previous_individual_identity_scope'] = copy.deepcopy(cov['individual'])
        cov['individual'].update(status='Shared design reference',basis=resolution['scope'],
            terminal_review_state='OWNER_DESIGN_RELATIONSHIP_RESOLVED_NO_SEPARATE_PHOTO_SELECTED',exact_option=False,
            owner_identity_resolution=resolution)
        cov['notes'] = ['Owner confirms FFL1 and FFS2 share the relief design. Current face stays70×15cm. Separate source/option records and physical/commercial qualifications retained.']
        audit['counts']['individual_statuses'].pop('Unbound identity')
        audit['counts']['individual_statuses']['Shared design reference'] = 1
        for key in ['legacy_frozen_identity_gaps','outstanding_individual_image_or_identity_actions']:
            audit['counts'][key] = 0
        audit['counts']['legacy_frozen_identity_review_deferred'] = False
        audit['counts']['actions_by_role']['Individual'] = 0
        audit['counts']['actions_by_type']['Verify existing image'] = 0
        audit['counts']['required_picture_actions'] = 23
        audit['counts']['resolved_action_rows'] += 1
        audit['counts']['active_action_rows'] -= 1
        for row in audit['identity_review']:
            if row.get('case_id') == 'ID-FROZEN-FISH-LONG':
                row['previous_owner_identity_scope'] = copy.deepcopy({k:row.get(k) for k in ['state','proposed_identity','check','owner_decision']})
                row.update(state='OWNER_CONFIRMED_SAME_RELIEF_DESIGN',proposed_identity='Same relief as Frozen Fish Two White (FFS2)',
                    check=resolution['scope'],owner_decision='Same design',owner_identity_resolution=resolution)
        for row in audit['missing_pictures']:
            if row.get('option_id') != legacy_id:
                continue
            row['current_owner_identity_resolution'] = resolution
            if row['role'] == 'Individual':
                row.update(status='Resolved — owner confirmed shared relief design',action_type='Resolved identity',
                    action='Retain the FFS2 image as a qualified shared-design reference. No separate legacy photo selected and no new capture request.',
                    qualification=resolution['scope'],owner_response='Same design',review_deferred_by_owner_scope=False,
                    terminal_review_state='OWNER_DESIGN_RELATIONSHIP_RESOLVED')
            else:
                row['action'] = 'Identity relationship resolved as FFS2. Existing context deferral and optional-series scope remain unchanged.'
    else:
        oid = relationship['product_id']
        option = options[oid]
        assert option['file_id'] == relationship['file_id'] and option['folder_id'] == relationship['folder_id']
        assert option['master_fields'] == answer['source_fields_snapshot']
        pattern = relationship['pattern_name']
        resolution = {**provenance,'status':'OWNER_CONFIRMED_PATTERN_NAME','pattern_name':pattern,
            'native_pattern_or_variant_id_assigned':None,'scope':'Exact presented appearance name only; no automatic alias to a native swatch or exact platform variant.'}
        option['owner_confirmed_pattern_name'] = pattern
        option['current_owner_pattern_resolution'] = resolution
        if relationship.get('catalogue_display_name'):
            previous_name = option['name']
            assert previous_name == relationship['previous_product_name']
            if previous_name not in option['retained_names']:
                option['retained_names'].append(previous_name)
            option['name'] = relationship['catalogue_display_name']
            option['owner_pattern_name_history'] = {'previous_name':previous_name,'owner_name':option['name'],'provenance':provenance}
            for key in ['current_listing_reconciliation','current_listing_resolution']:
                if isinstance(option.get(key),dict) and 'name' in option[key]:
                    option[key]['name'] = option['name']
            for key in ['coverage','missing_pictures']:
                for row in audit[key]:
                    if row.get('option_id') == oid:
                        row['name'] = option['name']
        option['readiness_note'] = 'Owner confirmed the exact pattern name. Existing native variant/configuration mapping and all physical/commercial field qualifications remain separate.'
        listing = option['current_listing_resolution']
        option['previous_pattern_question_listing_scope'] = copy.deepcopy(listing)
        listing.update(current_source_resolution_disposition='OWNER_NAMED_PATTERN_NATIVE_VARIANT_UNRESOLVED',
            next_action='Pattern name confirmed by owner. Check exact existing native variant/configuration separately before creation or publication; do not repeat this naming question.',
            owner_pattern_resolution=resolution)
        for row in audit['identity_review']:
            if oid in row.get('related_option_ids',[]):
                row['previous_pattern_question_scope'] = copy.deepcopy({k:row.get(k) for k in ['state','check','owner_decision']})
                row.update(state='Owner-confirmed pattern name; native variant mapping remains unverified',owner_decision=answer['owner_answer_verbatim'],
                    check=resolution['scope'],current_owner_pattern_resolution=resolution)
                row['name'] = option['name']

decisions = [{k:x[k] for k in ['seal','seal_sha256','answer_path','answer_sha256']} | {
    'decision_id':x['answer']['decision_id'],'owner_answer_verbatim':x['answer']['owner_answer_verbatim'],
    'accepted_relationship':x['answer']['accepted_relationship']} for x in packets]
summary = {'status':'PREPARED_EXACT_OWNER_IDENTITY_ANSWERS','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'decisions':decisions,'active_option_records':188,'retained_option_records':189,'retained_component_records':112,
    'working_design_groups':110,'new_physical_measurements':0,'new_exact_platform_matches':0,'new_selected_primary_images':0,
    'identity_wording_field_objects_updated':len(field_wording_changes),'all_other_working_field_objects_unchanged':1134-len(field_wording_changes),
    'physical_commercial_numeric_values_unchanged':True,'context_deferrals':22,'series_deferrals':1,'native_or_platform_writes':0,
    'remaining_owner_decision_ids':sorted(allowed_ids-{x['decision_id'] for x in decisions})}
g['latest_owner_identity_decision_import'] = summary
audit['latest_owner_identity_decision_import'] = summary
assert g['active_option_ids'] == before['active_option_ids'] and len(g['components']) == len(before['components']) == 112
assert g['original_review_specification_assertions'] == before['original_review_specification_assertions']
assert audit['counts']['in_situ_statuses'] == audit_before['counts']['in_situ_statuses']
assert audit['counts']['series_statuses'] == audit_before['counts']['series_statuses']
write(H/'canonical-master-register.json',g)
write(H/'image-coverage-current.json',audit)
write(H/'working-design-group-projection.json',g['current_working_design_group_projection'])
write(H/'import-summary.json',summary)
write(H/'approved-packets.json',decisions)
write(H/'identity-wording-field-changes.json',field_wording_changes)
print(json.dumps({'status':summary['status'],'decisions':[x['decision_id'] for x in decisions],
    'active_options':188,'component_records':112,'working_groups':110,'field_identity_wording_changes':len(field_wording_changes)},indent=2))
