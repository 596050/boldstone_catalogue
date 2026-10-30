"""Import four scoped Moon/Shellwave identities; all 24 specification groups stay open."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'
sys.path.insert(0, str(ROOT / 'components/scripts'))
from review_decision_counts import identity_counts, specification_counts
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(p, j):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(j, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def main():
    receipt_path = HERE / 'import-receipt.json'
    manifest = read(HERE / 'source-manifest.json')
    paths = {'user': REVIEWS / 'user_classifications.json',
             'progress': REVIEWS / 'specification_review_progress.json',
             'walkthrough': REVIEWS / 'walkthrough_checkpoint.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(p) for k, p in paths.items()}
    if receipt_path.exists():
        existing = [x.get('source_decision_id') for values in docs['user'].values()
                    if isinstance(values, list) for x in values if isinstance(x, dict)]
        assert all(existing.count(d['source_decision_id']) == 1 for d in manifest['decisions'])
        print(json.dumps({'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE', 'decisions': 4}))
        return
    for f in manifest['files']:
        p = ROOT / f['snapshot']
        assert sha(p) == f['sha256'] and p.stat().st_size == f['bytes']
    current = read(HERE / 'current-reference-check.json')
    metadata = {x['request_id']: x for x in current['metadata']}
    live = {}
    for d in manifest['decisions']:
        expected, folder_expected = d['primary_expected'], d['folder_expected']
        f = metadata[expected['file_id']]['file']
        fol = metadata[folder_expected['folder_id']]['folder']
        assert f['id'] == expected['file_id'] and f['rev'] == expected['rev']
        assert f['size'] == expected['bytes'] and f['path_display'] == expected['path']
        assert fol['id'] == folder_expected['folder_id'] and fol['path_display'] == folder_expected['path']
        assert f['path_display'].rsplit('/', 1)[0] == fol['path_display']
        live[d['source_decision_id']] = {'file_id': f['id'], 'folder_id': fol['id'],
            'file_path': f['path_display'], 'folder_path': fol['path_display'],
            'rev': f['rev'], 'bytes': f['size'], 'checked_utc': current['checked_utc'],
            'changed_since_owner_card': False, 'image_url': expected['url'], 'folder_url': folder_expected['url'],
            'target_position': expected.get('target_position'), 'source_image_limits': expected.get('provenance_limits', expected.get('provenance_status'))}
    before = copy.deepcopy(docs)
    hashes = {k: sha(p) for k, p in paths.items()}
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert cp['current_component_id'] == 'BC-MCP-1' and cp['current_answer_recorded']
    assert cp['current_size_finish_variant_id'] == 'MCP1-WHITE'
    assert docs['root']['current_component_review'] == c
    affected = {'BC-MSW-MOON', 'BC-MSW-SPIRAL'}
    assert not any(cid in p['reviews'] for cid in affected)
    protected_paths = [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
                       ROOT / cp['current_review_record'], ROOT / cp['last_identity_approval']]
    protected = {str(x): sha(x) for x in protected_paths}
    now = datetime.now(timezone.utc).isoformat()
    write(HERE / 'before-import.json', {'recorded_utc': now,
        'files': {rel(paths[k]): value for k, value in before.items()}, 'protected_sha256': protected})
    existing = {x.get('source_decision_id') for values in u.values()
                if isinstance(values, list) for x in values if isinstance(x, dict)}
    imported = []
    for d in manifest['decisions']:
        assert d['source_decision_id'] not in existing
        source, card = read(ROOT / d['receipt_snapshot']), read(ROOT / d['pre_answer_review'])
        ref = live[d['source_decision_id']]
        cid, vid, kind = d['component_id'], d['variant_id'], d['scope_kind']
        is_build = kind == 'build_variant'
        proposals = copy.deepcopy(card['specification_review_items'])
        for x in proposals:
            x.update({'field': x.get('field', x['group']), 'display': x.get('display', x.get('proposal')),
                      'owner_approved': False, 'physical_specs_verified': False})
        assert len(proposals) == 6
        decision = {'schema_version': 1, 'decision_id': cid + ':' + vid + ':identity:keep',
            'component_id': cid, ('build_variant_id' if is_build else 'size_finish_variant_id'): vid,
            'source_configuration_id': card.get('source_configuration_id'),
            'canonical_name': d['name'], 'confirmed_name': d['name'],
            'recorded_utc': d['authoritative_owner_evidence']['timestamp'], 'imported_utc': now,
            'review_number': d['review_number'], 'action': 'keep',
            'user_statement': d['authoritative_owner_evidence']['text'],
            'status': 'USER CONFIRMED DEPICTED NAME AND SCOPED IDENTITY ONLY',
            'identity_confirmed': True, 'identity_scope': source['identity_scope'], 'scope': source['scope_note'],
            'source_owner_session': d['owner_session'], 'source_decision_id': d['source_decision_id'],
            'source_receipt_snapshot': d['receipt_snapshot'], 'source_receipt_sha256': d['receipt_sha256'],
            'proposal_source': d['pre_answer_review'], 'proposal_source_sha256': d['pre_answer_review_sha256'],
            'working_entry_snapshot': d['working_entry'], 'working_entry_sha256': d['working_entry_sha256'],
            'authoritative_user_evidence': d['authoritative_owner_evidence'],
            'preceding_assistant_card_evidence': d['preceding_review_card_evidence'],
            'specifications_approved': False, 'proposals_approved': False, 'approved_proposal_ids': [],
            'confirmed_fields': ['Working component/finish/build name', 'Depicted identity within stated scope'],
            'not_confirmed': [x['field'] for x in proposals],
            'physical_specs_verified': False, 'physical_manufacture_confirmed': False,
            'primary_file_id': ref['file_id'], 'evidence_file_id': ref['file_id'],
            'primary_folder_id': ref['folder_id'], 'evidence_file_ids': [ref['file_id']],
            'containing_folder_ids': [ref['folder_id']], 'current_dropbox_reference': ref,
            'image_link': ref['image_url'], 'folder_link': ref['folder_url'],
            'arrangement_scope': copy.deepcopy(card.get('arrangement_scope')),
            'remote_files_changed': False, 'live_platform_records_changed': False,
            'workbook_status': 'Unchanged; scoped review overlay for later export.'}
        output = HERE / 'decisions' / cid / vid / 'identity-approval.json'
        write(output, decision)
        ledger = 'build_variant_decisions' if is_build else 'size_finish_variant_decisions'
        u[ledger].append(decision | {'approval_record': rel(output)})
        parent = p['reviews'].setdefault(cid, {'identity_confirmed': False,
            'specifications_approved': False, 'physical_specs_verified': False,
            'scope': 'Named individual configurations approved below; no blanket all-finish/build approval.'})
        variants = parent.setdefault('build_variants' if is_build else 'size_finish_variants', {})
        assert vid not in variants
        variants[vid] = {'canonical_name': d['name'], 'identity_confirmed': True,
            ('build_variant_id' if is_build else 'size_finish_variant_id'): vid,
            'identity_approval': rel(output), 'review_record': d['pre_answer_review'],
            'reviewed_utc': now, 'specification_proposals': proposals,
            'specifications_approved': False, 'proposals_approved': False, 'physical_specs_verified': False,
            'scope': source['scope_note'], 'identity_scope': source['identity_scope'],
            'primary_image_id': ref['file_id'], 'primary_folder_id': ref['folder_id'],
            'current_dropbox_reference': ref, 'photo_selection_review': copy.deepcopy(card.get('photo_selection_review')),
            'production_status': copy.deepcopy(card.get('production_status')),
            'arrangement_scope': copy.deepcopy(card.get('arrangement_scope')),
            'platform_mapping': copy.deepcopy(card.get('platform_mapping')),
            'missing_photographs': copy.deepcopy(card.get('missing_photographs', [])),
            'missing_specifications': copy.deepcopy(card.get('missing_specifications', [])),
            'complete_source_review_snapshot': d['pre_answer_review'], 'workbook_contains_import': False}
        cp['pending_specification_reviews'].append({'component_id': cid,
            ('build_variant_id' if is_build else 'size_finish_variant_id'): vid,
            'canonical_name': d['name'], 'identity_approved': True, 'specifications_approved': False,
            'pending_fields': [x['field'] for x in proposals], 'review_record': d['pre_answer_review'],
            'identity_approval': rel(output), 'image_link': ref['image_url'], 'folder_link': ref['folder_url'],
            'scope': source['scope_note']})
        imported.append({'component_id': cid, 'variant_id': vid, 'scope_kind': kind, 'name': d['name'],
                         'approval': rel(output), 'source_decision_id': d['source_decision_id']})
    u['identity_confirmation_counts'] = identity_counts(u)
    u['specification_approval_counts'] = specification_counts(u)
    expected_counts = before['user']['identity_confirmation_counts'] | {
        'explicit_size_finish_variant_names': before['user']['identity_confirmation_counts']['explicit_size_finish_variant_names'] + 3,
        'explicit_build_variant_decisions': before['user']['identity_confirmation_counts']['explicit_build_variant_decisions'] + 1,
        'components_with_any_identity_scope': before['user']['identity_confirmation_counts']['components_with_any_identity_scope'] + 2}
    assert u['identity_confirmation_counts'] == expected_counts
    assert u['specification_approval_counts'] == before['user']['specification_approval_counts']
    assert u['dimension_confirmation_counts'] == before['user']['dimension_confirmation_counts']
    exception_source = next(x['snapshot'] for x in manifest['files'] if x['source'].endswith('/family-closeout/media-exceptions.json'))
    audit_source = next(x['snapshot'] for x in manifest['files'] if x['source'].endswith('/family-closeout/family-media-audit.json'))
    supplement = {'import_receipt': rel(receipt_path), 'source_manifest': rel(HERE / 'source-manifest.json'),
        'family_media_audit': audit_source, 'file_specific_exceptions': exception_source,
        'source_snapshot_scope': 'Peer thumbnail-or-better triage of188files;13current originals locally hash-verified by peer. Root refreshed four selected files and four folders; not a root live full-family content audit.',
        'scope_notes': manifest['import_constraints'], 'outstanding_followups': manifest['outstanding_followups'],
        'review_reference_cards_answered': 4, 'reference_total_is_sculpture_count': False,
        'all_24_specification_groups_unapproved': True, 'physical_specs_verified': False}
    assert 'Moon & Shellwave' not in c['family_review_supplements']
    c['family_review_supplements']['Moon & Shellwave'] = copy.deepcopy(supplement)
    p.setdefault('parallel_family_evidence', {})['Moon & Shellwave'] = copy.deepcopy(supplement)
    p['family_review_progress']['Moon & Shellwave'] = supplement | {
        'status': 'KNOWN_REFERENCE_NAMES_REVIEWED_SPECIFICATIONS_AND_PHOTO_GAPS_PENDING',
        'review_reference_total': 4, 'specifications_complete': False,
        'scope': 'Three finish references plus one upper-panel water-feature build, covering two component designs; not four moulds or a physical stock count.'}
    summary = {'recorded_utc': now, 'receipt': rel(receipt_path), 'component_ids': sorted(affected),
        'identity_receipts': 4, 'size_finish_identity_receipts': 3, 'build_identity_receipts': 1,
        'new_specification_approvals': 0, 'wholly_unconfirmed_specification_groups': 24,
        'current_MCP1_review_preserved': True, 'workbook_export_pending': True}
    for entry in cp['parallel_import_queue']:
        if entry['receipt'] == manifest['source_package']:
            assert not entry['approval_imported']
            entry.update({'approval_imported': True, 'status': 'IMPORTED_EXACT_NAME_SCOPES; ALL24SPECIFICATION_GROUPS_PENDING',
                'import_receipt': rel(receipt_path), 'imported_utc': now})
    for entry in cp['parallel_owner_reviews']:
        if entry['component_id'] in affected:
            entry.update({'status': 'SEALED NAME RECEIPTS IMPORTED; SPECIFICATION AND PHOTO GAPS RETAINED',
                          'import_receipt': rel(receipt_path)})
    cp['last_parallel_import'] = copy.deepcopy(summary)
    cp['next_serialized_parallel_import'].update({'status': 'APPLIED_AND_VERIFIED',
        'receipt': rel(receipt_path), 'completed_utc': now})
    cp['completed_serialized_parallel_import'] = copy.deepcopy(cp['next_serialized_parallel_import'])
    cp['updated_utc'] = now
    p['latest_parallel_import'] = copy.deepcopy(summary)
    c.update({'parallel_import_queue': copy.deepcopy(cp['parallel_import_queue']),
        'parallel_owner_reviews': copy.deepcopy(cp['parallel_owner_reviews']),
        'last_parallel_import': copy.deepcopy(summary), 'updated_utc': now})
    counts = u['identity_confirmation_counts']
    c['interactive_review_state'].update({'explicit_identity_confirmations': counts['component_designs'],
        'explicit_size_finish_variant_names_confirmed': counts['explicit_size_finish_variant_names'],
        'explicit_build_variant_decisions': counts['explicit_build_variant_decisions'],
        'components_with_any_identity_scope': counts['components_with_any_identity_scope']})
    u['updated_utc'] = p['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    docs['root']['updated_utc'] = now
    for key, value in before['walkthrough'].items():
        if key.startswith('current_') or key in ['proposed_name', 'answer_state', 'question_scope', 'next_review_after_keep']:
            assert cp[key] == value, key
    for key, value in before['user'].items():
        if isinstance(value, list):
            assert u[key][:len(value)] == value, key
    assert all(p['reviews'][cid] == value for cid, value in before['progress']['reviews'].items())
    assert cp['pending_specification_reviews'][:len(before['walkthrough']['pending_specification_reviews'])] == before['walkthrough']['pending_specification_reviews']
    assert all(sha(path) == hashes[k] for k, path in paths.items()), 'Shared writer collision'
    assert all(sha(Path(path)) == digest for path, digest in protected.items())
    for key, path in paths.items():
        write(path, docs[key])
        assert read(path) == docs[key]
    result = {'status': 'APPLIED_AND_VERIFIED', **summary, 'imported': imported,
        'counts': {'identity': counts, 'specification': u['specification_approval_counts']},
        'protected_sha256': protected, 'source_files_frozen': len(manifest['files']),
        'owner_replies_and_preceding_cards_verified': 8, 'root_checkpoint_matches_component': True,
        'water_feature_approval_upper_panel_only': True, 'source_media_exceptions_preserved': True,
        'remote_files_changed': False, 'live_platform_records_changed': False, 'physical_specs_verified': False}
    write(receipt_path, result)
    event = {'event_id': 'parallel-import:batch7:2026-10-19', 'event': 'VERIFIED_SCOPED_OWNER_NAMES_IMPORTED',
        'recorded_utc': now, 'import_receipt': rel(receipt_path), 'identity_receipts': 4,
        'new_specification_approval_inferred': False, 'current_MCP1_review_preserved': True}
    for path in [REVIEWS / 'identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(json.dumps({'status': result['status'], **summary, 'counts': result['counts']}))


if __name__ == '__main__':
    main()
