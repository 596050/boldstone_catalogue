"""Import one Bronze working approval and two bounded evidence updates."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from import_moonphase_silver_working_specs_62 import ROOT, PATHS, read, sha, rel, write, specification_counts
from import_source_followups_24_25 import canonical_messages

HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch74'
SOURCE = ROOT / 'components/parallel-reviews/acanthus-two-leaves-bronze-working-specs-2026-10-20/owner-working-specs-keep'
FFL = ROOT / 'components/parallel-reviews/frozen-fish-long-source-gap-2026-10-20/EVIDENCE_RECONCILIATION.json'
CID, VID = 'BC-AC-TWO', 'AC-TWO-BRONZE'

def main():
    docs = {k: read(v) for k, v in PATHS.items()}
    if (HERE / 'import-receipt.json').exists():
        assert docs['progress']['reviews'][CID]['size_finish_variants'][VID]['all_six_working_specification_fields_accepted']
        assert docs['progress']['source_only_gap_reviews']['BC-FFL-1']['mapping_confirmed'] is False
        print(json.dumps({'batch': 74, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    before = copy.deepcopy(docs); guards = {k: sha(v) for k, v in PATHS.items()}; files = []
    def freeze(path, digest):
        path = Path(path); assert sha(path) == digest, str(path)
        dest = HERE / 'sources' / (digest + path.suffix); dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert sha(dest) == digest
        else: dest.write_bytes(path.read_bytes())
        entry = {'source': str(path), 'snapshot': rel(dest), 'sha256': digest}
        if entry not in files: files.append(entry)
        return rel(dest)
    package_path = SOURCE / 'IMPORT_PACKAGE.json'
    freeze(package_path, 'cd4184a38d84d751c36d4542ee9a5b3f4bdc9024f12d39fa90c3a1e2f58e00b8'); pkg = read(package_path)
    freeze(pkg['manifest']['path'], pkg['manifest']['sha256'])
    for item in read(pkg['manifest']['path'])['files']: freeze(item['path'], item['sha256'])
    assert sha(pkg['decision']['path']) == '3af20b840fa1f5eae9567bb865d79fd462e0e3894ce1c48864e53d76925a6a59'
    decision = read(pkg['decision']['path'])
    evidence = [decision['preceding_review_card_evidence'], decision['authoritative_user_evidence']]
    messages = canonical_messages([x | {'transcript': x['transcript_path']} for x in evidence], pkg['source_owner_session'])
    assert [x['line'] for x in messages] == [28639, 28701]
    assert messages[1]['text'] == 'Yes: Keep these six working specifications for Acanthus Two Leaves — Bronze, with the source claims, estimate, proposal and unknowns still labelled'
    assert messages[1]['immediately_preceding_assistant']['line'] == 28639
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component']); node = p['reviews'][CID]['size_finish_variants'][VID]
    assert docs['root']['current_component_review'] == c and cp['last_parallel_import']['batch'] == 73
    assert node['identity_confirmed'] and not node['proposals_approved'] and node['specification_proposals'] == decision['source_specification_proposals_retained']
    assert decision['source_specifications_retained'] == read(decision['source_review_before_answer']['path'])['specifications']
    heads = {x[x['metadata_type']]['id']: x[x['metadata_type']] for x in read(HERE / 'current-reference-check.json')['metadata']}
    ref = node['current_dropbox_reference']; primary, folder = heads[node['primary_image_id']], heads[node['primary_folder_id']]
    assert primary['rev'] == ref['file_revision'] and primary['size'] == ref['file_bytes'] and primary['path_display'] == ref['file_path'] and folder['path_display'] == ref['folder_path']
    context_ref = pkg['context_output_update']; freeze(context_ref['path'], 'a49b047c247866ca1cc33aae513efc72ef43eaf66a841f2d60ec9356662e26a4')
    context = read(context_ref['path']); ctx = context['context_images']; binding_ref = ctx['source_binding']; freeze(binding_ref['path'], binding_ref['sha256']); binding = read(binding_ref['path'])
    assert len(binding['sources']) == 6
    for item in binding['sources']:
        cached = item['cached_image']; freeze(cached['path'], cached['sha256']); head = heads[item['file_id']]
        assert head['size'] == item['remote_original_bytes'] and head['name'] == item['name'] and head['path_display'].rsplit('/', 1)[0] == folder['path_display']
        if item['cache_kind'] == 'original':
            raw = Path(cached['path']).read_bytes(); assert len(raw) == head['size'] and head['rev'] == item['current_file_metadata']['rev']
            blocks = b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0, len(raw), 4194304))
            assert hashlib.sha256(blocks).hexdigest() == item['baseline_original_dropbox_hash']
        else: assert item['cache_kind'] == 'thumbnail' and not item['original_bytes_rehashed_this_turn']
    freeze(HERE / 'bronze-context-contact-sheet.jpg', sha(HERE / 'bronze-context-contact-sheet.jpg'))
    freeze(FFL, 'd072ad301bbffd5545d6929c69850c03ca4a7674292e2d01b40ead9b31884b1b'); long_gap = read(FFL)
    def referenced(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str) and value.get('sha256'): freeze(value['path'], value['sha256'])
            for child in value.values(): referenced(child)
        elif isinstance(value, list):
            for child in value: referenced(child)
    referenced(long_gap)
    assert long_gap['search_findings']['registered_frozen_fish_groups_checked'] == 7 and long_gap['search_findings']['registered_frozen_fish_assets_metadata_checked'] == 96
    assert long_gap['search_findings']['maker_solo_row_same_picture_for_both_sizes'] and not long_gap['search_findings']['mapped_FFL_asset_folder_or_offer'] and not long_gap['identity_card_created']
    freeze(HERE / 'current-reference-check.json', sha(HERE / 'current-reference-check.json'))
    protected = {str(path): sha(path) for path in [ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'working-specification-approval.json'); fields = decision['approved_field_groups']
    assert len(fields) == 6 and set(fields) == set(decision['specifications'])
    ids = [VID + ':' + field.upper() for field in fields]
    decision.update({'source_approved_proposal_ids': copy.deepcopy(decision['approved_proposal_ids']), 'approved_proposal_ids': ids, 'approval_record': approval, 'imported_utc': now, 'authoritative_user_evidence': messages[1], 'verified_review_card_evidence': messages[0], 'shared_master_import_performed': True, 'context_evidence_imported_once': True})
    assert not any(x.get('decision_id') == decision['decision_id'] for x in u['size_finish_variant_specification_decisions'])
    u['size_finish_variant_specification_decisions'].append(decision); u['specification_approval_counts'] = specification_counts(u)
    assert u['specification_approval_counts']['proposal_groups'] == before['user']['specification_approval_counts']['proposal_groups'] + 6 == 118
    accepted = copy.deepcopy(decision['specifications'])
    for field, item in accepted.items(): item['proposal_id'] = VID + ':' + field.upper()
    node.update({'specifications_approved': True, 'proposals_approved': True, 'owner_estimates_accepted': True, 'source_claims_accepted_as_working': True, 'all_six_working_specification_fields_accepted': True, 'approved_proposal_ids': ids, 'specification_approval': approval, 'working_specifications_approval_scope': 'EXACT_FINISH_ALL_SIX_WORKING_VALUES', 'accepted_working_specifications': accepted, 'source_specifications_retained': decision['source_specifications_retained'], 'source_specification_proposals_retained_unchanged': True, 'physical_specs_verified': False, 'actual_stock_verified': False, 'fully_confirmed_specification_groups': [], 'current_public_selling_price_verified': False, 'specification_status_display': 'Six working specifications accepted; source claims, weight guess and unknowns retained', 'scope': decision['scope'] + ' Existing White working approval and all other finishes remain separate. Source snapshots retain historical unapproved flags; current acceptance is the working overlay.'})
    context_record = rel(HERE / 'bronze-context-evidence.json')
    photo = copy.deepcopy(node.get('photo_coverage', {})); photo.update({'on_wall': True, 'contextual_images_available': True, 'contextual_source_status': 'Available: close individual on-wall views and rear reference', 'contextual_source_description': ctx['type'] + '. ' + ctx['limitations'], 'contextual_file_ids': [ctx['representative_file_id'], ctx['rear_reference_file_id']], 'rear_reference_file_id': ctx['rear_reference_file_id'], 'individual_wider_room_established': False, 'series_imagery_established': False, 'installation_provenance': 'UNCONFIRMED', 'exact_physical_cast_identity_verified': False, 'root_evidence_kind': '001_AND_006_CACHED_ORIGINALS_REHASHED;002_TO_005_THUMBNAILS', 'evidence_record': context_record})
    node.update({'photo_coverage': photo, 'context_output_review': context_record})
    assert VID not in p['current_component_photograph_gaps']
    gap = {'component_id': CID, 'size_finish_variant_id': VID, 'canonical_name': node['canonical_name'], 'finish': 'Bronze', 'front': 'Complete individual front source001 linked; cached original rehashed.', 'room': 'Close individual on-wall views available. Dedicated wider-room view not established among six direct-child images; elsewhere unknown.', 'series': 'No series scene established among these six; availability elsewhere unknown.', 'evidence': ctx['limitations'], 'missing': 'Wider-room and series images, calibrated side/profile and exact cast binding to rear006 not established; rear reference exists, load rating unknown.', 'review_record': context_record}
    p['current_component_photograph_gaps'][VID] = gap
    context.update({'root_imported_utc': now, 'root_current_reference_check': rel(HERE / 'current-reference-check.json'), 'root_all_six_cached_views_visually_inspected': True, 'root_originals_rehashed': [ctx['representative_file_id'], ctx['rear_reference_file_id']], 'root_new_private_original_downloads': 0, 'new_owner_approval_from_context': False, 'shared_master_import_performed': True})
    ffl_record = rel(HERE / 'frozen-fish-long-evidence.json')
    p.setdefault('source_only_gap_reviews', {})['BC-FFL-1'] = {'component_id': 'BC-FFL-1', 'canonical_name': 'Frozen Fish Long (FFL1)', 'status': long_gap['status'], 'mapping_confirmed': False, 'historical_size_cm': [100, 22], 'historical_depth_cm': [5, 7], 'groups_checked': 7, 'asset_metadata_checked': 96, 'maker_same_picture_for_short_and_long': True, 'stable_dropbox_file_id': None, 'stable_dropbox_folder_id': None, 'source_offer_match_confirmed': False, 'evidence_record': ffl_record, 'evidence_needed': long_gap['evidence_still_needed'], 'absence_claimed': False, 'new_owner_decisions': 0}
    p.setdefault('pending_specification_checks', {})[VID + '-WORKING-SPECS-01'] = {'owner_answer_recorded': True, 'approval_record': approval, 'working_values_accepted': True, 'actual_specification_fields_pending': fields, 'physical_specs_verified': False}
    c['interactive_review_state']['approved_proposal_groups'] = 118
    summary = {'batch': 74, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'EXACT_BRONZE_SIX_WORKING_FIELDS_AND_CONTEXT;FFL_BOUNDED_SOURCE_GAP', 'component_id': CID, 'size_finish_variant_id': VID, 'new_working_specification_approvals': 1, 'new_accepted_working_proposal_groups': 6, 'new_physically_verified_specification_groups': 0, 'new_name_approvals': 0, 'new_owner_policy_events': 0, 'new_registered_BC_component_ids': [], 'new_photo_gap_rows': 2, 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(package_path), 'receipt_sha256': sha(package_path), 'approval_imported': True, 'evidence_imported': True, 'import_receipt': summary['receipt'], 'status': 'BRONZE_SIX_WORKING_FIELDS_ACCEPTED;CONTEXT_IMPORTED_ONCE;FFL_SOURCE_GAP_RETAINED'})
    for item in cp.get('parallel_source_reconciliation_reviews', []):
        if item.get('component_id') == 'BC-FFL-1': item.update({'status': 'BOUNDED_SOURCE_GAP_RECONCILED;EXACT_LONG_IMAGE_UNBOUND', 'evidence_record': ffl_record, 'identity_card_created': False})
    c['parallel_source_reconciliation_reviews'] = copy.deepcopy(cp.get('parallel_source_reconciliation_reviews', []))
    c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
    for doc in docs.values(): doc['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    assert node['specification_proposals'] == before['progress']['reviews'][CID]['size_finish_variants'][VID]['specification_proposals']
    assert all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_')) and all(sha(PATHS[k]) == v for k, v in guards.items()) and all(sha(path) == v for path, v in protected.items())
    write(HERE / 'before-import.json', before); write(HERE / 'working-specification-approval.json', decision); write(HERE / 'bronze-context-evidence.json', context); write(HERE / 'bronze-photo-gap.json', gap); write(HERE / 'frozen-fish-long-evidence.json', long_gap); write(HERE / 'source-manifest.json', {'files': files, 'verified_messages': messages})
    for k, path in PATHS.items(): write(path, docs[k])
    write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'decision_id': decision['decision_id'], 'protected_sha256': protected, 'shared_after_sha256': {k: sha(v) for k, v in PATHS.items()}})
    print(json.dumps({'batch': 74, 'status': 'APPLIED', 'accepted_working_field_groups': 118, 'actual_specs_verified': False, 'FFL_mapping_unconfirmed': True}))

if __name__ == '__main__': main()
