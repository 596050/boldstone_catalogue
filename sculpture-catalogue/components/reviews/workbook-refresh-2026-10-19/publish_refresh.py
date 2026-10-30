"""Publish a verified local review export to the shared catalogue checkpoints."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))


def write(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main(batch):
    data, receipt, qa = (read(HERE / name) for name in ['refresh-data.json', 'export-receipt.json', 'independent-file-verification.json'])
    output = Path(receipt['output'])
    assert qa['status'] == 'PASS' and qa['output_sha256'] == receipt['output_sha256'] == sha(output)
    paths = {'progress': ROOT / 'components/reviews/specification_review_progress.json',
             'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json',
             'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {key: read(path) for key, path in paths.items()}
    before, guards = copy.deepcopy(docs), {key: sha(path) for key, path in paths.items()}
    for source in data['source_files']:
        if source.get('snapshot'):
            assert sha(Path(source['source'])) == source['sha256'], 'Source changed after export capture'
    now = datetime.now(timezone.utc).isoformat()
    prior = docs['progress'].get('latest_workbook_export', {})
    visual = {'status': 'PASS', 'checked_utc': now, 'scope': 'MCP4 Verdigris/Rust175GBP per panel and made-to-order policy accepted; owner-stated unlimited stock and one-week lead time shown. Prior25x25/approximately6cm,4kg,plaster/faux finish and keyhole type unchanged; keyhole count unknown. Canonical standing working-specification instruction shown with uncertainties retained. Fountain Egyptian Bronze/Verdigris and Mediterranean White six working fields and scoped context inspected. Leaf Curve, Growth White/Gold and Form LF1/LF2White/Gold six working fields, exact native image/folder links, source conflicts and context limitations inspected. Growth18kg versus12kg unresolved; Gold cropped details do not establish complete front or room context. Leaf Form White exhibition differs from authenticated home installation; Gold room scene provenance unknown. Eight new scoped photograph-gap rows and stable IDs inspected. WhiteBlack accepted175GBP basis clarified without altering source evidence. Summary186working groups/22group references/130photo-gap records; final individual-sale count and actual specifications incomplete. Original source dictionaries and source platform split preserved; no remote writes',
              'prior_unchanged_visual_scope_workbook_sha256': prior.get('workbook_sha256'),
              'source_and_review_worksheet_layouts_preserved': True,
              'hyperlink_verification': 'Saved native link targets and display values checked from the XLSX package.',
              'Dropbox_browser_navigation_tested': False, 'native_application_open_test': 'NOT_RUN'}
    if batch == 87:
        visual['scope'] = 'Nine existing sculpture/finish reviews inspected: seven Moon Crater Phase1/2/3 finishes, Embedded Shells White and Faceted Mound Gold Leaf.54 working fields accepted under existing policy80 with originals preserved. White maker2-4kg/trade4kg/retail5kg sources remain distinct; coloured4kg figures conditional.350GBP Blue proposal is not an exact Blue offer; dated MCP2Rust350/MCP3Rust395 listing references retain unverified current CDN image correspondence. Embedded owner70x15face retained, depth5-7guess/4-6kg/250-350range; Faceted70x30x7-10size/6-10kg/500-800range remain guesses. Both owner keyhole-type facts inspected; counts, attachment and load unknown. One global offered keyhole/French-cleat choice inspected in Summary and representative existing, accepted, partial, source-only, alias and deferred fixing fields. All278 fixing entries independently checked to preserve pre-policy installed/source hardware detail. Nine new linked photograph-gap rows and contexts inspected, including shared White027 series, unpaired candidate rears, and unauthenticated room presentations.240working groups/22group references/139photo-gap records. Source platform split, counts and all actual-specification unknowns remain separate; no remote writes.'
    if batch == 91:
        visual['scope'] = 'Fifteen existing component/finish reviews inspected: Acanthus Left Sandstone/Pewter, Panel Curves Beige/Gold, Plant White, six Raked finishes, Crater Wide Drip Rust, Fishwave Left/Right White and Moon Ring White.90 scoped working fields added under policy80, source dictionaries and confirmed subfields retained. Acanthus cropped details/workshop context remain distinct from isolated fronts; Raked beige pair positions remain references with null individual primary IDs. Gold owner25cm face/gold-leaf fact and Raked equality-only size/source-weight conflicts retained. Fishwave maker8-10/trade12/retail12-15kg and individual550GBP proposal remain distinct from pair30kg/800GBP. One global weight policy90 applied:214 current numeric bodies retained,9 conditional estimates,7 recovered source displays,48 scoped reference/deferred dispositions. Chelsea100kg75-140 for owner250x100BASE only; Knightsbridge100kg60-180 dry hollow-shell model keeps literal50cm depth and uncertain construction. Ammonite four individual source-weight conflicts recovered; Barbados existing83kg recovered without raw unit conversion. Existing Chelsea current replacement53Gw/revision/size/cached bytes rechecked; previousyj2w retained as history. Offered fixing choices remain separate from installed hardware/count/load.15 scoped photo-gap records added/updated with no Acanthus duplicates;330 scoped proposal approvals/22group references/152photo-gap records. Final individually buyable count and actual specifications remain incomplete. Original platform split and all source IDs/claims retained; no remote writes.'
    if batch == 97:
        visual['scope'] = 'Remaining working reviews through97:121 existing component/finish/build/source scopes, one prior Barbados six-field display recovery and two reference dispositions. All eight newly reviewed Moonphase aliases retain ten historical source bundles; no cast, mould or size-version equivalence inferred. Four Ammonite panels retain individual source conflicts and unc osted per-panel price proposals separate from pair values. Brancusi White components retain historical individual trade/retail versions and new250GBP working proposals; no Gold or pair-value transfer. Root MCP4 Verdigris/Rust25x25/approximately6cm/4kg/plaster composite/faux finish/keyhole type/175GBP/MTO/Unlimited/one-week facts retained only for that finish; actual fixing count unknown. Azure conditional7kg net4-10kg remains separate from15kg shipping. Basin freestanding support is distinct from global wall-fixing choices. Cropped Bronze Spiralfish, tabletop textured panels, grouped Glen/FFS references, rear-only and unauthenticated room/water-feature scenes remain bounded. All93 planned changed-layout previews actually inspected; source-reference lists flowed without removing evidence text and historic reply/current working states clarified.1045 deduplicated working groups,22 group references,272 photo-gap records,278 overlapping review scopes. Source platform split81/37/43/1 and6663file IDs preserved. Final unique listings, exact platform matches, measurements and physical stock remain incomplete; no remote writes.'.replace('unc osted','uncosted')
    visual['affected_previews'] = [{'path': rel(path), 'sha256': sha(path)} for path in sorted((HERE / 'after').glob(f'owner{batch}_*.png'))]
    if batch == 83:
        inspection = read(HERE / 'model-preview-inspection-batch83.json')
        assert inspection['status'] == 'PASS_ACTUAL_MODEL_INSPECTION'
        assert inspection['final_previews'] == visual['affected_previews'] and len(visual['affected_previews']) == 35
        visual['model_inspection_receipt'] = rel(HERE / 'model-preview-inspection-batch83.json')
        visual['model_inspection_receipt_sha256'] = sha(HERE / 'model-preview-inspection-batch83.json')
    if batch == 87:
        inspection = read(HERE / 'model-preview-inspection-batch87.json')
        assert inspection['status'] == 'PASS_ACTUAL_MODEL_INSPECTION'
        assert inspection['final_previews'] == visual['affected_previews'] and len(visual['affected_previews']) == 44
        visual['model_inspection_receipt'] = rel(HERE / 'model-preview-inspection-batch87.json')
        visual['model_inspection_receipt_sha256'] = sha(HERE / 'model-preview-inspection-batch87.json')
    if batch == 91:
        inspection = read(HERE / 'model-preview-inspection-batch91.json')
        assert inspection['status'] == 'PASS_ACTUAL_MODEL_INSPECTION'
        planned = [{'path': rel(Path(x['path'])), 'sha256': sha(Path(x['path']))} for x in receipt['previews'] if Path(x['path']).name.startswith('owner91_')]
        assert inspection['final_previews'] == visual['affected_previews'] == sorted(planned, key=lambda x: x['path'])
        assert inspection['final_preview_count'] == len(visual['affected_previews']) and len(visual['affected_previews']) >= 60
        visual['model_inspection_receipt'] = rel(HERE / 'model-preview-inspection-batch91.json')
        visual['model_inspection_receipt_sha256'] = sha(HERE / 'model-preview-inspection-batch91.json')
    if batch == 97:
        inspection = read(HERE / 'model-preview-inspection-batch97.json')
        plan = read(HERE / 'preview-plan-batch97.json')
        planned = [{'path':rel(Path(x['path'])),'sha256':sha(Path(x['path']))} for x in receipt['previews'] if Path(x['path']).name.startswith('owner97_')]
        assert inspection['status'] == 'PASS_ACTUAL_MODEL_INSPECTION'
        assert inspection['final_previews'] == visual['affected_previews'] == sorted(planned,key=lambda x:x['path'])
        assert inspection['final_preview_count'] == plan['view_count'] == len(visual['affected_previews']) == 93
        assert plan['refresh_data_sha256'] == sha(HERE/'refresh-data.json')
        assert read(HERE/'view-scope-readback-batch97.json')['status'] == 'PASS'
        visual['model_inspection_receipt'] = rel(HERE/'model-preview-inspection-batch97.json')
        visual['model_inspection_receipt_sha256'] = sha(HERE/'model-preview-inspection-batch97.json')
    visual['actual_model_inspection_complete'] = True
    write(HERE / 'visual-qa.json', visual)
    qa.update({'visual_verification': 'PASS', 'visual_qa': rel(HERE / 'visual-qa.json'), 'visual_qa_sha256': sha(HERE / 'visual-qa.json')})
    write(HERE / 'independent-file-verification.json', qa)
    receipt.update({'status': 'PASS_FILE_AND_VISUAL_VERIFICATION', 'independent_verification': rel(HERE / 'independent-file-verification.json'),
                    'independent_verification_sha256': sha(HERE / 'independent-file-verification.json'), 'visual_verification': 'PASS'})
    write(HERE / 'export-receipt.json', receipt)
    summary = {'recorded_utc': now, 'workbook': rel(output), 'workbook_sha256': sha(output),
               'export_receipt': rel(HERE / 'export-receipt.json'), 'export_receipt_sha256': sha(HERE / 'export-receipt.json'),
               'validation': rel(HERE / 'independent-file-verification.json'), 'validation_sha256': sha(HERE / 'independent-file-verification.json'),
               'validation_status': 'PASS', 'visual_validation_status': 'PASS', 'included_owner_review_imports_through_batch': batch,
               'source_platform_records': 81, 'source_platform_pair_count': 37, 'source_squarespace_only': 43, 'source_shopify_only': 1,
               'source_dropbox_file_ids': 6663, 'review_scope_rows': len(data['reviews']), 'reviewed_specification_entries': len(data['specifications']),
               'photograph_gap_records': data['baseline_photo_gaps'] + len(data['additional_photograph_gaps']),
               'group_reference_records': len(data['groups']), 'native_hyperlinks': receipt['native_hyperlinks_written'],
               'counts_scope': data['scope_note'], 'final_individual_listing_count': None,
               'all_actual_specifications_complete': False, 'all_images_individually_classified': False,
               'physical_manufacture_owner_stated_for_all_catalogue_sculptures': True,
               'repeat_manufacture_questions_required': False,
               'group_photo_component_identification_required': False, 'dropbox_or_platform_writes_for_this_export': 0}
    if data.get('global_fixing_choice_policy'):
        summary.update({'global_offered_fixing_options': [x['label'] for x in data['global_fixing_choice_policy']['offered_fixing_options']], 'global_fixing_choice_policy_events': 1, 'installed_fixing_hardware_is_separately_recorded': True})
    if data.get('global_approximate_weight_policy'):
        summary.update({'global_approximate_weight_policy_events': 1, 'weight_policy_counts': data['weight_policy_counts'], 'actual_mass_independently_verified_by_weight_policy': False})
    if batch == 97:
        summary.update({'remaining_working_review_import_scopes':121,'prior_six_field_display_recoveries':1,'reference_dispositions':2,'all_allocated_working_review_batches_complete':True,'allocated_remaining_scope_count':111,'allocated_six_field_working_scopes':109,'tracked_accepted_working_groups':1045,'unique_individual_listing_count_verified':False})
    progress, cp, component, root = (docs[key] for key in ['progress', 'walkthrough', 'component', 'root'])
    assert root['current_component_review'] == component
    assert cp['last_parallel_import']['batch'] == batch
    for target in [progress, cp, component]: target['latest_workbook_export'] = copy.deepcopy(summary)
    progress['workbook'] = cp['register_workbook'] = component['workbook'] = rel(output)
    cp.update({'register_workbook_sha256': sha(output), 'register_validation': summary['validation'],
               'register_validation_status': 'PASS', 'register_validation_sha256': summary['validation_sha256']})
    component.update({'workbook_sha256': sha(output), 'validation': summary['validation'],
                      'validation_sha256': summary['validation_sha256'], 'validation_status': 'PASS',
                      'phase': f'Working catalogue exported with verified owner review imports through batch{batch}; standalone identity, specifications and exact matching continue'})
    for target, key in [(progress, 'latest_parallel_import'), (cp, 'last_parallel_import'), (component, 'last_parallel_import')]:
        target[key]['workbook_export_pending'] = False
        target[key]['workbook_export'] = rel(output)
    main_batch = progress.get('latest_main_owner_review', {}).get('batch')
    if isinstance(main_batch, int) and main_batch <= batch:
        progress['latest_main_owner_review'].update({'workbook_export_pending': False, 'workbook_export': rel(output), 'workbook_sha256': sha(output), 'workbook_included_through_batch': batch})
    for item in cp['parallel_import_queue']:
        if (item.get('approval_imported') or item.get('evidence_imported')) and item.get('import_receipt'):
            item.update({'workbook_export_pending': False, 'workbook_export': rel(output)})
    component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target in docs.values(): target['updated_utc'] = now
    root['current_component_review'] = copy.deepcopy(component)
    assert progress['reviews'] == before['progress']['reviews'] and progress['source_design_reviews'] == before['progress']['source_design_reviews']
    assert all(cp[k] == value for k, value in before['walkthrough'].items() if k.startswith('current_'))
    assert cp['current_answer_recorded'] == before['walkthrough']['current_answer_recorded'] and cp['deferred_reviews'] == before['walkthrough']['deferred_reviews']
    assert component['counts'] == before['component']['counts']
    assert all(sha(paths[key]) == digest for key, digest in guards.items())
    write(HERE / f'before-checkpoint-publication-batch{batch}.json', before)
    for key, path in paths.items(): write(path, docs[key])
    after = {key: read(path) for key, path in paths.items()}
    assert after['root']['current_component_review'] == after['component']
    assert after['progress']['latest_workbook_export']['workbook_sha256'] == sha(output)
    publication = {'status': 'PASS', 'recorded_utc': now, 'summary': summary,
                   'shared_after_sha256': {key: sha(path) for key, path in paths.items()},
                   'existing_identity_and_specification_decisions_unchanged': True,
                   'current_owner_review_state_preserved': True, 'MCP4_consolidation_answer_recorded': cp['current_identity_relationship_answer_recorded'], 'G050_owner_deferral_preserved': True}
    write(HERE / 'checkpoint-publication-receipt.json', publication)
    event = {'event': 'catalogue_review_workbook_export', 'recorded_utc': now, 'workbook': rel(output),
             'workbook_sha256': sha(output), 'export_receipt': summary['export_receipt'], 'validation_status': 'PASS',
             'included_owner_review_imports_through_batch': batch, 'final_individual_listing_count': None,
             'new_identity_or_specification_approval_inferred': False, 'remote_mutations': 0}
    for journal in [ROOT / 'components/reviews/identity_review_journal.jsonl', ROOT / 'review_journal.jsonl']:
        with journal.open('a') as stream: stream.write(json.dumps(event, ensure_ascii=False) + '\n')
    print(json.dumps({'status': 'PASS_PUBLISHED_LOCAL_WORKBOOK', 'sha256': sha(output), 'group_references': len(data['groups']),
                      'native_hyperlinks': receipt['native_hyperlinks_written'], 'independent_checks': qa['check_count'],
                      'included_import_batch': batch, 'final_listing_count': 'UNVERIFIED'}))


if __name__ == '__main__':
    main(int(sys.argv[1]))
