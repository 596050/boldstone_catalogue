"""Import one owner-selected display name for two pixel-identical source references."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from import_moonphase_silver_working_specs_62 import ROOT, PATHS, read, sha, rel, write
from import_source_followups_24_25 import canonical_messages

HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch73'
SOURCE = ROOT / 'components/parallel-reviews/fingerprint-unresolved-groups-2026-10-19/offset-rough-canonical-alias-review/owner-canonical-name-selection'
KEY = 'PIXEL-IDENTICAL-G158022-G160001'
SOURCES = ['FINGERPRINT-OFFSET-SPIRAL-VERDIGRIS-G158022', 'FINGERPRINT-ROUGH-CONCENTRIC-VERDIGRIS-G160001']
NAME = 'Fingerprint — Rough Concentric Panels (Verdigris)'
ALIAS = 'Fingerprint — Offset Spiral Panels (Verdigris)'

def main():
    docs = {k: read(v) for k, v in PATHS.items()}
    if (HERE / 'import-receipt.json').exists():
        assert docs['progress']['duplicate_source_image_reviews'][KEY]['canonical_name'] == NAME
        assert not docs['progress']['duplicate_source_image_reviews'][KEY]['canonical_name_decision_pending']
        print(json.dumps({'batch': 73, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    before = copy.deepcopy(docs); guards = {k: sha(v) for k, v in PATHS.items()}; files = []
    def freeze(path, expected):
        path = Path(path); assert sha(path) == expected, str(path)
        dest = HERE / 'sources' / (expected + path.suffix); dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert sha(dest) == expected
        else: dest.write_bytes(path.read_bytes())
        entry = {'source': str(path), 'snapshot': rel(dest), 'sha256': expected}
        if entry not in files: files.append(entry)
        return rel(dest)
    package_path = SOURCE / 'IMPORT_PACKAGE.json'
    freeze(package_path, 'c6d38aad6daeb7ac62bcbbd4cdbcf0df6c105b197f001eb3dbdebfe3c88c421c'); pkg = read(package_path)
    for k in ['owner_decision', 'canonical_overlay', 'source_binding_addendum', 'exact_owner_transcript', 'frozen_sources']:
        freeze(pkg[k]['path'], pkg[k]['sha256'])
    for item in read(pkg['frozen_sources']['path'])['files']: freeze(item['frozen_path'], item['sha256'])
    decision = read(pkg['owner_decision']['path']); overlay = read(pkg['canonical_overlay']['path'])
    messages = canonical_messages([decision['preceding_card_evidence'], decision['owner_evidence']], pkg['source_owner_session'])
    assert [x['line'] for x in messages] == [18469, 18498]
    assert messages[1]['text'] == 'Use “Fingerprint — Rough Concentric Panels (Verdigris)”'
    assert messages[1]['immediately_preceding_assistant']['line'] == 18469
    assert ALIAS in messages[0]['text'] and 'retained as an alias' in messages[0]['text']
    assert decision['canonical_name'] == overlay['canonical_name'] == NAME and overlay['retained_aliases'] == [ALIAS]
    assert not decision['specifications_accepted'] and not decision['physical_component_equivalence_confirmed']
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == c and cp['last_parallel_import']['batch'] == 72
    assert len(u['source_design_name_decisions']) == 19 and sum(x['source_design_key'].startswith('FINGERPRINT-') for x in u['source_design_name_decisions']) == 18 and len(u['design_production_confirmation_decisions']) == 11
    heads = {x[x['metadata_type']]['id']: x[x['metadata_type']] for x in read(HERE / 'current-reference-check.json')['metadata']}
    for source in overlay['sources']:
        node = next(p['source_design_reviews'][k] for k in SOURCES if p['source_design_reviews'][k]['source_asset_id'] == source['file_id'])
        assert node['canonical_source_name'] == source['prior_source_name'] and not node['owner_estimates_accepted']
        current = heads[source['file_id']]; folder = heads[source['folder_id']]
        assert current['path_display'].rsplit('/', 1)[0] == folder['path_display']
        old_ref = next(x for x in read(ROOT / p['duplicate_source_image_reviews'][KEY]['evidence_record'])['source_images'] if x['file_id'] == source['file_id'])
        assert current['rev'] == old_ref['file_revision'] and current['size'] == old_ref['file_bytes']
    protected = {str(path): sha(path) for path in [ROOT / cp['register_workbook'], ROOT / cp['current_review_record'], ROOT / 'components/evidence/component_register.json', ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'canonical-name-decision.json')
    decision.update({'imported_utc': now, 'approval_record': approval, 'verified_review_card_evidence': messages[0], 'verified_owner_evidence': messages[1], 'shared_master_import_performed': True})
    entries = u.setdefault('source_image_canonical_name_decisions', [])
    assert not any(x['decision_id'] == decision['decision_id'] for x in entries)
    entries.append(decision)
    record = p['duplicate_source_image_reviews'][KEY]
    record.update({'canonical_name_decision_pending': False, 'canonical_name': NAME, 'retained_aliases': [ALIAS], 'owner_name_decision': approval, 'owner_answer_recorded': True, 'source_specification_conflicts_pending': True})
    for k in SOURCES:
        node = p['source_design_reviews'][k]
        node.update({'canonical_display_name': NAME, 'retained_source_name_aliases': [ALIAS], 'source_image_name_consolidation_record': approval})
        node['duplicate_source_image_evidence'].update({'canonical_name_decision_pending': False, 'canonical_name': NAME, 'retained_aliases': [ALIAS], 'owner_name_decision': approval})
    pending = next(x for x in cp['pending_source_name_consolidations'] if x['relationship_key'] == KEY)
    pending.update({'owner_answer_recorded': True, 'status': 'CANONICAL_ROUGH_CONCENTRIC_SELECTED;OFFSET_SPIRAL_ALIAS_RETAINED;SOURCE_SPEC_DRAFTS_UNACCEPTED', 'canonical_name': NAME, 'retained_aliases': [ALIAS], 'owner_name_decision': approval})
    c['pending_source_name_consolidations'] = copy.deepcopy(cp['pending_source_name_consolidations'])
    summary = {'batch': 73, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'EXACT_SOURCE_IMAGE_CANONICAL_NAME_AND_HISTORICAL_ALIAS', 'relationship_key': KEY, 'new_canonical_name_selection_events': 1, 'new_source_name_approvals': 0, 'new_specification_approvals': 0, 'new_owner_policy_events': 0, 'new_registered_BC_component_ids': [], 'new_physical_stock_count': 0, 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(package_path), 'receipt_sha256': sha(package_path), 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'CANONICAL_NAME_SELECTED;BOTH_SOURCES_AND_UNACCEPTED_SPEC_DRAFTS_RETAINED'})
    c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
    for doc in docs.values(): doc['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    assert u['specification_approval_counts'] == before['user']['specification_approval_counts']
    assert p['reviews'] == before['progress']['reviews']
    assert all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_'))
    assert all(sha(PATHS[k]) == v for k, v in guards.items()) and all(sha(path) == v for path, v in protected.items())
    freeze(HERE / 'current-reference-check.json', sha(HERE / 'current-reference-check.json'))
    write(HERE / 'before-import.json', before); write(HERE / 'canonical-name-decision.json', decision); write(HERE / 'source-manifest.json', {'files': files, 'verified_messages': messages})
    for k, path in PATHS.items(): write(path, docs[k])
    write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'decision_id': decision['decision_id'], 'protected_sha256': protected, 'shared_after_sha256': {k: sha(v) for k, v in PATHS.items()}})
    print(json.dumps({'batch': 73, 'status': 'APPLIED', 'canonical_name': NAME, 'working_field_groups_unchanged': 112}))

if __name__ == '__main__': main()
