"""Import exact Silver working acceptance and two-image Acanthus context evidence."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'components/scripts'))
from review_decision_counts import specification_counts
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch62'
SOURCE = ROOT / 'components/parallel-reviews/moonphase-four-silver-2026-10-19/working-specification-review/owner-working-specs-keep'
CONTEXT = ROOT / 'components/parallel-reviews/acanthus-gold-finish-2026-10-19/working-specification-review/CONTEXT_OUTPUT_UPDATE.json'
DESIGN, VARIANT = 'MOONPHASE-CURRENT-4', 'MOONPHASE-CURRENT-4:SILVER'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
rel = lambda path: str(Path(path).relative_to(ROOT))
PATHS = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}

def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

def main():
    docs = {key: read(path) for key, path in PATHS.items()}
    if (HERE / 'import-receipt.json').exists():
        assert docs['progress']['catalogue_alias_reviews'][VARIANT]['all_six_working_specification_fields_accepted']
        print(json.dumps({'batch': 62, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    before, guards = copy.deepcopy(docs), {key: sha(path) for key, path in PATHS.items()}
    files = []
    def freeze(path, expected):
        path = Path(path); assert sha(path) == expected, str(path)
        dest = HERE / 'sources' / (expected + path.suffix); dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert sha(dest) == expected
        else: dest.write_bytes(path.read_bytes())
        files.append({'source': str(path), 'snapshot': rel(dest), 'sha256': expected}); return rel(dest)
    package_path = SOURCE / 'IMPORT_PACKAGE.json'; digest = '35ac646f848dadd460304d7eff9acdc3fa392a4eedd13153329af5657ad8920d'
    freeze(package_path, digest); package = read(package_path)
    freeze(package['manifest']['path'], package['manifest']['sha256'])
    for item in read(package['manifest']['path'])['files']: freeze(item['path'], item['sha256'])
    assert sha(package['decision']['path']) == 'f4b623340c428f94ac8bb7dfd2b11ac39cc5efa623f69c57ff0f994f44c5e958'
    decision = read(package['decision']['path'])
    messages = canonical_messages([item | {'transcript': item['transcript_path']} for item in [decision['preceding_review_card_evidence'], decision['authoritative_user_evidence']]], package['source_owner_session'])
    assert [item['line'] for item in messages] == [27819, 27839]
    assert messages[-1]['text'] == 'Keep these six working specifications for Moonphase Four — Silver (MP4)'
    assert '__001.jpg' in messages[0]['text'] and 'with the listing claims and unknown details still labelled' in messages[0]['text']
    u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == c and cp['last_parallel_import']['batch'] == 61
    node = p['catalogue_alias_reviews'][VARIANT]; assert node['identity_confirmed'] and not node['proposals_approved']
    source_items = {item['id']: item for item in decision['source_specification_review_items_retained']}
    assert len(node['specification_proposals']) == len(source_items) == 6
    assert all(item['display'] == source_items[item['proposal_id']]['display'] and not item['owner_approved'] for item in node['specification_proposals'])
    metadata = read(HERE / 'current-reference-check.json')['metadata']; heads = {item[item['metadata_type']]['id']: item[item['metadata_type']] for item in metadata}
    head, folder = heads[node['primary_image_id']], heads[node['primary_folder_id']]; ref = node['current_dropbox_reference']
    assert all(head[key] == ref[target] for key, target in [('id', 'file_id'), ('rev', 'file_revision'), ('size', 'file_bytes'), ('path_display', 'file_path')]) and folder['path_display'] == ref['folder_path']
    original = ROOT / node['root_verified_cached_original']['snapshot']; content = original.read_bytes()
    assert len(content) == head['size'] and sha(original) == node['root_verified_cached_original']['sha256']
    blocks = b''.join(hashlib.sha256(content[i:i+4194304]).digest() for i in range(0, len(content), 4194304))
    assert hashlib.sha256(blocks).hexdigest() == node['root_verified_cached_original']['baseline_dropbox_content_hash']
    freeze(original, sha(original)); freeze(HERE / 'current-reference-check.json', sha(HERE / 'current-reference-check.json'))
    context_digest = '6365055f9f0141bc444082bc6a478f2bc7114a00798331db76e027e9171518ec'; freeze(CONTEXT, context_digest); context = read(CONTEXT)
    assert context['new_name_or_specification_approvals'] == 0 and context['component_id'] == 'BC-AC-FULL'
    for item in context['evidence'].values(): freeze(item['path'], item['sha256'])
    binding = read(context['evidence']['cached_images']['path'])
    for item in binding['images']:
        raw = Path(item['path']).read_bytes(); current = heads[item['file_id']]
        assert len(raw) == item['bytes'] == current['size'] and hashlib.sha256(raw).hexdigest() == item['sha256']
        blocks = b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0, len(raw), 4194304))
        assert hashlib.sha256(blocks).hexdigest() == item['expected_dropbox_content_hash']
        freeze(item['path'], item['sha256'])
    for key in ['individual_file', 'context_file']:
        item = read(context['evidence']['current_reference']['path'])[key]; current = heads[item['id']]
        assert all(current[field] == item[field] for field in ['rev', 'size', 'path_display'])
        assert current['path_display'].rsplit('/', 1)[0] in [item['path_display'] for item in heads.values() if 'rev' not in item]
    protected = {str(path): sha(path) for path in [ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'working-specification-approval.json')
    fields = decision['approved_field_groups']; assert len(fields) == 6 and set(fields) == set(decision['specifications'])
    source_ids = decision['approved_proposal_ids']; scoped_ids = [VARIANT + ':' + field.upper() for field in fields]
    decision.update({'component_id': DESIGN, 'size_finish_variant_id': VARIANT, 'catalogue_variant_key': VARIANT, 'source_approved_proposal_ids': source_ids, 'approved_proposal_ids': scoped_ids, 'imported_utc': now, 'approval_record': approval, 'authoritative_user_evidence': messages[-1], 'verified_review_card_evidence': messages[0], 'shared_master_import_performed': True})
    assert not any(item.get('decision_id') == decision['decision_id'] for item in u['size_finish_variant_specification_decisions'])
    u['size_finish_variant_specification_decisions'].append(decision); u['specification_approval_counts'] = specification_counts(u)
    assert u['specification_approval_counts']['proposal_groups'] == before['user']['specification_approval_counts']['proposal_groups'] + 6 == 88
    accepted = copy.deepcopy(decision['specifications'])
    for field, item in accepted.items():
        item['proposal_id'] = VARIANT + ':' + field.upper()
        item['status'] = 'PUBLIC_LISTING_CLAIM;OWNER_ACCEPTED_AS_WORKING;ACTUAL_SPECIMEN_APPLICABILITY_UNVERIFIED'
        item['basis'] = 'Listing source checked ' + item['source_checked_utc'] + '. ' + item['source_url'] + ' . Owner accepted the six working values with source labels and unknowns retained. No independent physical measurement, hardware/load rating, actual stock or lead-time verification.'
    node.update({'specifications_approved': True, 'proposals_approved': True, 'owner_estimates_accepted': True, 'approved_proposal_ids': scoped_ids, 'specification_approval': approval, 'working_specifications_approval_scope': 'EXACT_FINISH_ALL_SIX_WORKING_VALUES', 'all_six_working_specification_fields_accepted': True, 'physical_specs_verified': False, 'actual_stock_verified': False, 'fully_confirmed_specification_groups': [], 'source_specification_proposals_retained_unchanged': True, 'accepted_working_specifications': accepted, 'specification_status_display': 'Six working specifications accepted; listing claims and unknowns retained', 'scope': decision['scope'] + ' Historical BC-MP-1/BC-MP-5 and maker-code lineage, source001 identity, prior name approval and photo coverage retained. Exact Shopify counterpart and scene provenance remain unconfirmed.'})
    assignment = 'Owner kept Moonphase Four — Silver (MP4) source001 and six working specifications; listing claims, actual specimen applicability, Shopify counterpart, stock and scene provenance remain unverified. Historical BC-MP-1/5 retained.'
    p['asset_assignment_overrides'][head['id']]['assignment_status'] = assignment
    p['catalogue_group_overrides']['G243']['assignment_status'] = assignment
    for item in cp['pending_specification_reviews']:
        if item.get('size_finish_variant_id') == VARIANT:
            item.update({'specifications_approved': True, 'working_specifications_accepted': True, 'physical_specs_verified': False, 'specification_approval': approval, 'actual_specification_fields_pending': fields})
    ac = p['reviews']['BC-AC-FULL']['size_finish_variants']['AC-FULL-GOLD-LEAF']
    assert ac['identity_confirmed'] and not ac.get('proposals_approved')
    ctx = context['context_images']; photo = copy.deepcopy(ac.get('photo_coverage', {}))
    photo.update({'on_wall': True, 'wider_room': True, 'contextual_images_available': True, 'contextual_source_status': 'Available: on-wall and room presentation', 'contextual_source_description': ctx['type'] + '. ' + ctx['limitations'], 'contextual_file_ids': [ctx['representative_file_id'], 'id:cnqzTNngPVsAAAAAAAygIA'], 'installation_provenance': 'UNCONFIRMED', 'exact_physical_cast_identity_verified': False, 'review_scope': 'Two representative cached originals rehashed and visually reviewed; current file revisions, sizes and containing folders checked. No complete-folder or whole-library absence claim.', 'new_original_downloads': 0})
    ac.update({'photo_coverage': photo, 'context_output_review': rel(HERE / 'acanthus-context-evidence.json')})
    context.update({'root_reviewed_utc': now, 'root_cached_originals_viewed': [item['file_id'] for item in binding['images']], 'root_current_reference_check': rel(HERE / 'current-reference-check.json'), 'root_new_private_original_downloads': 0, 'shared_master_import_performed': True})
    c['interactive_review_state']['approved_proposal_groups'] = 88
    summary = {'batch': 62, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'SILVER_EXACT_SIX_WORKING_VALUES_AND_SEPARATE_ACANTHUS_CONTEXT_EVIDENCE', 'catalogue_design_key': DESIGN, 'catalogue_variant_key': VARIANT, 'new_working_specification_approvals': 1, 'new_accepted_working_proposal_groups': 6, 'new_physically_verified_specification_groups': 0, 'new_name_approvals': 0, 'new_owner_policy_events': 0, 'new_registered_BC_component_ids': [], 'context_evidence_update': 'BC-AC-FULL:AC-FULL-GOLD-LEAF;NO_SPECIFICATION_APPROVAL', 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(package_path), 'receipt_sha256': digest, 'approval_imported': True, 'evidence_imported': True, 'import_receipt': summary['receipt'], 'status': 'SILVER_SIX_WORKING_VALUES_ACCEPTED;ACANTHUS_CONTEXT_ONLY;ACTUAL_DETAILS_UNVERIFIED'})
    c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
    for doc in docs.values(): doc['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    assert node['specification_proposals'] == before['progress']['catalogue_alias_reviews'][VARIANT]['specification_proposals']
    assert ac['specification_proposals'] == before['progress']['reviews']['BC-AC-FULL']['size_finish_variants']['AC-FULL-GOLD-LEAF']['specification_proposals']
    assert all(cp[key] == value for key, value in before['walkthrough'].items() if key.startswith('current_'))
    assert all(sha(PATHS[key]) == value for key, value in guards.items()) and all(sha(path) == value for path, value in protected.items())
    write(HERE / 'before-import.json', before); write(HERE / 'working-specification-approval.json', decision); write(HERE / 'accepted-working-review.json', node); write(HERE / 'acanthus-context-evidence.json', context); write(HERE / 'source-manifest.json', {'files': files, 'verified_messages': messages})
    for key, path in PATHS.items(): write(path, docs[key])
    write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'decision_id': decision['decision_id'], 'protected_sha256': protected, 'shared_after_sha256': {key: sha(path) for key, path in PATHS.items()}})
    print(json.dumps({'batch': 62, 'status': 'APPLIED', 'accepted_working_field_groups': 88, 'Silver_actual_specs_verified': False, 'Acanthus_specifications_unaccepted': True, 'root_count_question_preserved': True}))

if __name__ == '__main__': main()
