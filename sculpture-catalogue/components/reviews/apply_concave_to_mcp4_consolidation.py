"""Apply the owner's MCP4 canonical identity and verified, move-only Dropbox readback."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
REV = ROOT / 'components/reviews'
HERE = REV / 'concave-to-mcp4-consolidation-2026-10-19'
IMPORT = REV / 'parallel-import-2026-10-19-batch27'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    paths = {'user': REV / 'user_classifications.json', 'progress': REV / 'specification_review_progress.json',
             'walkthrough': REV / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    if (IMPORT / 'import-receipt.json').exists():
        assert docs['progress']['canonical_component_consolidations']['BC-CONCAVE']['canonical_component_id'] == 'BC-MCP-4'
        assert docs['walkthrough']['current_identity_relationship_answer_recorded'] is True
        print(json.dumps({'batch': 27, 'status': 'ALREADY_APPLIED_IDEMPOTENT_NO_WRITE'})); return
    before = copy.deepcopy(docs); guards = {k: sha(p) for k, p in paths.items()}
    user, progress, cp, c, root = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component', 'root'])
    assert root['current_component_review'] == c
    assert cp['current_component_id'] == 'BC-MCP-4' and cp['current_answer_recorded'] is False
    assert cp['current_size_finish_variant_id'] == 'MCP4-WHITE'
    current_book = ROOT / progress['latest_workbook_export']['workbook']
    assert sha(current_book) == progress['latest_workbook_export']['workbook_sha256'] == 'f3a180d5bdb41a0a86b0d30225839e08641d1655a05c7e8b56f422b37bd1df7c'
    protected = {str(p): sha(p) for p in [current_book, ROOT / 'components/evidence/component_register.json',
        ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    assert read(HERE / 'live-move-verification.json')['status'] == 'PASS_LIVE_MOVE_READBACK'
    owner = read(HERE / 'owner-decision-evidence.json')['messages'][-1]
    assert owner['line'] == 16210 and owner['text'] == 'Concave Moon should be consolidated under Moon Crater Phase 4'
    with Path(owner['transcript']).open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            if number == owner['line']:
                item = json.loads(raw); payload = item['payload']
                text = '\n'.join(x.get('text', '') for x in payload['content'] if x.get('type') in ['input_text', 'output_text'])
                assert payload['role'] == 'user' and text == owner['text'] and sha_line(raw) == owner['raw_line_sha256']
                break
    model = read(ROOT / 'components/evidence/component_register.json')
    after = read(HERE / 'after-live-metadata.json')
    files = {x['file']['id']: x['file'] for x in after['metadata'] if x.get('file')}
    folders = {x['folder']['id']: x['folder'] for x in after['metadata'] if x.get('folder')}
    folder_paths = {x['path_display']: x for x in folders.values()}
    listings = {x['folder_id']: x for x in read(HERE / 'after-live-listings.json')['listings']}
    assert len(files) == 47 and sum(x['size'] for x in files.values()) == 225017179
    now = datetime.now(timezone.utc).isoformat()
    record_path = rel(HERE / 'canonical-consolidation.json')

    def reference(fid):
        f = files[fid]; path = f['path_display']; parent = folder_paths[path.rsplit('/', 1)[0]]
        return {'file_id': fid, 'folder_id': parent['id'], 'file_path': path, 'folder_path': parent['path_display'],
                'file_revision': f['rev'], 'file_bytes': f['size'], 'checked_utc': after['checked_utc'],
                'image_url': 'https://www.dropbox.com/home' + quote(parent['path_display'], safe='/') + '?preview=' + quote(f['name']),
                'folder_url': 'https://www.dropbox.com/home' + quote(parent['path_display'], safe='/')}

    variant_map = {'CM-WHITE-25': 'MCP4-WHITE', 'CM-SILVER-25': 'MCP4-SILVER-BRONZE-25', 'CM-VERDIGRIS-25': 'MCP4-VERDIGRIS-25'}
    names = {'MCP4-WHITE': 'Moon Crater Phase 4 — White (MCP4)',
             'MCP4-SILVER-BRONZE-25': 'Moon Crater Phase 4 — Silver and Bronze', 'MCP4-VERDIGRIS-25': 'Moon Crater Phase 4 — Verdigris'}
    old = progress['reviews']['BC-CONCAVE']; previous_mcp = progress['reviews']['BC-MCP-4']
    variants = {}
    for old_key, new_key in variant_map.items():
        source = old['size_finish_variants'][old_key]; node = copy.deepcopy(source)
        ref = reference(node['primary_image_id'])
        node.update({'component_id': 'BC-MCP-4', 'size_finish_variant_id': new_key, 'canonical_name': names[new_key],
            'proposed_name': names[new_key], 'display_name': names[new_key], 'identity_confirmed': True,
            'canonical_consolidation_record': record_path, 'historical_component_id': 'BC-CONCAVE',
            'historical_size_finish_variant_id': old_key, 'former_names': [source.get('canonical_name', source.get('proposed_name'))],
            'current_dropbox_reference': ref, 'primary_folder_id': ref['folder_id'], 'physical_specs_verified': False,
            'specification_approval_origin': {'component_id': 'BC-CONCAVE', 'size_finish_variant_id': old_key,
                'source_approval': source.get('specification_approval'), 'approval_not_expanded_by_consolidation': True},
            'scope': 'Canonical MCP4 finish record formerly reviewed as ' + old_key + '. Existing finish-specific dimensions, estimates and approval states retained. Other finishes and physical casts are not merged.',
            'review_record': rel(HERE / 'canonical-reviews' / (new_key + '.json'))})
        assert node['specification_proposals'] == source['specification_proposals']
        variants[new_key] = node
    white = copy.deepcopy(variants['MCP4-WHITE'])
    white.update({'review_number': 74, 'family': 'Moon Crater Phase', 'series_code': 'MCP4',
        'canonical_design_name': 'Moon Crater Phase 4', 'owner_relationship_confirmed': True,
        'review_decision_mode': 'OWNER_CANONICAL_DESIGN_CONSOLIDATION', 'identity_approval': record_path,
        'size_finish_variants': variants, 'pending_size_finish_variants': copy.deepcopy(previous_mcp['pending_size_finish_variants']),
        'pending_arrangement_component_review': previous_mcp.get('pending_arrangement_component_review'),
        'additional_same_design_reference_file_ids': ['id:cnqzTNngPVsAAAAAAAyjMA'],
        'canonical_design_record': {'canonical_name': 'Moon Crater Phase 4', 'identity_confirmed': True,
            'primary_image_id': white['primary_image_id'], 'primary_folder_id': white['primary_folder_id'],
            'current_dropbox_reference': white['current_dropbox_reference'], 'scope': 'One current design. Concave Moon is a former name/source ID. Use finish-specific records for specifications; physical casts, moulds and stock remain unverified.',
            'available': {k: 'Use the finish-specific record; no value is assigned across every MCP4 finish or size.'
                          for k in ['dimensions', 'weight', 'material', 'fixing_source_claim', 'individual_price', 'availability']}}})
    progress['reviews']['BC-MCP-4'] = white
    old.update({'current_catalogue_status': 'HISTORICAL_ALIAS_ONLY;USE_BC-MCP-4', 'canonical_component_id': 'BC-MCP-4',
                'canonical_design_name': 'Moon Crater Phase 4', 'canonical_consolidation_record': record_path,
                'separate_listing_required': False, 'historical_specifications_and_approvals_retained': True})
    decision = {'schema_version': 1, 'decision_id': 'BC-CONCAVE:CANONICAL-UNDER:BC-MCP-4:OWNER-LINE16210',
        'recorded_utc': now, 'component_id': 'BC-CONCAVE', 'canonical_component_id': 'BC-MCP-4',
        'canonical_name': 'Moon Crater Phase 4', 'canonical_series_code': 'MCP4', 'former_name': 'Concave Moon',
        'relationship': 'OWNER_CONFIRMED_CANONICAL_DESIGN_CONSOLIDATION', 'authoritative_user_evidence': owner,
        'historical_component_ids': ['BC-CONCAVE', 'BC-MCP-4'], 'variant_aliases': variant_map,
        'canonical_folder_id': 'id:cnqzTNngPVsAAAAAAArqTw', 'canonical_folder_path': folders['id:cnqzTNngPVsAAAAAAArqTw']['path_display'],
        'canonical_folder_url': 'https://www.dropbox.com/home' + quote(folders['id:cnqzTNngPVsAAAAAAArqTw']['path_display'], safe='/'),
        'prior_white_25_working_approval_preserved': True, 'new_specification_approvals': 0,
        'physical_cast_mould_or_stock_merge': False, 'new_registered_BC_component_ids': [],
        'Silver_vs_Silver_Bronze_finish_equivalence_confirmed': False,
        'native_vs_former_Concave_Verdigris_finish_equivalence_confirmed': False,
        'exact_platform_match_upgraded': False, 'remote_verification': rel(HERE / 'live-move-verification.json'),
        'approval_record': record_path, 'no_separate_Concave_listing': True}
    user.setdefault('component_identity_relationship_decisions', []).append(copy.deepcopy(decision))
    user.setdefault('catalogue_naming_corrections', []).append(copy.deepcopy(decision))
    progress.setdefault('canonical_component_consolidations', {})['BC-CONCAVE'] = copy.deepcopy(decision)
    progress.setdefault('canonical_variant_aliases', {}).update({f'BC-CONCAVE|{k}': {'canonical_component_id': 'BC-MCP-4',
        'canonical_variant_id': v, 'approval_record': record_path, 'specification_approvals_retain_original_scope': True} for k, v in variant_map.items()})
    progress['current_catalogue_overlays']['Concave Moon'] = copy.deepcopy(decision)
    progress.setdefault('live_dropbox_metadata_overlays', {})['MCP4_CONSOLIDATION'] = {'files': files, 'folders': folders,
        'checked_utc': after['checked_utc'], 'file_hashes_reverified': False, 'record': rel(HERE / 'after-live-metadata.json')}
    for fid, f in files.items():
        ref = reference(fid); override = progress['asset_assignment_overrides'].setdefault(fid, {})
        override.update({'file_id': fid, 'folder_id': ref['folder_id'], 'path_display': f['path_display'],
            'family': 'Moon Crater Phase', 'component_ids': ['BC-MCP-4'], 'canonical_design_name': 'Moon Crater Phase 4',
            'assignment_status': 'OWNER_CANONICAL_DESIGN_CONSOLIDATION;FINISH_SPECIFICATIONS_AND_PHYSICAL_STOCK_SEPARATE',
            'review_record': record_path, 'current_reference_check': rel(HERE / 'after-live-metadata.json')})
    for g in model['groups']:
        if g['id'] not in folders: continue
        f = folders[g['id']]; count = len(listings[g['id']]['entries']); retired = count == 0
        progress['catalogue_group_overrides'][g['group_ref']] = {'current_family': 'Moon Crater Phase', 'current_name': f['name'],
            'current_folder_id': f['id'], 'current_folder_path': f['path_display'], 'file_count': count,
            'role': 'Empty historical folder ID retained' if retired else g.get('role', 'MCP4 finish reference'),
            'component_ids': [] if retired else ['BC-MCP-4'], 'assignment_status': 'EMPTY_HISTORICAL_FOLDER;WHITE_FILES_CONSOLIDATED' if retired else 'MCP4_CANONICAL_DESIGN;FINISH_SCOPES_RETAINED',
            'canonical_consolidation_record': record_path}
    cp.update({'current_answer_recorded': True, 'current_identity_relationship_answer_recorded': True,
        'current_identity_relationship_approval': record_path, 'last_identity_relationship_approval': record_path,
        'canonical_depicted_name': 'Moon Crater Phase 4', 'proposed_name': names['MCP4-WHITE'],
        'candidate_canonical_depicted_name': 'Moon Crater Phase 4',
        'state': 'CANONICAL_IDENTITY_CONSOLIDATED;OTHER_MCP4_FINISH_MATCHES_PENDING',
        'answer_state': 'Owner made Moon Crater Phase4 canonical; Concave Moon retained as former name. No new specification approval.',
        'question_scope': 'Consolidation answered; native Silver and Verdigris finish comparisons await preparation.',
        'current_review_record': white['review_record'], 'last_completed_component_id': 'BC-MCP-4',
        'last_completed_review_number': 74, 'current_specification_answer_recorded': False,
        'current_dimension_answer_recorded': False, 'review_decision_mode': 'OWNER_CANONICAL_DESIGN_CONSOLIDATION'})
    main_ref = white['current_dropbox_reference']; f = files[main_ref['file_id']]; folder = folders[main_ref['folder_id']]
    cp['primary_image'] = {'file_id': f['id'], 'name': f['name'], 'path_display': f['path_display'], 'open_in_dropbox_url': main_ref['image_url']}
    cp['containing_folder'] = {'folder_id': folder['id'], 'name': folder['name'], 'path_display': folder['path_display'], 'open_in_dropbox_url': main_ref['folder_url']}
    cp['displayed_identity_evidence_folder_ids'] = [main_ref['folder_id']]
    c['interactive_review_state'].update({'current_name': names['MCP4-WHITE'], 'state': cp['state'],
        'identity_relationship_answered': True, 'canonical_component_id': 'BC-MCP-4', 'former_component_id': 'BC-CONCAVE',
        'last_identity_relationship_approval': record_path})
    c['last_identity_relationship_decision'] = copy.deepcopy(decision)
    c['current_component_review_record'] = white['review_record']
    c['current_catalogue_overlays']['Concave Moon'] = copy.deepcopy(decision)
    reservation = read(HERE / 'exclusive-write-reservation.json')
    reservation['status'] = 'VERIFIED_REMOTE_CONSOLIDATION;SHARED_CANONICAL_CORRECTION_APPLIED;RESERVATION_RELEASED'
    reservation['released_utc'] = now
    for target in [cp, c]: target.setdefault('dropbox_write_reservations', []).append(copy.deepcopy(reservation))
    summary = {'batch': 27, 'recorded_utc': now, 'receipt': rel(IMPORT / 'import-receipt.json'),
        'scope': 'OWNER_CONCAVE_TO_MCP4_CANONICAL_CONSOLIDATION', 'canonical_component_id': 'BC-MCP-4',
        'historical_component_id': 'BC-CONCAVE', 'new_registered_BC_component_ids': [], 'new_full_specification_approvals': 0,
        'new_identity_alias_relationships': 1, 'new_canonical_name_corrections': 1, 'workbook_export_pending': True,
        'remote_move_entries_verified': 13, 'retained_image_files': 47, 'root_new_private_original_downloads': 0}
    cp['parallel_import_queue'].append({'scope_kind': summary['scope'], 'receipt': record_path, 'approval_imported': True,
        'import_receipt': summary['receipt'], 'status': 'OWNER_SCOPE_APPLIED;LIVE_MOVES_VERIFIED;SPECIFICATIONS_UNCHANGED'})
    c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target in [cp, c]: target['last_parallel_import'] = copy.deepcopy(summary)
    progress['latest_parallel_import'] = copy.deepcopy(summary)
    for target in docs.values(): target['updated_utc'] = now
    root['current_component_review'] = copy.deepcopy(c)
    assert c['counts'] == before['component']['counts']
    for ledger in ['identity_confirmation_counts', 'specification_approval_counts', 'dimension_confirmation_counts',
                   'specification_decisions', 'size_finish_variant_specification_decisions', 'dimension_decisions']:
        assert user[ledger] == before['user'][ledger]
    assert all(sha(paths[k]) == v for k, v in guards.items()) and all(sha(k) == v for k, v in protected.items())
    write(IMPORT / 'before-import.json', before)
    write(HERE / 'canonical-consolidation.json', decision)
    for node in variants.values(): write(ROOT / node['review_record'], node)
    # The current white record includes its design and the three historically reviewed finish scopes.
    write(ROOT / white['review_record'], white)
    for k, p in paths.items(): write(p, docs[k])
    write(HERE / 'exclusive-write-reservation.json', reservation)
    write(IMPORT / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'decision_id': decision['decision_id'],
        'summary': summary, 'canonical_consolidation': record_path, 'protected_sha256': protected,
        'shared_after_sha256': {k: sha(p) for k, p in paths.items()}})
    print(json.dumps({'batch': 27, 'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'canonical_name': 'Moon Crater Phase 4',
                      'new_specification_approvals': 0, 'image_files': 47}))


def sha_line(raw):
    return hashlib.sha256(raw).hexdigest()


if __name__ == '__main__': main()
