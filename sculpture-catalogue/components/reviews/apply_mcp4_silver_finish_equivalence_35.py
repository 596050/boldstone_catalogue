"""Record one owner-confirmed MCP4 finish across two stable Dropbox reference groups."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/silver-finish-comparison'
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch35'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n'); temp.replace(path)


def main():
    paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json',
             'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(v) for k, v in paths.items()}
    cid, source_vid, vid = 'BC-MCP-4', 'MCP4-SILVER', 'MCP4-SILVER-BRONZE-25'
    qid = 'MCP4-SILVER-VS-SILVER-BRONZE-FINISH-EQUIVALENCE-01'
    did = cid + ':' + source_vid + ':FINISH-REFERENCE-EQUIVALENCE:OWNER-LINE17463'
    if (HERE / 'import-receipt.json').exists():
        assert sum(x['decision_id'] == did for x in docs['user']['finish_reference_equivalence_decisions']) == 1
        assert docs['progress']['canonical_variant_aliases'][cid + '|' + source_vid]['canonical_variant_id'] == vid
        print(json.dumps({'batch': 35, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    before = copy.deepcopy(docs); guards = {k: sha(v) for k, v in paths.items()}
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == c and cp['current_question_id'] == qid and not cp['current_answer_recorded']
    cardpath = BASE / 'component-review.json'; card = read(cardpath)
    assert sha(cardpath) == p['finish_reference_equivalence_reviews'][qid]['review_record_sha256']
    evidence = read(BASE / 'owner-answer-evidence.json')
    messages = canonical_messages([evidence['preceding_assistant'], evidence['owner']], '01a144ab-1a7c-7223-a403-73a4d53d70ff')
    assert [x['line'] for x in messages] == [17456, 17463]
    assert messages[-1]['text'] == 'Yes: Should both groups be catalogued together as “Moon Crater Phase 4 — Silver and Bronze” — one finish record?'
    assert '__002.jpg' in messages[0]['text'] and '__002.jpeg' in messages[0]['text'] and 'one finish record' in messages[0]['text']
    live = read(BASE / 'owner-answer-live-listings.json'); cached = read(BASE / 'cached-media-manifest.json')
    headcheck = read(HERE / 'current-reference-check.json'); metadata = headcheck['metadata']
    for field in ['primary_image', 'comparison_image']:
        previous = card[field]; head = next(x['file'] for x in metadata if x.get('file', {}).get('id') == previous['id'])
        assert all(head[k] == previous[k] for k in ['id', 'name', 'size', 'rev', 'path_display'])
    groups = [('G215', 'silver', card['containing_folder']), ('G051', 'silver_bronze', card['comparison_folder'])]
    references = []
    for group_ref, key, folder in groups:
        listing = live['listings'][key]; assert not listing['has_more'] and not listing['cursor']
        head = next(x['folder'] for x in metadata if x.get('folder', {}).get('id') == folder['id'])
        assert head['path_display'] == folder['path_display']
        expected = {x['file_id']: x for x in cached['records'] if x['folder_id'] == folder['id']}
        assert set(expected) == {x['file_id'] for x in listing['entries']}
        for item in listing['entries']:
            source = expected[item['file_id']]
            assert item['name'] == source['name'] and item['file']['size'] == source['baseline_source_bytes']
            assert item['path_display'].rsplit('/', 1)[0] == folder['path_display']
            references.append({'file_id': item['file_id'], 'folder_id': folder['id'], 'group_ref': group_ref,
                               'name': item['name'], 'path_display': item['path_display'], 'bytes': item['file']['size'],
                               'image_url': 'https://www.dropbox.com/home' + quote(folder['path_display'], safe='/') + '?preview=' + quote(item['name']),
                               'folder_url': folder['open_in_dropbox_url'], 'checked_utc': live['checked_utc']})
    assert len(references) == len({x['file_id'] for x in references}) == 18
    parent = p['reviews'][cid]; target = parent['size_finish_variants'][vid]
    assert target['identity_confirmed'] and not target['proposals_approved'] and len(target['specification_proposals']) == 6
    assert any(x['variant_id'] == source_vid for x in parent['pending_size_finish_variants'])
    protected = {str(path): sha(path) for path in [cardpath, ROOT / cp['register_workbook'], ROOT / 'components/evidence/component_register.json',
        ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat(); approval_path = HERE / 'finish-reference-equivalence-approval.json'
    scope = 'Owner confirmed G215 Silver and G051 Silver and Bronze reference groups as one MCP4 Silver and Bronze finish record. All 18 file IDs and both containing folder IDs retained. Existing six specification groups and platform claims keep their original applicability and approval states. Physical casts, moulds, stock, exact dimensions and prices are not merged or verified.'
    decision = {'schema_version': 1, 'decision_id': did, 'recorded_utc': now, 'component_id': cid, 'source_variant_id': source_vid,
        'canonical_size_finish_variant_id': vid, 'canonical_name': target['canonical_name'], 'owner_question_id': qid,
        'authoritative_user_evidence': messages[-1], 'preceding_review_card_evidence': messages[0], 'approval_record': rel(approval_path),
        'scope': scope, 'finish_reference_equivalence_confirmed': True, 'source_group_refs': ['G215', 'G051'],
        'source_folder_ids': [x[2]['id'] for x in groups], 'source_file_ids': [x['file_id'] for x in references],
        'new_name_approvals': 0, 'new_registered_BC_component_ids': [], 'new_specification_approvals': 0,
        'physical_cast_mould_stock_merge': False, 'exact_platform_match_upgraded': False, 'remote_mutations': 0, 'new_original_downloads': 0}
    u.setdefault('finish_reference_equivalence_decisions', []).append(decision)
    p['canonical_variant_aliases'][cid + '|' + source_vid] = {'canonical_component_id': cid, 'canonical_variant_id': vid,
        'approval_record': rel(approval_path), 'specification_approvals_retain_original_scope': True}
    parent['pending_size_finish_variants'] = [x for x in parent['pending_size_finish_variants'] if x['variant_id'] != source_vid]
    target.update({'finish_reference_equivalence_confirmed': True, 'finish_reference_equivalence_approval': rel(approval_path),
        'reference_file_ids': [x['file_id'] for x in references], 'reference_folder_ids': decision['source_folder_ids'],
        'reference_groups': [{'group_ref': ref, 'folder_id': folder['id'], 'folder_path': folder['path_display'], 'folder_url': folder['open_in_dropbox_url']} for ref, _, folder in groups],
        'reference_files': references, 'scope': scope, 'review_record': rel(HERE / 'confirmed-finish-review.json')})
    target.setdefault('former_names', []).append('Moon Crater Phase 4 — Silver')
    target['photo_coverage']['review_scope'] = '18 cached thumbnails across G215 and G051 inspected; complete live ID/name/size/path listings checked. No fresh original-byte hashes fetched.'
    for item in references:
        prior = p['asset_assignment_overrides'].get(item['file_id'], {})
        p['asset_assignment_overrides'][item['file_id']] = prior | {'file_id': item['file_id'], 'folder_id': item['folder_id'], 'component_ids': [cid],
            'size_finish_variant_ids': [vid], 'canonical_size_finish_variant_id': vid, 'path_display': item['path_display'],
            'owner_finish_reference_equivalence_approval': rel(approval_path), 'review_record': target['review_record'],
            'assignment_status': 'OWNER_CONFIRMED_MCP4_SILVER_AND_BRONZE_FINISH_REFERENCE;PHYSICAL_CAST_AND_SPECS_UNVERIFIED'}
    for group_ref, key, folder in groups:
        override = p['catalogue_group_overrides'].setdefault(group_ref, {})
        override.update({'current_family': 'Moon Crater Phase', 'current_name': folder['name'], 'current_folder_id': folder['id'],
            'current_folder_path': folder['path_display'], 'file_count': len(live['listings'][key]['entries']), 'component_ids': [cid],
            'canonical_size_finish_variant_id': vid, 'owner_finish_reference_equivalence_approval': rel(approval_path),
            'assignment_status': 'Owner confirmed finish: Moon Crater Phase 4 — Silver and Bronze (MCP4-SILVER-BRONZE-25). Two reference folders, one finish record; physical casts and stock unverified.'})
    for consolidation in [p['canonical_component_consolidations']['BC-CONCAVE'], c['current_catalogue_overlays']['Concave Moon']]:
        consolidation.update({'Silver_vs_Silver_Bronze_finish_equivalence_confirmed': True, 'Silver_finish_equivalence_approval': rel(approval_path)})
    p['finish_reference_equivalence_reviews'][qid].update({'state': 'OWNER_CONFIRMED_ONE_FINISH_REFERENCE_RECORD', 'approval_record': rel(approval_path)})
    p['current_finish_reference_equivalence_review'] = copy.deepcopy(p['finish_reference_equivalence_reviews'][qid])
    cp.update({'current_answer_recorded': True, 'current_finish_reference_equivalence_answer_recorded': True,
        'current_finish_reference_equivalence_approval': rel(approval_path), 'state': 'MCP4_SILVER_REFERENCE_GROUPS_CONSOLIDATED;VERDIGRIS_COMPARISON_NEXT',
        'answer_state': scope, 'current_size_finish_variant_id': vid, 'last_finish_reference_equivalence_approval': rel(approval_path)})
    c['interactive_review_state'].update({'state': cp['state'], 'current_size_finish_variant_id': vid,
        'current_finish_reference_equivalence_answer_recorded': True, 'last_finish_reference_equivalence_approval': rel(approval_path)})
    c['next_work'][0] = 'Silver reference groups are one owner-confirmed MCP4 Silver and Bronze finish. Compare the native and former Concave Verdigris references next, then review Verdigris/Rust.'
    summary = {'batch': 35, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'MAIN_OWNER_FINISH_REFERENCE_EQUIVALENCE',
        'component_id': cid, 'canonical_size_finish_variant_id': vid, 'new_finish_reference_equivalence_decisions': 1,
        'new_name_approvals': 0, 'new_full_specification_approvals': 0, 'reference_file_ids': 18, 'source_folder_ids': 2,
        'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(approval_path), 'approval_imported': True,
        'import_receipt': summary['receipt'], 'status': 'OWNER_FINISH_EQUIVALENCE_APPLIED;SPECIFICATIONS_RETAIN_PRIOR_SCOPE'})
    c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for doc, field in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: doc[field] = copy.deepcopy(summary)
    p['latest_main_owner_review'] = copy.deepcopy(summary)
    for doc in docs.values(): doc['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(c)
    assert target['specification_proposals'] == before['progress']['reviews'][cid]['size_finish_variants'][vid]['specification_proposals']
    assert target['platform_mapping'] == before['progress']['reviews'][cid]['size_finish_variants'][vid]['platform_mapping']
    assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'] and u['specification_approval_counts'] == before['user']['specification_approval_counts']
    assert all(u[k] == value for k, value in before['user'].items() if k != 'updated_utc')
    assert c['counts'] == before['component']['counts'] and cp['deferred_reviews'] == before['walkthrough']['deferred_reviews']
    assert all(sha(paths[k]) == value for k, value in guards.items()) and all(sha(Path(k)) == value for k, value in protected.items())
    write(HERE / 'before-import.json', before); write(approval_path, decision); write(HERE / 'confirmed-finish-review.json', target)
    frozen = []
    for source in [cardpath, BASE / 'owner-answer-evidence.json', BASE / 'owner-answer-live-listings.json', BASE / 'cached-media-manifest.json', HERE / 'current-reference-check.json']:
        dest = HERE / 'sources' / (sha(source) + source.suffix); dest.parent.mkdir(exist_ok=True); dest.write_bytes(source.read_bytes())
        frozen.append({'source': str(source), 'snapshot': rel(dest), 'sha256': sha(dest), 'bytes': dest.stat().st_size})
    write(HERE / 'source-manifest.json', {'files': frozen, 'verified_messages': messages})
    for k, path in paths.items(): write(path, docs[k])
    write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary,
        'protected_sha256': protected, 'shared_after_sha256': {k: sha(path) for k, path in paths.items()}})
    print(json.dumps({'batch': 35, 'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'finish_records': 1, 'reference_files': 18, 'new_specification_approvals': 0}))


if __name__ == '__main__': main()
