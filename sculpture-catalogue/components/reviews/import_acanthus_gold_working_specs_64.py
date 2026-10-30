"""Apply an exact six-field working Keep while preserving source and context records."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from import_source_followups_24_25 import canonical_messages
from import_moonphase_silver_working_specs_62 import ROOT, PATHS, read, sha, rel, write, specification_counts

HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch64'
SOURCE = ROOT / 'components/parallel-reviews/acanthus-gold-finish-2026-10-19/working-specification-review/owner-working-specs-keep'
CID, VID = 'BC-AC-FULL', 'AC-FULL-GOLD-LEAF'

def main():
    docs = {key: read(path) for key, path in PATHS.items()}
    if (HERE / 'import-receipt.json').exists():
        assert docs['progress']['reviews'][CID]['size_finish_variants'][VID]['all_six_working_specification_fields_accepted']
        print(json.dumps({'batch': 64, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    before, guards = copy.deepcopy(docs), {key: sha(path) for key, path in PATHS.items()}
    files = []
    def freeze(path, digest):
        assert sha(path) == digest, str(path)
        dest = HERE / 'sources' / (digest + __import__('pathlib').Path(path).suffix); dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert sha(dest) == digest
        else: dest.write_bytes(__import__('pathlib').Path(path).read_bytes())
        files.append({'source': str(path), 'snapshot': rel(dest), 'sha256': digest}); return rel(dest)
    package_path = SOURCE / 'IMPORT_PACKAGE.json'; digest = '631db58caaa66f74cdb10e16b5d251bca4146802ac214128386961636747d0e2'
    freeze(package_path, digest); package = read(package_path)
    freeze(package['manifest']['path'], package['manifest']['sha256'])
    for item in read(package['manifest']['path'])['files']: freeze(item['path'], item['sha256'])
    assert sha(package['decision']['path']) == '541c3bf05b01868053bd5f52a827c2542ee9da3d0f2b258c90fbfe544a13ec3f'
    decision = read(package['decision']['path'])
    messages = canonical_messages([item | {'transcript': item['transcript_path']} for item in [decision['preceding_review_card_evidence'], decision['authoritative_user_evidence']]], package['source_owner_session'])
    assert [item['line'] for item in messages] == [28051, 28058]
    literal = 'Keep these six working specifications for Acanthus and Moon — Gold Leaf, with the source claims, proposal and unknowns still labelled?'
    assert messages[-1]['text'] == literal and literal in messages[0]['text'] and 'acanthus-and-moon-gold-leaf__001.jpg' in messages[0]['text']
    u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component']); node = p['reviews'][CID]['size_finish_variants'][VID]
    assert docs['root']['current_component_review'] == c and cp['last_parallel_import']['batch'] == 63 and node['identity_confirmed'] and not node['proposals_approved']
    assert node['specification_proposals'] == decision['prior_catalogue_specifications_retained']
    presented = read(decision['source_review_before_answer']['path'])
    assert presented['specifications'] == decision['source_specifications_retained'] and len(presented['specifications']) == 6
    assert all(not item['owner_approved'] for item in node['specification_proposals'].values())
    heads = read(HERE / 'current-reference-check.json')['metadata']; head = heads[0]['file']; folder = heads[1]['folder']; ref = node['current_dropbox_reference']
    assert all(head[key] == ref[target] for key, target in [('id', 'file_id'), ('rev', 'file_revision'), ('size', 'file_bytes'), ('path_display', 'file_path')]) and folder['id'] == ref['folder_id'] and folder['path_display'] == ref['folder_path']
    original = ROOT / node['root_verified_cached_original']['snapshot']; content = original.read_bytes()
    assert len(content) == head['size'] and sha(original) == node['root_verified_cached_original']['sha256']
    blocks = b''.join(hashlib.sha256(content[index:index+4194304]).digest() for index in range(0, len(content), 4194304))
    assert hashlib.sha256(blocks).hexdigest() == node['root_verified_cached_original']['dropbox_content_hash']
    freeze(original, sha(original)); freeze(HERE / 'current-reference-check.json', sha(HERE / 'current-reference-check.json'))
    protected = {str(path): sha(path) for path in [ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'working-specification-approval.json')
    fields = decision['approved_field_groups']; assert len(fields) == 6 and set(fields) == set(decision['specifications'])
    scoped_ids = [VID + ':' + field.upper() for field in fields]
    decision.update({'source_approved_proposal_ids': copy.deepcopy(decision['approved_proposal_ids']), 'approved_proposal_ids': scoped_ids, 'approval_record': approval, 'imported_utc': now, 'authoritative_user_evidence': messages[-1], 'verified_review_card_evidence': messages[0], 'shared_master_import_performed': True})
    assert not any(item.get('decision_id') == decision['decision_id'] for item in u['size_finish_variant_specification_decisions'])
    u['size_finish_variant_specification_decisions'].append(decision); u['specification_approval_counts'] = specification_counts(u)
    assert u['specification_approval_counts']['proposal_groups'] == before['user']['specification_approval_counts']['proposal_groups'] + 6 == 94
    accepted = copy.deepcopy(decision['specifications'])
    for field, item in accepted.items(): item['proposal_id'] = VID + ':' + field.upper()
    node.update({'specifications_approved': True, 'proposals_approved': True, 'owner_estimates_accepted': True, 'source_claims_accepted_as_working': True, 'all_six_working_specification_fields_accepted': True, 'approved_proposal_ids': scoped_ids, 'specification_approval': approval, 'working_specifications_approval_scope': 'EXACT_FINISH_ALL_SIX_WORKING_VALUES', 'accepted_working_specifications': accepted, 'source_specification_proposals_retained_unchanged': True, 'physical_specs_verified': False, 'actual_stock_verified': False, 'fully_confirmed_specification_groups': [], 'specification_status_display': 'Six working specifications accepted; source claims, proposal and unknowns retained', 'scope': decision['scope'] + ' Prior name approval, individual and room image IDs, physical-cast and installation limits retained. This working acceptance does not verify the exact material, load capacity, actual stock or current sale offer.'})
    p.setdefault('pending_specification_checks', {})[VID + '-WORKING-SPECS-01'] = {'owner_answer_recorded': True, 'approval_record': approval, 'working_values_accepted': True, 'actual_specification_fields_pending': fields, 'physical_specs_verified': False}
    c['interactive_review_state']['approved_proposal_groups'] = 94
    summary = {'batch': 64, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'EXACT_ACANTHUS_GOLD_SIX_WORKING_SPECIFICATIONS', 'component_id': CID, 'size_finish_variant_id': VID, 'new_working_specification_approvals': 1, 'new_accepted_working_proposal_groups': 6, 'new_physically_verified_specification_groups': 0, 'new_name_approvals': 0, 'new_owner_policy_events': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(package_path), 'receipt_sha256': digest, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'SIX_WORKING_VALUES_ACCEPTED;SOURCE_PROPOSAL_UNKNOWN_LABELS_RETAINED;ACTUAL_DETAILS_UNVERIFIED'})
    c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
    for doc in docs.values(): doc['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    assert node['specification_proposals'] == before['progress']['reviews'][CID]['size_finish_variants'][VID]['specification_proposals']
    assert node['photo_coverage'] == before['progress']['reviews'][CID]['size_finish_variants'][VID]['photo_coverage']
    assert all(cp[key] == value for key, value in before['walkthrough'].items() if key.startswith('current_'))
    assert all(sha(PATHS[key]) == value for key, value in guards.items()) and all(sha(path) == value for path, value in protected.items())
    write(HERE / 'before-import.json', before); write(HERE / 'working-specification-approval.json', decision); write(HERE / 'accepted-working-review.json', node); write(HERE / 'source-manifest.json', {'files': files, 'verified_messages': messages})
    for key, path in PATHS.items(): write(path, docs[key])
    write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'decision_id': decision['decision_id'], 'protected_sha256': protected, 'shared_after_sha256': {key: sha(path) for key, path in PATHS.items()}})
    print(json.dumps({'batch': 64, 'status': 'APPLIED', 'accepted_working_field_groups': 94, 'actual_specs_verified': False, 'context_and_other_Acanthus_scopes_unchanged': True, 'root_count_question_preserved': True}))

if __name__ == '__main__': main()
