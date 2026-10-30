"""Point the catalogue controls to the verified consolidated master."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
read = lambda p: json.loads(p.read_text())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def write(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)

def main():
    gpath = HERE / 'canonical-master-register.json'
    g = read(gpath)
    export = read(HERE / 'export-receipt.json')
    check = read(HERE / 'saved-file-verification.json')
    visual = read(HERE / 'visual-verification.json')
    dependency = read(HERE / 'formula-dependency-check.json')
    book = Path(export['output'])
    assert check['status'] == visual['status'] == dependency['status'] == 'PASS'
    assert digest(book) == export['workbook_sha256'] == check['workbook_sha256'] == visual['workbook_sha256']
    assert digest(gpath) == export['master_register_sha256'] == check['master_register_sha256']
    assert g['summary']['options_with_six_working_fields'] == 184
    source_preservation = []
    for key, record in g['master_input_manifest'].items():
        source = Path(record['source'])
        actual = digest(source)
        assert actual == record['sha256'], 'Source changed before publication: ' + key
        source_preservation.append({'source_key': key, 'sha256': actual, 'unchanged': True})
    old_review = BASE / 'outputs/01a144ab-1a7c-7223-a403-73a4d53d70ff/Boldstone_Sculpture_Catalogue_Review_2026-10-20.xlsx'
    assert digest(old_review) == '75076dbfb62dab8e98f6355213756a07ae4d16d9222674f28016826d1b7c619e'
    assert g['original_review_specification_assertions'] == read(Path(g['master_input_manifest']['count_register']['snapshot']))['original_review_specification_assertions']
    relative = lambda p: str(p.relative_to(BASE))
    proof = lambda p: {'path': relative(p), 'sha256': digest(p)}
    now = datetime.now(timezone.utc).isoformat()
    publication = HERE / 'publication-receipt.json'
    pointer = {'recorded_utc': now, 'status': 'CURRENT_CONSOLIDATED_MASTER',
               'workbook': relative(book), 'workbook_sha256': digest(book),
               'register': relative(gpath), 'register_sha256': digest(gpath),
               'publication_receipt': relative(publication),
               'main_sheet': 'Master Catalogue', 'specification_value_owner_sheet': 'Specifications',
               'summary': g['summary'], 'all184_options_have_six_working_fields_recorded': True,
               'working_estimates_and_source_conflicts_retained': True,
               'all_actual_specifications_complete': False, 'physical_stock_quantity': None,
               'whole_library_unique_design_total': None,
               'latest_corrections': 'Four earlier price/size corrections, four additional six-field working completions and36 saved Wall Circle proposal displays',
               'current_path_scope': 'Verified Moon Crater Phase4, three family renames and four Ammonite arrangement/context folder renames',
               'link_scope': 'Saved native hyperlinks and stable-ID/path overlays verified; no live HTTP access audit',
               'historical_review_workbook_preserved': relative(old_review),
               'historical_count_workbook_preserved': g['master_input_manifest']['count_workbook']['source'],
               'source_platform_records_are_preserved_snapshots': True,
               'exact_platform_matches_not_upgraded': True,
               'dropbox_and_platform_writes_for_consolidation': 0}
    export_record = {'recorded_utc': now, 'workbook': relative(book), 'workbook_sha256': digest(book),
                     'export_receipt': relative(HERE / 'export-receipt.json'), 'export_receipt_sha256': digest(HERE / 'export-receipt.json'),
                     'validation': relative(HERE / 'saved-file-verification.json'), 'validation_sha256': digest(HERE / 'saved-file-verification.json'),
                     'validation_status': 'PASS', 'visual_validation_status': 'PASS',
                     'workbook_layout': 'CONSOLIDATED_MASTER_CATALOGUE_V1',
                     'individual_option_records': 184, 'identified_component_identities': 111,
                     'current_specification_field_groups': 1104, 'original_specification_records': 1668,
                     'source_platform_records': 81, 'wall_circle_native_combinations': 144,
                     'all_current_options_have_six_working_fields': True,
                     'all_actual_specifications_complete': False, 'all_images_individually_classified': False,
                     'physical_specifications_independently_verified': False,
                     'final_individual_listing_count': None,
                     'counts_scope': '184 individually described catalogue options, including seven Wall Circle visual entries and one image-unbound Long size option. Not a physical-stock or whole-library unique-design total.',
                     'native_hyperlinks': check['native_hyperlinks'],
                     'global_offered_fixing_options': ['Keyhole fixing', 'French cleat'],
                     'installed_fixing_hardware_is_separately_recorded': True,
                     'dropbox_or_platform_writes_for_this_export': False}

    controls = [BASE / 'components/reviews/specification_review_progress.json', BASE / 'components/checkpoint.json', BASE / 'checkpoint.json']
    changes = []
    for path in controls:
        before_raw = path.read_bytes()
        before = json.loads(before_raw)
        after = copy.deepcopy(before)
        backup = HERE / 'inputs' / (path.parent.name + '-' + path.name + '.before-publication')
        assert not backup.exists(), 'Publication already performed; inspect the existing receipt'
        backup.write_bytes(before_raw)
        after['current_master_catalogue'] = pointer
        after['current_master_workbook'] = relative(book)
        after['current_master_register'] = relative(gpath)
        after['updated_utc'] = now
        if path != BASE / 'checkpoint.json':
            after.setdefault('prior_workbook_exports', []).append({'preserved_at': now, 'role': 'Historical review workbook before master consolidation',
                                                                   'workbook': before.get('workbook'), 'latest_workbook_export': before.get('latest_workbook_export')})
            after['source_review_workbook'] = before.get('workbook')
            after['workbook'] = relative(book)
            after['latest_workbook_export'] = export_record
            if 'workbook_sha256' in after: after['workbook_sha256'] = digest(book)
            after['all_working_option_specifications_recorded'] = True
            if path.name == 'specification_review_progress.json':
                after['current_working_specification_completion'] = {'status': 'APPLIED_TO_CURRENT_MASTER',
                    'source_packet': g['master_working_completion']['packet'], 'source_seal': g['master_working_completion']['seal'],
                    'option_ids': g['master_working_completion']['option_ids'], 'field_groups': 24,
                    'current_master_register_sha256': digest(gpath), 'new_owner_name_or_identity_events': 0,
                    'photo_and_physical_verification_gaps_retained': True}
                after['wall_circle_current_display_recovery'] = {'status': 'SAVED_PROPOSAL_TEXT_RESTORED', 'field_groups': 36,
                    'uncertainty_and_existing_working_approval_retained': True, 'new_acceptance_events': 0,
                    'current_master_register_sha256': digest(gpath)}
            else:
                after['phase'] = 'Consolidated master published with184 individual options and six working specification groups per option'
                after['current_master_validation'] = proof(HERE / 'saved-file-verification.json')
        else:
            current = after.setdefault('current_component_review', {})
            current['current_master_catalogue'] = pointer
            current['workbook'] = relative(book)
            current['workbook_sha256'] = digest(book)
            after['counts_scope_note'] = before.get('counts_scope_note', '') + ' Current accepted option/specification data is in current_master_catalogue; earlier top-level source counts remain historical.'
        if 'current_individual_catalogue_count' in after:
            after['current_individual_catalogue_count']['current_file_superseded_by'] = relative(book)
            after['current_individual_catalogue_count']['role'] = 'Preserved count reconciliation. Use current_master_catalogue for current specifications and Dropbox paths.'
        # Owner decisions, legacy coverage counts and source model records are not reclassified.
        for key in ['reviews', 'decisions', 'identity_confirmation_counts', 'specification_approval_counts', 'counts', 'coverage',
                    'global_fixing_choice_policy', 'global_approximate_weight_policy', 'group_photo_review_policy']:
            if key in before: assert after[key] == before[key], 'Protected source control changed: ' + key
        write(path, after)
        assert read(path) == after
        changes.append({'path': relative(path), 'before_sha256': hashlib.sha256(before_raw).hexdigest(), 'after_sha256': digest(path),
                        'changed_keys': [k for k in after if after[k] != before.get(k)], 'backup': str(backup)})

    assert digest(BASE / 'components/reviews/user_classifications.json') == g['master_input_manifest']['owner_ledger']['sha256']
    assert digest(BASE / 'components/evidence/component_register.json') == g['master_input_manifest']['source_component_model']['sha256']
    assert digest(book) == check['workbook_sha256']
    write(BASE / 'current-master.json', pointer)
    receipt = {'status': 'PUBLISHED_AND_VERIFIED', 'recorded_utc': now, 'current_master': pointer,
               'export': proof(HERE / 'export-receipt.json'), 'saved_file_validation': proof(HERE / 'saved-file-verification.json'),
               'visual_validation': proof(HERE / 'visual-verification.json'), 'working_dependency_validation': proof(HERE / 'formula-dependency-check.json'),
               'source_integrity_before_control_publication': source_preservation, 'control_changes': changes,
               'owner_ledger_source_model_old_count_register_and_workbooks_preserved': True,
               'original1668_specification_records_preserved': True, 'current_option_identities_and_counts_unchanged': True,
               'new_owner_name_or_identity_events': 0, 'remote_writes': 0}
    write(publication, receipt)
    write(HERE / 'completion.json', {'status': 'COMPLETE', 'workbook': relative(book), 'workbook_sha256': digest(book),
                                    'publication_receipt': relative(publication), 'publication_receipt_sha256': digest(publication),
                                    'summary': g['summary'], 'user_task': 'Consolidate184 individual options, accepted specifications and latest corrections into one current master workbook'})
    print(json.dumps({'status': receipt['status'], 'workbook': relative(book), 'workbook_sha256': digest(book),
                      'master_register_sha256': digest(gpath), 'publication_receipt_sha256': digest(publication),
                      'controls_updated': len(changes), 'options':184, 'working_specification_groups':1104}, indent=2))

if __name__ == '__main__': main()
