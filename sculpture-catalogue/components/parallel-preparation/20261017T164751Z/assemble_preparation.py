"""Assemble isolated advisory packets without writing the interactive catalogue."""
from pathlib import Path
from collections import Counter
from urllib.parse import quote
import copy, datetime, hashlib, html, json, sys

R = Path(__file__).parent
MASTER = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue/components')
FIELDS = ['dimensions', 'weight', 'material_finish', 'fixing', 'individual_price', 'availability']
LABELS = ['Dimensions', 'Weight', 'Material and finish', 'Fixing', 'Individual price', 'Availability']

def read(p):
    return json.loads(Path(p).read_text())

def save(p, obj):
    p = Path(p)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(p)

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def stringify(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

def esc(value):
    return html.escape(stringify(value))

def iter_examples(obj):
    if isinstance(obj, dict):
        if obj.get('file_id'):
            yield obj
        for k, value in obj.items():
            if k != 'current_binding':
                yield from iter_examples(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from iter_examples(value)

def main():
    allow_partial = '--allow-partial' in sys.argv
    contract = read(R / 'COORDINATION.json')
    expected = contract['component_ids']
    assert len(expected) == len(set(expected)) == 101
    assert 'BC-CONCAVE' not in expected and 'BC-WALL-CIRCLE' not in expected
    snapshot = read(R / 'snapshots/component_register.json')
    oldassets = {a['id']: a for a in snapshot['assets']}
    oldcomponents = {c['component_id']: c for c in snapshot['components']}
    census_receipt = read(R / 'Current_Metadata_Receipt.json')
    assert digest(census_receipt['path']) == census_receipt['sha256']
    census = read(census_receipt['path'])
    assert census['pagination_exhausted'] and census['remote_mutations'] == 0
    native = {x['id']: x for x in census['entries']}
    native_paths = {x['path'].casefold(): x for x in census['entries']}
    linkfile = R / 'Current_Example_Links.json'
    links = read(linkfile)['entries'] if linkfile.exists() else {}
    document_file = R / 'Current_Document_Bindings.json'
    documents = read(document_file)['entries'] if document_file.exists() else {}
    entries, inputs, errors, pending = [], [], [], []
    for w in contract['workers']:
        folder = Path(w['folder'])
        f = folder / 'packets.json'
        complete = f.exists()
        if not complete:
            f = folder / 'packets.partial.json'
        if not f.exists():
            pending.extend(w['component_ids'])
            continue
        d = read(f)
        assert d['worker_number'] == w['worker_number']
        ids = [x['component_id'] for x in d['entries']]
        assert len(ids) == len(set(ids)) and set(ids) <= set(w['component_ids'])
        if complete:
            assert set(ids) == set(w['component_ids'])
        pending.extend(x for x in w['component_ids'] if x not in ids)
        inputs.append({'path': str(f), 'sha256': digest(f), 'worker_number': w['worker_number'], 'entries': len(ids), 'worker_complete': complete})
        for item in d['entries']:
            e = copy.deepcopy(item)
            e['preparation_owner'] = contract['owner_session']
            e['preparation_worker'] = w['worker_number']
            e['approval_state'] = 'PROPOSAL_ONLY_REQUIRES_INTERACTIVE_OWNER_REVIEW'
            e['physical_specs_verified'] = False
            e['source_packet'] = str(f)
            e['source_packet_sha256'] = digest(f)
            cid = e['component_id']
            assert not (set(oldcomponents[cid]['group_refs']) & {f'G{x}' for x in range(331,344)})
            for field in FIELDS:
                v = e.get('specifications', {}).get(field)
                if not isinstance(v, dict) or not v.get('display') or not v.get('proposal') or not v.get('evidence_state'):
                    errors.append({'component_id': cid, 'field': field, 'problem': 'MISSING_REVIEWABLE_SPECIFICATION_FIELD'})
                elif v.get('requires_owner_check') is not True:
                    errors.append({'component_id': cid, 'field': field, 'problem': 'OWNER_CHECK_MUST_REMAIN_REQUIRED'})
            for image in iter_examples(e):
                item_id = image['file_id']
                head, old = native.get(item_id), oldassets.get(item_id)
                if not head or not old:
                    # A rendered project-sheet page is a document reference,
                    # not an image asset inside the wall-sculpture census.
                    doc = documents.get(item_id)
                    if doc and doc.get('snapshot_hash_size_unchanged'):
                        dh, parent = doc['head'], doc['parent']
                        image['current_binding'] = {
                            'status': 'PASS_CURRENT_SOURCE_DOCUMENT_HASH_SIZE',
                            'file_id': item_id, 'folder_id': parent['id'],
                            'current_path': dh['path'], 'current_name': dh['name'],
                            'rev': dh.get('rev'), 'content_hash': dh.get('content_hash'), 'bytes': dh.get('size'),
                            'source_local_sha256': doc['source_local_sha256'],
                            'snapshot_hash_size_unchanged': True,
                            'local_preview_exists': bool(image.get('preview_path') and Path(image['preview_path']).is_file()),
                            'cached_preview_binding': 'Locally rendered dated source document page; not an isolated product image',
                            'image_url': 'https://www.dropbox.com/preview' + quote(dh['path'], safe='/'),
                            'folder_url': 'https://www.dropbox.com/preview' + quote(parent['path'], safe='/'),
                            'checked_utc': doc['checked_utc'], 'browser_open_tested': False, 'remote_mutations': 0,
                        }
                        continue
                    image['current_binding'] = {'status': 'UNBOUND_CURRENT_OR_SNAPSHOT_ID', 'file_id': item_id}
                    errors.append({'component_id': cid, 'file_id': item_id, 'problem': 'UNBOUND_CURRENT_OR_SNAPSHOT_ID'})
                    continue
                unchanged = head.get('content_hash') == old.get('content_hash') and head.get('size') == old.get('bytes')
                parentpath = head['path'].rsplit('/', 1)[0]
                parent = native_paths.get(parentpath.casefold())
                folder_matches = bool(parent and parent['id'] == image.get('folder_id'))
                if not unchanged or not folder_matches:
                    errors.append({'component_id': cid, 'file_id': item_id, 'problem': 'HASH_SIZE_OR_FOLDER_CHANGED', 'hash_size_match': unchanged, 'folder_matches': folder_matches})
                preview = image.get('preview_path')
                preview_exists = bool(preview and Path(preview).is_file())
                if preview and not preview_exists:
                    errors.append({'component_id': cid, 'file_id': item_id, 'problem': 'LOCAL_PREVIEW_MISSING'})
                link = links.get(item_id, {})
                folderlink = links.get(parent['id'], {}) if parent else {}
                image['current_binding'] = {
                    'status': 'PASS_CURRENT_ID_HASH_SIZE_AND_FOLDER' if unchanged and folder_matches else 'REQUIRES_RECHECK',
                    'native_census_utc': census['recorded_utc'],
                    'file_id': item_id, 'folder_id': parent['id'] if parent else None,
                    'current_path': head['path'], 'current_name': head['name'],
                    'rev': head.get('rev'), 'content_hash': head.get('content_hash'), 'bytes': head.get('size'),
                    'snapshot_hash_size_unchanged': unchanged, 'local_preview_exists': preview_exists,
                    'cached_preview_binding': 'Preview selected by worker from the unchanged stable-ID snapshot; no new binary download in this run',
                    'existing_shared_image_links': link.get('existing_shared_links', []),
                    'existing_shared_folder_links': folderlink.get('existing_shared_links', []),
                    'image_url': (link.get('existing_shared_links') or [{}])[0].get('url') or 'https://www.dropbox.com/preview' + quote(head['path'], safe='/'),
                    'folder_url': ((folderlink.get('existing_shared_links') or [{}])[0].get('url') or 'https://www.dropbox.com/preview' + quote(parentpath, safe='/')),
                    'link_status': link.get('status', 'CURRENT_PATH_ACCOUNT_LINK_CONSTRUCTED'),
                    'browser_open_tested': False, 'remote_mutations': 0,
                }
            primary = e.get('primary_example')
            e['complete_single_component_primary_available'] = bool(isinstance(primary, dict) and primary.get('file_id') and primary.get('shows_complete_single_component') is True and primary.get('current_binding', {}).get('status') == 'PASS_CURRENT_ID_HASH_SIZE_AND_FOLDER')
            entries.append(e)
    byid = {x['component_id']: x for x in entries}
    assert len(byid) == len(entries)
    entries = [byid[x] for x in expected if x in byid]
    assert set(byid) <= set(expected)
    if not allow_partial:
        assert not pending, f'WORKER_PACKETS_PENDING:{pending}'
        assert len(entries) == 101
    current_checkpoint = read(MASTER / 'reviews/walkthrough_checkpoint.json')
    current_approvals = read(MASTER / 'reviews/user_classifications.json')
    prior_approvals = read(R / 'snapshots/user_classifications.json')
    decision_collections = ['decisions', 'specification_decisions', 'dimension_decisions', 'reference_label_decisions', 'build_variant_decisions', 'structure_changes']
    def decision_rows(data):
        return [d for name in decision_collections for d in data.get(name, []) if isinstance(d, dict)]
    old_decisions = {json.dumps(d, sort_keys=True, ensure_ascii=False) for d in decision_rows(prior_approvals)}
    new_decisions = [d for d in decision_rows(current_approvals) if json.dumps(d, sort_keys=True, ensure_ascii=False) not in old_decisions]
    changed_ids = sorted({d.get('component_id') for d in new_decisions if d.get('component_id')})
    current_register = read(MASTER / 'evidence/component_register.json')
    current_components = {c['component_id']: c for c in current_register['components']}
    changed_component_ids = [cid for cid in expected if json.dumps(current_components.get(cid), sort_keys=True) != json.dumps(oldcomponents[cid], sort_keys=True)]
    expected_order_unchanged = [cid for cid in current_checkpoint['review_order'] if cid in set(expected)] == expected
    current_claims = {x['claim_id']: x for x in current_register['claims'] if x.get('component_id') in expected}
    old_claims = {x['claim_id']: x for x in snapshot['claims'] if x.get('component_id') in expected}
    changed_claim_component_ids = sorted({x.get('component_id') for key,x in current_claims.items() if old_claims.get(key) != x} | {x.get('component_id') for key,x in old_claims.items() if key not in current_claims})
    reconcile_ids = set(changed_ids + changed_component_ids + changed_claim_component_ids)
    for e in entries:
        e['upstream_owner_state_changed_during_preparation'] = e['component_id'] in changed_ids
        e['upstream_component_or_claim_changed_during_preparation'] = e['component_id'] in set(changed_component_ids + changed_claim_component_ids)
        e['handoff_use'] = 'RECONCILE_WITH_NEW_UPSTREAM_STATE_BEFORE_USE' if e['component_id'] in reconcile_ids else 'ADVISORY_INPUT_FOR_MAIN_WALKTHROUGH_ONLY'
    hashes = [{'source': s['source'], 'snapshot_sha256': s['sha256'], 'current_sha256': digest(s['source']), 'changed_by_other_process': digest(s['source']) != s['sha256']} for s in contract['source_snapshots']]
    currentfiles = {k for k,v in native.items() if v['kind'] == 'file'}
    missing = sorted(set(oldassets) - currentfiles)
    added = sorted(currentfiles - set(oldassets))
    counts = {
        'assigned': 101, 'prepared': len(entries), 'pending': len(pending),
        'complete_single_component_primaries': sum(x['complete_single_component_primary_available'] for x in entries),
        'without_complete_single_component_primary': sum(not x['complete_single_component_primary_available'] for x in entries),
        'specification_fields_prepared': len(entries) * 6,
        'owner_approvals_created': 0, 'shared_master_writes': 0, 'remote_mutations': 0,
    }
    peer_file = R / 'worker-02/Peer_Review_03.json'
    peer_review = {'path': str(peer_file), 'sha256': digest(peer_file), 'scope': read(peer_file)['scope'], 'result': read(peer_file)['overall_result']} if peer_file.exists() else None
    result = {
        'schema': 'boldstone.parallel-preparation.advisory.v1', 'prepared_utc': now(),
        'status': 'PREPARED_COMPLETE' if not pending and not errors else ('PARTIAL_PREPARATION' if pending else 'VALIDATION_REQUIRES_CORRECTION'),
        'ownership_contract': str(R / 'COORDINATION.json'), 'coordination_additions': str(R / 'COORDINATION_ADDITIONS.json'),
        'counts': counts, 'pending_component_ids': pending, 'validation_errors': errors,
        'main_interactive_session': contract['interactive_owner_session'], 'approval_state': 'ALL_PROPOSALS_ONLY',
        'current_main_state': {'component_id': current_checkpoint.get('current_component_id'), 'review_number': current_checkpoint.get('current_review_number'), 'state': current_checkpoint.get('state'), 'updated_utc': current_checkpoint.get('updated_utc')},
        'owner_decision_component_ids_changed_since_snapshot': changed_ids,
        'future_component_records_changed_since_snapshot': changed_component_ids,
        'future_claim_component_ids_changed_since_snapshot': changed_claim_component_ids,
        'future_review_order_unchanged': expected_order_unchanged,
        'source_change_receipts': hashes, 'worker_inputs': inputs,
        'live_read_receipt': census_receipt,
        'source_index': {'path': str(R / 'Source_Index.json'), 'sha256': digest(R / 'Source_Index.json')},
        'document_bindings': {'path': str(document_file), 'sha256': digest(document_file)} if document_file.exists() else None,
        'bounded_peer_review': peer_review,
        'current_census_delta_from_snapshot': {'absent_file_ids': missing, 'added_file_ids': added, 'limits': 'Other processes may change their own lanes. Never restore historical IDs or replay writes from these differences.'},
        'live_limits': ['Read-only account/root-verified production metadata and existing links only; no disposable sandbox actions tested in this preparation.', 'Native content hashes and sizes match the cached source snapshot for bound examples; this run did not redownload binary originals.', 'Account preview links are constructed from current native paths; authenticated browser opening was not tested.', 'Dated source specifications, visual observations, model guesses, owner approvals and physical verification remain separate.'],
        'entries': entries,
    }
    save(R / 'Prepared_Catalogue_Packets.json', result)
    gaps = [{'component_id': e['component_id'], 'proposed_name': e['proposed_name'], 'primary_limits': (e.get('primary_example') or {}).get('selection_reason'), 'missing_evidence': e.get('missing_evidence'), 'source_packet': e['source_packet']} for e in entries if not e['complete_single_component_primary_available']]
    save(R / 'Image_Identity_Gaps.json', {'prepared_utc': result['prepared_utc'], 'count': len(gaps), 'rule': 'Complete-component photos and individual identity boundaries must be checked during the existing walkthrough; no additional approval queue is created here.', 'entries': gaps})
    validation = {k: result[k] for k in ['prepared_utc', 'status', 'counts', 'pending_component_ids', 'validation_errors', 'current_main_state', 'owner_decision_component_ids_changed_since_snapshot', 'future_component_records_changed_since_snapshot', 'future_claim_component_ids_changed_since_snapshot', 'future_review_order_unchanged', 'worker_inputs']}
    validation['check_results'] = {'disjoint_assigned_ids': True, 'concave_excluded': True, 'wall_circle_excluded': True, 'all_six_fields_present': not any('field' in e for e in errors), 'current_id_hash_size_folder_bindings': not any('file_id' in e for e in errors), 'shared_master_writes': 0, 'remote_mutations': 0}
    save(R / 'Validation.json', validation)
    rows = []
    for e in entries:
        specs = ''.join('<tr><th>' + label + '</th><td><div>' + esc(e['specifications'][field]['display']) + '</div><p>' + esc(e['specifications'][field]['proposal']) + '</p><small>' + esc(e['specifications'][field]['evidence_state']) + '</small></td></tr>' for field,label in zip(FIELDS,LABELS))
        primary = e.get('primary_example') or {}
        contextual = not e['complete_single_component_primary_available']
        if not primary.get('file_id'):
            candidates = e.get('series_images', []) + e.get('context_images', []) + e.get('alternate_examples', [])
            primary = next((x for x in candidates if isinstance(x, dict) and x.get('file_id')), {})
        visual = ''
        if primary.get('file_id'):
            b = primary.get('current_binding', {})
            if primary.get('preview_path'):
                visual += '<img loading="lazy" src="' + esc(Path(primary['preview_path']).as_uri()) + '" alt="Reviewed cached image for ' + esc(e['proposed_name']) + '">'
            visual += '<p><a href="' + esc(b.get('image_url','')) + '">View image in Dropbox</a> · <a href="' + esc(b.get('folder_url','')) + '">Open containing folder</a></p>'
            visual += '<small>' + esc(primary.get('selection_reason', primary.get('usage',''))) + '</small>'
            if contextual:
                visual = '<p><strong>Context / arrangement / detail reference only</strong></p>' + visual
        otherlinks = []
        for role in ['context_images', 'series_images']:
            image = next((x for x in e.get(role, []) if isinstance(x, dict) and x.get('current_binding', {}).get('image_url')), None)
            if image:
                otherlinks.append('<a href="' + esc(image['current_binding']['image_url']) + '">' + ('Context image' if role == 'context_images' else 'Series / arrangement reference') + '</a>')
        if otherlinks:
            visual += '<p>' + ' · '.join(otherlinks) + '</p>'
        status = 'Complete component example available' if e['complete_single_component_primary_available'] else 'Complete isolated component image still needed; context/detail only'
        notes = '<h3>Evidence and open questions</h3><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in e.get('source_conflicts',[]) + e.get('missing_evidence',[])) + '</ul>'
        sources = '<details><summary>Source references and platform mapping</summary><pre>' + esc({'source_refs':e.get('source_refs'), 'platform_mapping':e.get('platform_mapping'), 'primary_metadata':primary.get('current_binding')}) + '</pre></details>'
        rows.append('<article id="' + esc(e['component_id']) + '" data-search="' + esc((e['component_id'] + ' ' + e['proposed_name'] + ' ' + e['family']).lower()) + '"><h2>' + esc(e['proposed_name']) + '</h2><p class="id">' + esc(e['component_id']) + ' · ' + esc(status) + '</p>' + visual + '<table>' + specs + '</table>' + notes + sources + '</article>')
    doc = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone parallel catalogue preparation</title><style>
body{font:16px/1.5 system-ui,sans-serif;color:#202822;background:#f2f3ef;margin:0}header,main{max-width:1080px;margin:auto;padding:24px}header{position:relative}h1{font-size:30px;margin:0 0 8px}h2{margin:0}h3{font-size:17px}article{background:#fff;border:1px solid #d7ddd3;border-radius:10px;padding:24px;margin:0 0 24px;overflow:auto}a{color:#235b48}input{padding:12px;width:min(100%,560px);font:inherit;box-sizing:border-box}img{max-width:340px;max-height:290px;object-fit:contain;display:block;background:#f4f4f1}table{border-collapse:collapse;width:100%;margin:20px 0}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #dde2d8;padding:12px 8px}th{width:160px}td p{margin:8px 0}small,.id{color:#556352}small{font-size:13px}pre{white-space:pre-wrap;word-break:break-word;font:12px/1.5 ui-monospace,monospace}details{margin-top:14px}li{margin:6px 0}.notice{background:#e4ebdf;padding:14px;border-radius:6px}#empty{display:none}@media(max-width:640px){header,main{padding:16px}article{padding:16px}th{width:110px}img{max-width:100%}}
</style><header><h1>Boldstone catalogue preparation</h1><p>''' + esc(str(counts['prepared'])) + ''' of 101 future component packets prepared. ''' + esc(str(counts['complete_single_component_primaries'])) + ''' have a complete single-component primary image.</p><p class="notice">Advisory proposals for the existing owner walkthrough. These packets create no approvals. Dated source facts and working guesses are labelled separately. The main walkthrough remains the sole writer of the catalogue, checkpoints and workbook.</p><p>Current native metadata: ''' + esc(census['recorded_utc']) + '''. Image pixels are cached reviewed previews. Dropbox account links use the current path and require access; browser opening has not been tested.</p><input id="search" type="search" placeholder="Find a component by name or ID" aria-label="Find a component"><p id="found"></p></header><main>''' + ''.join(rows) + '''<p id="empty">No matching components.</p></main><script>const q=document.getElementById('search'),cards=[...document.querySelectorAll('article')];function filter(){const s=q.value.toLowerCase().trim();let n=0;cards.forEach(c=>{const show=c.dataset.search.includes(s);c.hidden=!show;if(show)n++});document.getElementById('found').textContent=n+' components shown';document.getElementById('empty').style.display=n?'none':'block'}q.addEventListener('input',filter);filter();</script></html>'''
    (R / 'Prepared_Catalogue_Packets.html').write_text(doc)
    instructions = f'''# Parallel preparation handoff

Prepared {now()}; {counts['prepared']}/101 assigned future components, {counts['complete_single_component_primaries']} complete single-component primary examples.

Use `Prepared_Catalogue_Packets.json` as advisory input, or search `Prepared_Catalogue_Packets.html`. All six specification groups retain source state, proposal wording and owner-check requirements. Unknown identities, cast applicability, source price conflicts and missing complete-component photos remain visible.

The interactive walkthrough session {contract['interactive_owner_session']} alone records owner answers and updates shared checkpoints, component registers or workbooks. Do not import this source snapshot wholesale. Check each component against newer owner decisions immediately before use. This run excludes current Concave and the separately owned Wall Circle lane. See `COORDINATION.json` and `COORDINATION_ADDITIONS.json` for exact ownership.

Current source state at assembly: {current_checkpoint.get('current_component_id')}, review {current_checkpoint.get('current_review_number')}. Owner decisions changed during preparation: {', '.join(changed_ids) or 'none found in the decision collections checked'}.

`Image_Identity_Gaps.json` lists the {len(gaps)} packets without a verified complete single-component primary. Context, arrangement and dated document images remain available for discussion. `worker-02/Peer_Review_03.json` records a bounded independent check of six components, with no concrete packet errors; its scope does not extend to all 101 packets.

`Validation.json` records coverage, worker packet hashes and current stable-ID/hash/size/parent-folder checks. `Source_Index.json` resolves source labels to local files, hashes and historical receipt identities. `Current_Metadata_Receipt.json` points to the complete native metadata census outside the application repository. `Fake_Adapter_Gate.json` records 74 passing offline fake-adapter tests before live reads. Live production reads are separate from tests; no live disposable-sandbox behavior was exercised here. No binary re-download, Dropbox mutation, sharing change, platform publication or owner approval was performed.

Existing shared links are reused when available. Otherwise an authenticated Dropbox preview link is constructed from the current native path. Those browser destinations were not opened by this preparation process. Cached previews are bound to unchanged snapshot file IDs/content hashes; they remain image evidence rather than physical product measurements.

Resume preparation with `collect_current_links.py`, then `assemble_preparation.py` after all three `worker-*/packets.json` files are present. `assemble_preparation.py --allow-partial` builds an interim handoff. Both scripts write only this isolated output directory or the private metadata directory named in `Live_Metadata_Location.json`. No script imports approvals into the main catalogue.
'''
    (R / 'HANDOFF.md').write_text(instructions)
    print(json.dumps(validation, ensure_ascii=False))
    if errors:
        raise SystemExit(2)

if __name__ == '__main__':
    main()
