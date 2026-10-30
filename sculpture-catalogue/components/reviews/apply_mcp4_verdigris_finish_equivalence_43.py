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
BASE = ROOT / 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/verdigris-finish-comparison'
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch43'
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
    cid, source_vid, vid = 'BC-MCP-4', 'MCP4-VERDIGRIS', 'MCP4-VERDIGRIS-25'
    qid = 'MCP4-NATIVE-VS-FORMER-CONCAVE-VERDIGRIS-FINISH-EQUIVALENCE-01'
    did = cid + ':' + source_vid + ':FINISH-REFERENCE-EQUIVALENCE:OWNER-LINE18425'
    if (HERE / 'import-receipt.json').exists():
        assert sum(x['decision_id'] == did for x in docs['user']['finish_reference_equivalence_decisions']) == 1
        assert docs['progress']['canonical_variant_aliases'][cid + '|' + source_vid]['canonical_variant_id'] == vid
        print(json.dumps({'batch': 43, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    before = copy.deepcopy(docs); guards = {k: sha(v) for k, v in paths.items()}
    u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == c and cp['current_question_id'] == qid and not cp['current_answer_recorded']
    cardpath = BASE / 'component-review.json'; card = read(cardpath)
    assert sha(cardpath) == p['finish_reference_equivalence_reviews'][qid]['review_record_sha256']
    evidence = read(BASE / 'owner-answer-evidence.json')
    messages = canonical_messages([evidence['preceding_assistant'], evidence['owner']], '01a144ab-1a7c-7223-a403-73a4d53d70ff')
    assert [x['line'] for x in messages] == [18408, 18425]
    assert messages[-1]['text'] == 'Yes:\nShould these two Verdigris photo groups also be catalogued together as “Moon Crater Phase 4 — Verdigris” — one finish record?'
    assert '__001.png' in messages[0]['text'] and '__005.jpeg' in messages[0]['text'] and 'one finish record' in messages[0]['text']
    live = read(BASE / 'owner-answer-live-listings.json'); cached = read(BASE / 'cached-media-manifest.json')
    headcheck = read(HERE / 'current-reference-check.json'); metadata = headcheck['metadata']
    for field in ['primary_image', 'comparison_image']:
        previous = card[field]; head = next(x['file'] for x in metadata if x.get('file', {}).get('id') == previous['id'])
        assert all(head[k] == previous[k] for k in ['id', 'name', 'size', 'rev', 'path_display'])
    group_ids = {'id:cnqzTNngPVsAAAAAAAyjNw': 'G216', 'id:cnqzTNngPVsAAAAAAAyjMw': 'G217', 'id:cnqzTNngPVsAAAAAAAygnw': 'G052', 'id:cnqzTNngPVsAAAAAAAyjyQ': 'G053'}
    groups = [(group_ids[g['folder']['id']], g['listing'], g['folder'] | {'open_in_dropbox_url': 'https://www.dropbox.com/home' + quote(g['folder']['path_display'], safe='/')}) for g in live['groups']]
    assert len(groups) == 4 and {x[0] for x in groups} == set(group_ids.values())
    references = []
    for group_ref, listing, folder in groups:
        assert not listing['has_more'] and not listing['cursor']
        head = next(x['folder'] for x in metadata if x.get('folder', {}).get('id') == folder['id'])
        assert head['path_display'] == folder['path_display']
        expected = {x['file_id']: x for x in cached['records'] if x['folder_id'] == folder['id']}
        assert set(expected) == {x['file_id'] for x in listing['entries']}
        for item in listing['entries']:
            source = expected[item['file_id']]
            assert item['name'] == source['name'] and item['file']['size'] == source['source_bytes']
            assert sha(source['thumbnail']) == source['thumbnail_sha256']
            assert item['path_display'].rsplit('/', 1)[0] == folder['path_display']
            references.append({'file_id': item['file_id'], 'folder_id': folder['id'], 'group_ref': group_ref,
                               'name': item['name'], 'path_display': item['path_display'], 'bytes': item['file']['size'],
                               'image_url': 'https://www.dropbox.com/home' + quote(folder['path_display'], safe='/') + '?preview=' + quote(item['name']),
                               'folder_url': folder['open_in_dropbox_url'], 'checked_utc': live['checked_utc']})
    assert len(references) == len({x['file_id'] for x in references}) == 15
    parent = p['reviews'][cid]; target = parent['size_finish_variants'][vid]
    assert target['identity_confirmed'] and not target['proposals_approved'] and len(target['specification_proposals']) == 6
    assert any(x['variant_id'] == source_vid for x in parent['pending_size_finish_variants'])
    protected = {str(path): sha(path) for path in [cardpath, ROOT / cp['register_workbook'], ROOT / 'components/evidence/component_register.json',
        ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat(); approval_path = HERE / 'finish-reference-equivalence-approval.json'
    scope = 'Owner confirmed native G216/G217 and former Concave G052/G053 references as one MCP4 Verdigris finish record. All 15 file IDs and four containing folder IDs retained, including seven room/arrangement references. Existing six specification groups and platform claims keep their original applicability and approval states. Physical casts, moulds, stock, exact dimensions and prices are not merged or verified.'
    decision = {'schema_version': 1, 'decision_id': did, 'recorded_utc': now, 'component_id': cid, 'source_variant_id': source_vid,
        'canonical_size_finish_variant_id': vid, 'canonical_name': target['canonical_name'], 'owner_question_id': qid,
        'authoritative_user_evidence': messages[-1], 'preceding_review_card_evidence': messages[0], 'approval_record': rel(approval_path),
        'scope': scope, 'finish_reference_equivalence_confirmed': True, 'source_group_refs': [x[0] for x in groups],
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
    target['photo_coverage']['review_scope'] = '15 cached thumbnails across G216/G217 and G052/G053 inspected; complete live ID/name/size/path listings checked. No fresh original-byte hashes fetched.'
    target['photo_coverage'].update({'contextual_images_available': True, 'context_image_type': 'Room and series/arrangement presentations', 'contextual_file_ids': [x['file_id'] for x in references if x['group_ref'] in ['G217', 'G053']], 'installation_provenance': 'UNCONFIRMED', 'context_images_count_is_physical_stock': False})
    for item in references:
        prior = p['asset_assignment_overrides'].get(item['file_id'], {})
        p['asset_assignment_overrides'][item['file_id']] = prior | {'file_id': item['file_id'], 'folder_id': item['folder_id'], 'component_ids': [cid],
            'size_finish_variant_ids': [vid], 'canonical_size_finish_variant_id': vid, 'path_display': item['path_display'],
            'owner_finish_reference_equivalence_approval': rel(approval_path), 'review_record': target['review_record'],
            'assignment_status': 'OWNER_CONFIRMED_MCP4_VERDIGRIS_FINISH_REFERENCE;PHYSICAL_CAST_AND_SPECS_UNVERIFIED'}
    for group_ref, listing, folder in groups:
        override = p['catalogue_group_overrides'].setdefault(group_ref, {})
        override.update({'current_family': 'Moon Crater Phase', 'current_name': folder['name'], 'current_folder_id': folder['id'],
            'current_folder_path': folder['path_display'], 'file_count': len(listing['entries']), 'component_ids': [cid],
            'canonical_size_finish_variant_id': vid, 'owner_finish_reference_equivalence_approval': rel(approval_path),
            'assignment_status': 'Owner confirmed finish: Moon Crater Phase 4 — Verdigris (MCP4-VERDIGRIS-25). Four reference folders, one finish record; room/arrangement pictures available; physical casts and stock unverified.'})
    for consolidation in [p['canonical_component_consolidations']['BC-CONCAVE'], c['current_catalogue_overlays']['Concave Moon']]:
        consolidation.update({'native_vs_former_Concave_Verdigris_finish_equivalence_confirmed': True, 'Verdigris_finish_equivalence_approval': rel(approval_path)})
    p['finish_reference_equivalence_reviews'][qid].update({'state': 'OWNER_CONFIRMED_ONE_FINISH_REFERENCE_RECORD', 'approval_record': rel(approval_path)})
    p['current_finish_reference_equivalence_review'] = copy.deepcopy(p['finish_reference_equivalence_reviews'][qid])
    cp.update({'current_answer_recorded': True, 'current_finish_reference_equivalence_answer_recorded': True,
        'current_finish_reference_equivalence_approval': rel(approval_path), 'state': 'MCP4_VERDIGRIS_REFERENCE_GROUPS_CONSOLIDATED;VERDIGRIS_RUST_REVIEW_NEXT',
        'answer_state': scope, 'current_size_finish_variant_id': vid, 'last_finish_reference_equivalence_approval': rel(approval_path)})
    c['interactive_review_state'].update({'state': cp['state'], 'current_size_finish_variant_id': vid,
        'current_finish_reference_equivalence_answer_recorded': True, 'last_finish_reference_equivalence_approval': rel(approval_path)})
    c['next_work'][0] = 'Native and former Concave Verdigris references are one owner-confirmed MCP4 Verdigris finish. Review the remaining Verdigris/Rust reference group next.'
    summary = {'batch': 43, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'MAIN_OWNER_FINISH_REFERENCE_EQUIVALENCE',
        'component_id': cid, 'canonical_size_finish_variant_id': vid, 'new_finish_reference_equivalence_decisions': 1,
        'new_name_approvals': 0, 'new_full_specification_approvals': 0, 'reference_file_ids': 15, 'source_folder_ids': 4,
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
    assert all(u[k] == value for k, value in before['user'].items() if k not in ['updated_utc', 'finish_reference_equivalence_decisions'])
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
    print(json.dumps({'batch': 43, 'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'finish_records': 1, 'reference_files': 15, 'new_specification_approvals': 0}))


if __name__ == '__main__': main()
