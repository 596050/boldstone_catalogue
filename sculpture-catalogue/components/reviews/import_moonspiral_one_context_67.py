"""Import derived photo coverage without accepting any Moonspiral specification."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from import_moonphase_silver_working_specs_62 import ROOT, PATHS, read, sha, rel, write

HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch67'
SOURCE = ROOT / 'components/parallel-reviews/moonspiral-one-white-working-specs-2026-10-20'
CID, VID = 'BC-MS-1', 'MS1-WHITE'

def main():
    docs = {key: read(path) for key, path in PATHS.items()}
    if (HERE / 'import-receipt.json').exists():
        assert docs['progress']['reviews'][CID]['size_finish_variants'][VID]['photo_coverage']['contextual_source_status'] == 'Available: on-wall and shared family room context'
        print(json.dumps({'batch': 67, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    before, guards = copy.deepcopy(docs), {key: sha(path) for key, path in PATHS.items()}; files = []
    def freeze(path, digest):
        path = Path(path); assert sha(path) == digest
        dest = HERE / 'sources' / (digest + path.suffix); dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert sha(dest) == digest
        else: dest.write_bytes(path.read_bytes())
        files.append({'source': str(path), 'snapshot': rel(dest), 'sha256': digest}); return rel(dest)
    context_path = SOURCE / 'CONTEXT_OUTPUT_UPDATE.json'; context_digest = 'c52ea62415aa982eba1c9e2730c22e0fcfa92d0d76af763cecbd64a5e8481478'
    freeze(context_path, context_digest); context = read(context_path); binding_ref = context['context_images']['source_binding']; freeze(binding_ref['path'], binding_ref['sha256']); binding = read(binding_ref['path'])
    freeze(binding['current_metadata']['path'], binding['current_metadata']['sha256']); original_heads = {item['id']: item for item in read(binding['current_metadata']['path'])['objects'].values()}
    freeze(binding['prior_media_review']['path'], binding['prior_media_review']['sha256']); freeze(binding['reviewed_contact_sheet']['path'], binding['reviewed_contact_sheet']['sha256'])
    metadata = read(HERE / 'current-reference-check.json')['metadata']; heads = {item[item['metadata_type']]['id']: item[item['metadata_type']] for item in metadata}
    for item in binding['sources']:
        preview = item['cached_preview']; freeze(preview['path'], preview['sha256']); assert Path(preview['path']).stat().st_size == item['cached_preview_bytes']
        head, folder = heads[item['file_id']], heads[item['folder_id']]
        assert head['size'] == item['remote_original_bytes'] and head['path_display'].rsplit('/', 1)[0] == folder['path_display']
        assert all(head[key] == original_heads[head['id']][key] for key in ['rev', 'size', 'path_display'])
        assert item['cache_kind'] == 'thumbnail' and not item['original_bytes_rehashed_this_turn']
    assert len(binding['sources']) == 3 and len(read(binding['current_metadata']['path'])['individual_listing']['entries']) == 10 and len(read(binding['current_metadata']['path'])['context_listing']['entries']) == 1
    assert not read(binding['current_metadata']['path'])['individual_listing']['has_more'] and not read(binding['current_metadata']['path'])['context_listing']['has_more']
    freeze(HERE / 'current-reference-check.json', sha(HERE / 'current-reference-check.json'))
    u, p, cp, c = (docs[key] for key in ['user', 'progress', 'walkthrough', 'component']); node = p['reviews'][CID]['size_finish_variants'][VID]
    assert docs['root']['current_component_review'] == c and cp['last_parallel_import']['batch'] == 66 and node['identity_confirmed'] and not node['proposals_approved']
    assert context['new_name_or_specification_approvals'] == 0 and context['new_BC_component_ids'] == [] and VID not in p['current_component_photograph_gaps']
    protected = {str(path): sha(path) for path in [ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat(); evidence_path = rel(HERE / 'context-evidence.json'); ctx = context['context_images']
    description = ctx['type'] + '. ' + ctx['limitations'] + ' Root checked three source thumbnails and the11-image contact sheet; original bytes were not rehashed in this context review.'
    coverage = copy.deepcopy(node.get('photo_coverage', {}))
    coverage.update({'on_wall': True, 'series_arrangement': True, 'family_wider_room_context': True, 'individual_wider_room_established': False, 'contextual_images_available': True, 'contextual_source_status': 'Available: on-wall and shared family room context', 'contextual_source_description': description, 'contextual_file_ids': [ctx['representative_file_id'], ctx['individual_context_file_id']], 'individual_context_file_id': ctx['individual_context_file_id'], 'individual_context_folder_id': ctx['individual_context_folder_id'], 'shared_family_context_file_id': ctx['representative_file_id'], 'shared_family_context_folder_id': ctx['representative_folder_id'], 'exact_physical_cast_identity_verified': False, 'installation_provenance': 'UNCONFIRMED', 'source_camera_original_verified': False, 'root_evidence_kind': 'THUMBNAILS_AND_CONTACT_SHEET_ONLY', 'original_bytes_rehashed_this_context_review': False, 'review_scope': 'Ten individual and one individual-context previews in prior scoped media review; root inspected that contact sheet and three source thumbnails, including one shared-room source. Shared-room folder not exhaustively audited.', 'evidence_record': evidence_path})
    node.update({'photo_coverage': coverage, 'context_output_review': evidence_path})
    gap = {'component_id': CID, 'size_finish_variant_id': VID, 'canonical_name': node['canonical_name'], 'finish': 'White', 'front': 'Complete front/on-wall depiction linked; cached thumbnail evidence.', 'room': 'Close individual on-wall view available. Wider-room pair image is shared family context; dedicated individual wider-room view unestablished.', 'series': 'Shared Moonspirals1-and2 wider-room picture available; no new member identification or physical count.', 'evidence': 'Three representative cached thumbnails and11-image contact sheet reviewed. Stable file/folder IDs and current metadata checked. Original bytes and installation authenticity unverified; not a whole-library absence claim.', 'missing': 'Rear/fixing, calibrated side/profile and dedicated individual wider-room image not established in the reviewed packet.', 'review_record': evidence_path, 'source_package_sha256': context_digest}
    p['current_component_photograph_gaps'][VID] = gap
    context.update({'imported_utc': now, 'root_current_reference_check': rel(HERE / 'current-reference-check.json'), 'root_viewed_cached_preview_file_ids': [item['file_id'] for item in binding['sources']], 'root_viewed_prior11_image_contact_sheet': binding['reviewed_contact_sheet'], 'root_original_bytes_rehashed': False, 'root_new_private_original_downloads': 0, 'owner_approval_inferred': False, 'shared_master_import_performed': True})
    summary = {'batch': 67, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'MOONSPIRAL_ONE_DERIVED_CONTEXT_AND_PHOTO_GAPS_ONLY', 'component_id': CID, 'size_finish_variant_id': VID, 'new_name_approvals': 0, 'new_working_specification_approvals': 0, 'new_physically_verified_specification_groups': 0, 'new_owner_policy_events': 0, 'new_registered_BC_component_ids': [], 'new_photo_gap_rows': 1, 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(context_path), 'receipt_sha256': context_digest, 'approval_imported': False, 'evidence_imported': True, 'import_receipt': summary['receipt'], 'status': 'CONTEXT_AND_PHOTO_GAPS_RECORDED;NO_OWNER_OR_SPECIFICATION_APPROVAL'})
    c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
    for key, doc in docs.items():
        if key != 'user': doc['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    assert u == before['user'] and node['specification_proposals'] == before['progress']['reviews'][CID]['size_finish_variants'][VID]['specification_proposals']
    assert all(cp[key] == value for key, value in before['walkthrough'].items() if key.startswith('current_')) and c['counts'] == before['component']['counts']
    assert all(sha(PATHS[key]) == value for key, value in guards.items()) and all(sha(path) == value for path, value in protected.items())
    write(HERE / 'before-import.json', before); write(HERE / 'context-evidence.json', context); write(HERE / 'photo-coverage.json', coverage); write(HERE / 'photo-gap.json', gap); write(HERE / 'source-manifest.json', {'files': files, 'root_visual_review_kind': 'THUMBNAILS_AND_CONTACT_SHEET_ONLY'})
    for key, path in PATHS.items():
        if key != 'user': write(path, docs[key])
    write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'protected_sha256': protected, 'shared_after_sha256': {key: sha(path) for key, path in PATHS.items()}})
    print(json.dumps({'batch': 67, 'status': 'APPLIED_CONTEXT_ONLY', 'source_thumbnails': 3, 'new_photo_gap_rows': 1, 'new_owner_or_specification_approvals': 0, 'root_count_question_preserved': True}))

if __name__ == '__main__': main()
