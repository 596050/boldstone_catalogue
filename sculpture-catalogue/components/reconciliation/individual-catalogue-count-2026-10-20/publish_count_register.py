"""Publish the verified additive count register without altering source ledgers."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
write = lambda p, d: p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')

def main():
    graph_path = HERE / 'canonical-count-register.json'
    graph = read(graph_path)
    export = read(HERE / 'export-receipt.json')
    saved = read(HERE / 'saved-file-verification.json')
    visual = read(HERE / 'visual-verification.json')
    workbook = Path(export['output'])
    graph_sha, book_sha = digest(graph_path), digest(workbook)
    assert saved['status'] == visual['status'] == 'PASS'
    assert graph_sha == export['register_sha256'] == saved['register_sha256']
    assert book_sha == export['workbook_sha256'] == saved['workbook_sha256'] == visual['workbook_sha256']
    peer = BASE / 'components/reconciliation/product-register-final-readback-2026-10-20'
    graph_proof = peer / ('FINAL_GRAPH_READBACK_' + graph_sha[:16] + '.json')
    book_proof = peer / ('SAVED_REGISTER_READBACK_' + book_sha[:16] + '.json')
    gp, bp = read(graph_proof), read(book_proof)
    assert gp['status'] == bp['status'] == 'PASS'
    assert gp['graph_sha256'] == bp['graph_sha256'] == graph_sha
    assert bp['workbook_sha256'] == book_sha and not bp['error_cells'] and not bp['superseded_path_links']
    source_checks = []
    for key, item in graph['input_manifest'].items():
        path = Path(item['source'])
        actual = digest(path)
        assert actual == item['sha256'], f'Source drift before publication: {key}'
        source_checks.append({'source_key': key, 'source': str(path), 'sha256': actual, 'unchanged': True})
    historical_book = BASE / 'outputs/01a144ab-1a7c-7223-a403-73a4d53d70ff/Boldstone_Sculpture_Catalogue_Review_2026-10-20.xlsx'
    assert digest(historical_book) == '75076dbfb62dab8e98f6355213756a07ae4d16d9222674f28016826d1b7c619e'
    assert len(graph['case_closure_dispositions']) == 15
    assert len(graph['scoped_working_correction_option_ids']) == 4
    timestamp = datetime.now(timezone.utc).isoformat()
    relative = lambda p: str(p.relative_to(BASE))
    proof = lambda p: {'path': relative(p), 'sha256': digest(p)}
    publication_path = HERE / 'publication-receipt.json'
    scoped_path = HERE / 'scoped-import-receipt.json'
    pointer = {'recorded_utc': timestamp, 'status': 'CLASSIFIED_CURRENT_CATALOGUE_WITH_EXPLICIT_EVIDENCE_LIMITS',
               'register': relative(graph_path), 'register_sha256': graph_sha,
               'workbook': relative(workbook), 'workbook_sha256': book_sha,
               'publication_receipt': relative(publication_path),
               'summary': graph['summary'], 'count_definition': graph['count_definition'],
               'whole_library_unique_design_total': None, 'physical_stock_quantity': None,
               'source_review_rows_are_not_a_sculpture_count': True,
               'group_only_components_not_inferred': True,
               'reference_only_finish_cases_closed': 9,
               'original_review_workbook_preserved': relative(historical_book),
               'exact_platform_matches_not_upgraded_by_count_projection': True}
    scoped = {'status': 'APPLIED_TO_CURRENT_ADDITIVE_REGISTER', 'recorded_utc': timestamp,
              'register': relative(graph_path), 'register_sha256': graph_sha,
              'source_cases_applied': len(graph['case_closure_dispositions']),
              'case_ids': [x['case_id'] for x in graph['case_closure_dispositions']],
              'existing_option_corrections': graph['scoped_working_correction_option_ids'],
              'existing_option_field_overlays': 24,
              'case_package_seal': graph['input_manifest']['case_package_seal'],
              'case_package_independent_check': graph['input_manifest']['case_package_independent_check'],
              'current_count_workbook': relative(workbook), 'current_count_workbook_sha256': book_sha,
              'workbook_display_boundary': 'The count workbook shows current dimensions and identity/option hierarchy. All six scoped working corrections are retained in the additive JSON register. The earlier full-specification Review97 workbook is an unchanged historical source.',
              'original_A173_product_ids_retained': 173, 'original_review97_assertions_retained': 1668,
              'new_owner_approval_events': 0, 'remote_mutations': 0,
              'review97_source_workbook_sha256_preserved': digest(historical_book)}
    write(scoped_path, scoped)

    control_paths = [BASE / 'components/reviews/specification_review_progress.json',
                     BASE / 'components/checkpoint.json', BASE / 'checkpoint.json']
    control_changes = []
    for path in control_paths:
        before_raw = path.read_bytes()
        before = json.loads(before_raw)
        backup = HERE / 'inputs' / (path.parent.name + '-' + path.name + '.before-publication')
        assert not backup.exists(), 'Publication already performed; inspect its receipt instead of duplicating it'
        backup.write_bytes(before_raw)
        after = json.loads(before_raw)
        after['current_individual_catalogue_count'] = pointer
        if path.name == 'specification_review_progress.json':
            after['scoped_source_case_and_price_reconciliation'] = {
                'status': scoped['status'], 'receipt': relative(scoped_path), 'receipt_sha256': digest(scoped_path),
                'source_cases_applied': 15, 'existing_option_corrections': 4,
                'original_specifications_and_approval_counts_preserved': True}
            after.setdefault('live_dropbox_metadata_overlays', {})['individual-count-current-links-2026-10-20'] = {
                'application_scope': 'Current count register and displayed links; historic source URLs retained as evidence',
                'MCP4_manual_change': proof(peer / 'MCP4_MANUAL_CURRENT_LINK_OVERLAY_VERIFIED.json'),
                'three_family_renames': proof(peer / 'THREE_FAMILY_CURRENT_LINK_OVERLAY_VERIFIED.json'),
                'current_register_sha256': graph_sha, 'remote_writes_by_count_register': 0}
        elif path == BASE / 'checkpoint.json':
            after.setdefault('current_component_review', {})['individual_catalogue_count_receipt'] = relative(publication_path)
        # Existing counts, names, owner events and source assertions are untouched.
        allowed = {'current_individual_catalogue_count'}
        if path.name == 'specification_review_progress.json':
            allowed |= {'scoped_source_case_and_price_reconciliation', 'live_dropbox_metadata_overlays'}
        elif path == BASE / 'checkpoint.json':
            allowed.add('current_component_review')
        assert all(after.get(k) == value for k, value in before.items() if k not in allowed)
        write(path, after)
        assert read(path) == after
        control_changes.append({'path': relative(path), 'before_sha256': hashlib.sha256(before_raw).hexdigest(),
                                'after_sha256': digest(path), 'backup': str(backup),
                                'changed_top_level_keys': [k for k in after if after[k] != before.get(k)]})
    assert digest(BASE / 'components/evidence/component_register.json') == graph['input_manifest']['source_model']['sha256']
    assert digest(BASE / 'components/reviews/user_classifications.json') == graph['input_manifest']['owner_ledger']['sha256']
    assert digest(historical_book) == '75076dbfb62dab8e98f6355213756a07ae4d16d9222674f28016826d1b7c619e'
    assert digest(workbook) == book_sha and digest(graph_path) == graph_sha
    receipt = {'status': 'PUBLISHED_AND_VERIFIED', 'recorded_utc': timestamp,
               'current_count_register': pointer, 'scoped_source_import': proof(scoped_path),
               'validation': {'saved_file': proof(HERE / 'saved-file-verification.json'),
                              'visual': proof(HERE / 'visual-verification.json'),
                              'independent_graph': proof(graph_proof), 'independent_saved_workbook': proof(book_proof)},
               'source_integrity_before_control_publication': source_checks,
               'control_changes': control_changes,
               'source_model_owner_ledger_and_review97_workbook_unchanged_after_publication': True,
               'new_owner_approval_events': 0, 'remote_writes': 0,
               'all_current_review_rows_classified': True,
               'current_library_unique_design_and_physical_stock_totals_not_invented': True}
    write(publication_path, receipt)
    completion = {'status': 'COMPLETE_FOR_CURRENT_REGISTER_COUNT_SCOPE',
                  'workbook': relative(workbook), 'workbook_sha256': book_sha,
                  'publication_receipt': relative(publication_path), 'publication_receipt_sha256': digest(publication_path),
                  'summary': graph['summary'],
                  'limits': graph['scope_status'],
                  'remaining_owner_question_required_for_this_count_publication': False}
    write(HERE / 'completion.json', completion)
    print(json.dumps({'status': receipt['status'], 'workbook_sha256': book_sha,
                      'register_sha256': graph_sha, 'publication_receipt_sha256': digest(publication_path),
                      'scoped_import_receipt_sha256': digest(scoped_path),
                      'control_files_updated': len(control_changes), 'summary': graph['summary']}, indent=2))

if __name__ == '__main__':
    main()
