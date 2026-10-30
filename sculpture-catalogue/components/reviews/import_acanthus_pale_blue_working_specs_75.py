"""Import the exact Pale Blue and White working approval and one-file context."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from import_moonphase_silver_working_specs_62 import ROOT, PATHS, read, sha, rel, write, specification_counts
from import_source_followups_24_25 import canonical_messages

HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch75'
SOURCE = ROOT / 'components/parallel-reviews/acanthus-two-leaves-pale-blue-white-working-specs-2026-10-20/owner-working-specs-keep'
CID, VID = 'BC-AC-TWO', 'AC-TWO-PALE-BLUE-WHITE'

def main():
    docs = {k: read(v) for k, v in PATHS.items()}
    if (HERE / 'import-receipt.json').exists():
        assert docs['progress']['reviews'][CID]['size_finish_variants'][VID]['all_six_working_specification_fields_accepted']
        print(json.dumps({'batch': 75, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    before = copy.deepcopy(docs); guards = {k: sha(v) for k, v in PATHS.items()}; files = []
    def freeze(path, digest):
        path = Path(path); assert sha(path) == digest, str(path)
        dest = HERE / 'sources' / (digest + path.suffix); dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert sha(dest) == digest
        else: dest.write_bytes(path.read_bytes())
        item = {'source': str(path), 'snapshot': rel(dest), 'sha256': digest}
        if item not in files: files.append(item)
        return rel(dest)
    package_path = SOURCE / 'IMPORT_PACKAGE.json'; freeze(package_path, '893bb05663d50ecebfe9c4674dff184fb21e22796f504184093e12065d69422d'); pkg = read(package_path)
    freeze(pkg['manifest']['path'], pkg['manifest']['sha256'])
    for item in read(pkg['manifest']['path'])['files']: freeze(item['path'], item['sha256'])
    assert sha(pkg['decision']['path']) == '064b475e032f0ea45942855720de67593c95c3abd6ae5a003f20dfd919b99c8a'; decision = read(pkg['decision']['path'])
    evidence = [decision['preceding_review_card_evidence'], decision['authoritative_user_evidence']]
    messages = canonical_messages([x | {'transcript': x['transcript_path']} for x in evidence], pkg['source_owner_session'])
    assert [x['line'] for x in messages] == [28814, 28844] and messages[1]['immediately_preceding_assistant']['line'] == 28814
    assert messages[1]['text'] == 'Yes: Keep these six working specifications for Acanthus Two Leaves — Pale Blue and White, with the estimates, proposals and unknowns still labelled'
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component']); node = p['reviews'][CID]['size_finish_variants'][VID]
    assert docs['root']['current_component_review'] == c and cp['last_parallel_import']['batch'] == 74 and node['identity_confirmed'] and not node['proposals_approved']
    assert node['specification_proposals'] == decision['source_specification_proposals_retained']
    assert decision['source_specifications_retained'] == read(decision['source_review_before_answer']['path'])['specifications']
    heads = {x[x['metadata_type']]['id']: x[x['metadata_type']] for x in read(HERE / 'current-reference-check.json')['metadata']}; ref = node['current_dropbox_reference']; head, folder = heads[ref['file_id']], heads[ref['folder_id']]
    assert head['rev'] == ref['file_revision'] and head['size'] == ref['file_bytes'] and head['path_display'] == ref['file_path'] and folder['path_display'] == ref['folder_path']
    context_ref = pkg['context_output_update']; freeze(context_ref['path'], '25e39ecca7bba04ebc3b4226c544238e6a88cdd87b659c26866027a763a4f568'); context = read(context_ref['path']); ctx = context['context_images']; binding_ref = ctx['source_binding']; freeze(binding_ref['path'], binding_ref['sha256']); binding = read(binding_ref['path']); source = binding['source']; cached = source['cached_original']
    freeze(cached['path'], cached['sha256']); raw = Path(cached['path']).read_bytes(); assert len(raw) == head['size'] == source['original_bytes'] and head['rev'] == source['file_revision'] and head['path_display'].rsplit('/', 1)[0] == folder['path_display']
    blocks = b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0, len(raw), 4194304)); assert hashlib.sha256(blocks).hexdigest() == source['baseline_original_dropbox_hash']
    freeze(binding['current_metadata']['path'], binding['current_metadata']['sha256']); freeze(binding['prior_source']['path'], binding['prior_source']['sha256']); freeze(HERE / 'current-reference-check.json', sha(HERE / 'current-reference-check.json'))
    protected = {str(path): sha(path) for path in [ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'working-specification-approval.json'); fields = decision['approved_field_groups']; assert len(fields) == 6 and set(fields) == set(decision['specifications']); ids = [VID + ':' + field.upper() for field in fields]
    decision.update({'source_approved_proposal_ids': copy.deepcopy(decision['approved_proposal_ids']), 'approved_proposal_ids': ids, 'approval_record': approval, 'imported_utc': now, 'authoritative_user_evidence': messages[1], 'verified_review_card_evidence': messages[0], 'shared_master_import_performed': True, 'context_evidence_imported_once': True})
    assert not any(x.get('decision_id') == decision['decision_id'] for x in u['size_finish_variant_specification_decisions']); u['size_finish_variant_specification_decisions'].append(decision); u['specification_approval_counts'] = specification_counts(u)
    assert u['specification_approval_counts']['proposal_groups'] == before['user']['specification_approval_counts']['proposal_groups'] + 6 == 124
    accepted = copy.deepcopy(decision['specifications'])
    for field, item in accepted.items(): item['proposal_id'] = VID + ':' + field.upper()
    node.update({'specifications_approved': True, 'proposals_approved': True, 'owner_estimates_accepted': True, 'source_claims_accepted_as_working': True, 'all_six_working_specification_fields_accepted': True, 'approved_proposal_ids': ids, 'specification_approval': approval, 'working_specifications_approval_scope': 'EXACT_FINISH_ALL_SIX_WORKING_VALUES', 'accepted_working_specifications': accepted, 'source_specifications_retained': decision['source_specifications_retained'], 'source_specification_proposals_retained_unchanged': True, 'physical_specs_verified': False, 'actual_stock_verified': False, 'fully_confirmed_specification_groups': [], 'current_public_selling_price_verified': False, 'specification_status_display': 'Six working specifications accepted; estimates, proposals and unknowns retained', 'scope': decision['scope'] + ' Existing White and Bronze working approvals remain separate. Original source snapshots retain historical flags; current owner acceptance is the working overlay.'})
    context_record = rel(HERE / 'context-evidence.json'); photo = copy.deepcopy(node.get('photo_coverage', {})); photo.update({'on_wall': True, 'contextual_images_available': True, 'contextual_source_status': 'Available: close individual on-wall image', 'contextual_source_description': ctx['type'] + '. ' + ctx['limitations'], 'contextual_file_ids': [ctx['representative_file_id']], 'individual_wider_room_established': False, 'series_imagery_established': False, 'rear_reference_established': False, 'installation_provenance': 'UNCONFIRMED', 'exact_physical_cast_identity_verified': False, 'root_evidence_kind': 'ONE_CACHED_ORIGINAL_REHASHED;NO_NEW_DOWNLOAD', 'evidence_record': context_record})
    node.update({'photo_coverage': photo, 'context_output_review': context_record}); assert VID not in p['current_component_photograph_gaps']
    gap = {'component_id': CID, 'size_finish_variant_id': VID, 'canonical_name': node['canonical_name'], 'finish': 'Pale Blue and White', 'front': 'Complete individual front source001 linked; cached original rehashed.', 'room': 'Close individual on-wall image available; wider-room view not established in this one-file folder, elsewhere unknown.', 'series': 'No series scene established in the one-file folder; availability elsewhere unknown.', 'evidence': ctx['limitations'], 'missing': 'Rear/fixing, calibrated side/profile, wider-room and series pictures not established in this one-file folder; elsewhere unknown.', 'review_record': context_record}; p['current_component_photograph_gaps'][VID] = gap
    context.update({'root_imported_utc': now, 'root_current_reference_check': rel(HERE / 'current-reference-check.json'), 'root_cached_original_visually_inspected_and_rehashed': True, 'root_new_private_original_downloads': 0, 'new_owner_approval_from_context': False, 'shared_master_import_performed': True})
    p.setdefault('pending_specification_checks', {})[VID + '-WORKING-SPECS-01'] = {'owner_answer_recorded': True, 'approval_record': approval, 'working_values_accepted': True, 'actual_specification_fields_pending': fields, 'physical_specs_verified': False}; c['interactive_review_state']['approved_proposal_groups'] = 124
    summary = {'batch': 75, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'EXACT_PALE_BLUE_WHITE_SIX_WORKING_FIELDS_AND_ONE_FILE_CONTEXT', 'component_id': CID, 'size_finish_variant_id': VID, 'new_working_specification_approvals': 1, 'new_accepted_working_proposal_groups': 6, 'new_physically_verified_specification_groups': 0, 'new_name_approvals': 0, 'new_owner_policy_events': 0, 'new_registered_BC_component_ids': [], 'new_photo_gap_rows': 1, 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(package_path), 'receipt_sha256': sha(package_path), 'approval_imported': True, 'evidence_imported': True, 'import_receipt': summary['receipt'], 'status': 'SIX_WORKING_FIELDS_ACCEPTED;EXACT_CONTEXT_IMPORTED_ONCE;ACTUAL_DETAILS_UNVERIFIED'}); c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
    for doc in docs.values(): doc['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    assert node['specification_proposals'] == before['progress']['reviews'][CID]['size_finish_variants'][VID]['specification_proposals'] and all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_'))
    assert all(sha(PATHS[k]) == v for k, v in guards.items()) and all(sha(path) == v for path, v in protected.items())
    write(HERE / 'before-import.json', before); write(HERE / 'working-specification-approval.json', decision); write(HERE / 'context-evidence.json', context); write(HERE / 'photo-gap.json', gap); write(HERE / 'source-manifest.json', {'files': files, 'verified_messages': messages})
    for k, path in PATHS.items(): write(path, docs[k])
    write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'decision_id': decision['decision_id'], 'protected_sha256': protected, 'shared_after_sha256': {k: sha(v) for k, v in PATHS.items()}})
    print(json.dumps({'batch': 75, 'status': 'APPLIED', 'accepted_working_field_groups': 124, 'actual_specs_verified': False, 'root_commercial_question_preserved': True}))

if __name__ == '__main__': main()
