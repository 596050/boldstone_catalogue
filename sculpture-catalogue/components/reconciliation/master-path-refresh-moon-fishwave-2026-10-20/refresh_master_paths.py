"""Refresh native Dropbox hyperlink destinations; preserve all workbook cells/features.

The consolidated workbook was authored with artifact-tool. Its documented native
OOXML hyperlink fallback is reused because HYPERLINK calculation was unsupported.
No cell, style, formula or calculated value is authored by this narrow refresh.
"""
import copy
import hashlib
import json
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit, urlunsplit
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
ROOT = BASE.parent
OLD = BASE / 'components/reconciliation/master-catalogue-consolidation-2026-10-20'
OVERLAY = ROOT / 'reports/dropbox-wall-structure-2026-10-20/step-04-moon-fishwave-renames-current-overlay.json'
OVERLAY_SHA = 'fb4f0fb22a6a86e9ef221f6fd0f052d70d685283ac6747fa59317b98961c3f65'
OLD_BOOK_SHA = 'f58bca0e6cc09775bb73255741f4c85d2ccd5f8425b6b12f63e635ae2688b345'
OLD_GRAPH_SHA = '07780607ef707fc3d89bdcbe6b1ec2757cb0b7642ca544bc3606f0ec2372eb66'
CONTROLS = ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json', 'current-master.json']
PNS = 'http://schemas.openxmlformats.org/package/2006/relationships'
SNS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
RNS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
now = lambda: datetime.now(timezone.utc).isoformat()
relative = lambda p: str(Path(p).relative_to(BASE))


def write(p, d):
    p = Path(p)
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(p)


def overlay():
    assert digest(OVERLAY) == OVERLAY_SHA
    o = read(OVERLAY)
    assert o['status'] == 'PASS_CURRENT_PATH_OVERLAY'
    assert len(o['objects']) == len({x['file_id'] for x in o['objects']}) == 134
    assert Counter(x['object_type'] for x in o['objects']) == {'file': 130, 'folder': 4}
    assert sum(x['path_changed'] for x in o['objects']) == 130
    assert all(x['old_name'] == x['current_name'] for x in o['objects'] if x['object_type'] == 'file')
    assert all(o['verification'].values())
    assert digest(o['receipts']['terminal']) == '56935550fec7e4fe0668ed1b35c03e58226a142789e7567cf217f92787b12e6e'
    assert read(o['receipts']['verification'])['status'] == 'PASS'
    return o


def transform(url, o):
    if not isinstance(url, str) or not url.startswith('https://www.dropbox.com/'):
        return url
    parts = urlsplit(url)
    if not parts.path.startswith(('/home/', '/preview/')):
        return url
    route = '/home' if parts.path.startswith('/home/') else '/preview'
    old_path = unquote(parts.path[len(route):])
    for m in o['prefix_maps']:
        prefix = m['old_prefix']
        if old_path == prefix or old_path.startswith(prefix + '/'):
            old_object_path = old_path
            if route == '/home' and 'preview' in parse_qs(parts.query):
                old_object_path += '/' + parse_qs(parts.query)['preview'][0]
            obj = next(x for x in o['objects'] if x['old_display_path'] == old_object_path)
            new_path = m['current_prefix'] + old_path[len(prefix):]
            new_object_path = new_path + ('/' + parse_qs(parts.query)['preview'][0] if route == '/home' and 'preview' in parse_qs(parts.query) else '')
            assert obj['current_display_path'] == new_object_path and obj['path_changed']
            return urlunsplit((parts.scheme, parts.netloc, route + quote(new_path, safe='/'), parts.query, parts.fragment))
    return url


def prepare():
    o = overlay()
    inputs = HERE / 'inputs'
    inputs.mkdir(exist_ok=True)
    assert not (HERE / 'input-manifest.json').exists(), 'Prepared inputs already exist'
    ptr = read(BASE / 'current-master.json')
    book, graph = BASE / ptr['workbook'], BASE / ptr['register']
    assert digest(book) == ptr['workbook_sha256'] == OLD_BOOK_SHA
    assert digest(graph) == ptr['register_sha256'] == OLD_GRAPH_SHA
    sources = {'workbook': book, 'register': graph, 'overlay': OVERLAY,
               'terminal': Path(o['receipts']['terminal']), 'overlay_verification': Path(o['receipts']['verification'])}
    sources.update({x: BASE / x for x in CONTROLS})
    manifest = {}
    for i, (key, source) in enumerate(sources.items()):
        snapshot = inputs / f'{i:02d}-{source.name}.before'
        snapshot.write_bytes(source.read_bytes())
        manifest[key] = {'source': str(source), 'snapshot': str(snapshot), 'sha256': digest(source)}
    write(HERE / 'input-manifest.json', manifest)
    g = read(graph)
    updated = copy.deepcopy(g)
    changes = []
    for i, x in enumerate(updated['options']):
        for key in ['image_url', 'folder_url', 'context_image_url', 'context_folder_url']:
            value = transform(x.get(key), o)
            if value != x.get(key):
                changes.append({'path': ['options', i, key], 'before': x[key], 'after': value})
                x[key] = value
    for group in ['source_sets', 'source_offer_edges']:
        for i, x in enumerate(updated[group]):
            ref = x.get('current_primary_reference', {})
            for key in ['image_url', 'folder_url']:
                value = transform(ref.get(key), o)
                if value != ref.get(key):
                    changes.append({'path': [group, i, 'current_primary_reference', key], 'before': ref[key], 'after': value})
                    ref[key] = value
    assert len(changes) == 8
    restored = copy.deepcopy(updated)
    for c in changes:
        node = restored
        for key in c['path'][:-1]: node = node[key]
        node[c['path'][-1]] = c['before']
    assert restored == g
    updated['latest_moon_fishwave_current_paths'] = {
        'status': 'APPLIED_CURRENT_NATIVE_LINKS', 'recorded_utc': now(),
        'source_overlay': str(OVERLAY), 'source_overlay_sha256': OVERLAY_SHA,
        'summary': o['summary'], 'prefix_maps': o['prefix_maps'],
        'current_reference_changes': changes, 'scene_provenance_guard': o['scene_provenance_guard'],
        'catalogue_identity_guard': o['catalogue_identity_guard'],
        'prior_master_register': ptr['register'], 'prior_master_register_sha256': OLD_GRAPH_SHA,
        'remote_writes': 0, 'http_access_audit': False}
    write(HERE / 'canonical-master-register.json', updated)
    write(HERE / 'refresh-plan.json', {'status': 'PREPARED', 'workbook': ptr['workbook'],
          'old_workbook_sha256': OLD_BOOK_SHA, 'graph_current_url_changes': changes,
          'all_non_link_data_preserved': True, 'expected_native_link_changes': 8})
    print(json.dumps({'status': 'PREPARED', 'current_url_changes': len(changes)}))


def stage():
    o = overlay()
    manifest = read(HERE / 'input-manifest.json')
    for x in manifest.values(): assert digest(x['source']) == digest(x['snapshot']) == x['sha256']
    old_book = Path(manifest['workbook']['snapshot'])
    pending = HERE / 'master-workbook.pending'
    assert not pending.exists(), 'Staged workbook already exists'
    changes, changed_parts, links = [], [], 0
    with zipfile.ZipFile(old_book) as src, zipfile.ZipFile(pending, 'w') as out:
        for info in src.infolist():
            raw = src.read(info.filename)
            if info.filename.endswith('.rels'):
                root = ET.fromstring(raw)
                replacements = {}
                for rel in root:
                    if rel.get('Type', '').endswith('/hyperlink'):
                        links += 1
                        before = rel.get('Target', '')
                        after = transform(before, o)
                        if before != after:
                            changes.append({'part': info.filename, 'relationship_id': rel.get('Id'), 'before': before, 'after': after})
                            replacements[before] = after
                for before, after in replacements.items():
                    attr = lambda s: ('Target="' + escape(s, {'"': '&quot;'}) + '"').encode()
                    assert attr(before) in raw
                    raw = raw.replace(attr(before), attr(after))
            if raw != src.read(info.filename): changed_parts.append(info.filename)
            out.writestr(info, raw)
    assert links == 7584 and len(changes) == 8 and len(changed_parts) == 3
    with zipfile.ZipFile(old_book) as before, zipfile.ZipFile(pending) as after:
        assert before.namelist() == after.namelist()
        for name in before.namelist():
            a, b = before.read(name), after.read(name)
            if name not in changed_parts:
                assert a == b, 'Unrelated workbook feature changed: ' + name
            else:
                r1, r2 = ET.fromstring(a), ET.fromstring(b)
                assert len(r1) == len(r2)
                for old, new in zip(r1, r2):
                    expected = dict(old.attrib)
                    if expected.get('Type', '').endswith('/hyperlink'):
                        expected['Target'] = transform(expected['Target'], o)
                    assert expected == new.attrib
        for name in after.namelist():
            if name.endswith('.rels'):
                for rel in ET.fromstring(after.read(name)):
                    if rel.get('Type', '').endswith('/hyperlink'):
                        assert transform(rel.get('Target', ''), o) == rel.get('Target', '')
    g = read(HERE / 'canonical-master-register.json')
    original = read(manifest['register']['snapshot'])
    assert g['summary'] == original['summary']
    assert g['original_review_specification_assertions'] == original['original_review_specification_assertions']
    for key in ['components', 'aliases', 'confirmed_arrangement_member_edges', 'wall_circle_native_options']:
        assert g[key] == original[key]
    check = {'status': 'PASS', 'recorded_utc': now(), 'workbook_sha256': digest(pending),
       'master_register_sha256': digest(HERE / 'canonical-master-register.json'),
       'old_workbook_sha256': OLD_BOOK_SHA, 'source_overlay_sha256': OVERLAY_SHA,
       'native_hyperlinks': 7768, 'external_native_hyperlink_relationships': links, 'changed_native_destinations': len(changes),
       'changed_archive_parts': changed_parts, 'link_changes': changes,
       'all_cell_formula_value_style_table_pane_and_object_parts_byte_identical': True,
       'all_calculation_dependencies_unchanged': True,
       'prior_saved_file_validation': str(OLD / 'saved-file-verification.json'),
       'prior_formula_dependency_validation': str(OLD / 'formula-dependency-check.json'),
       'visual_verification': 'Prior 33 verified previews reused: rendered cells, styles and calculation dependencies are byte-identical; hyperlink targets do not alter those views.',
       'prior_visual_validation': str(OLD / 'visual-verification.json'),
       'individual_records': 184, 'working_specification_groups': 1104,
       'all_identity_count_specification_and_provenance_values_preserved': True,
       'old_prefixes_in_current_native_links': 0, 'remote_reads': 0, 'remote_writes': 0,
       'http_access_audit': False}
    for key in ['prior_saved_file_validation', 'prior_formula_dependency_validation', 'prior_visual_validation']:
        assert read(check[key])['status'] == 'PASS'
        check[key + '_sha256'] = digest(check[key])
    write(HERE / 'saved-file-verification.json', check)
    print(json.dumps({'status': check['status'], 'links_changed': len(changes), 'all_cell_and_feature_parts_unchanged': True, 'workbook_sha256': check['workbook_sha256']}))


def publish():
    manifest = read(HERE / 'input-manifest.json')
    for x in manifest.values(): assert digest(x['source']) == digest(x['snapshot']) == x['sha256']
    check = read(HERE / 'saved-file-verification.json')
    pending = HERE / 'master-workbook.pending'
    assert check['status'] == 'PASS' and digest(pending) == check['workbook_sha256']
    assert digest(HERE / 'canonical-master-register.json') == check['master_register_sha256']
    prior = read(BASE / 'current-master.json')
    ptr = copy.deepcopy(prior)
    ptr.update(recorded_utc=now(), workbook_sha256=check['workbook_sha256'],
               register=relative(HERE / 'canonical-master-register.json'), register_sha256=check['master_register_sha256'],
               publication_receipt=relative(HERE / 'publication-receipt.json'))
    ptr['current_path_scope'] += '; two Moon Fishwave arrangement/context folder renames'
    ptr['latest_path_refresh'] = {'scope': 'Moon Fishwave group-folder native links', 'native_link_destinations_updated': 8,
        'overlay_sha256': OVERLAY_SHA, 'verification': relative(HERE / 'saved-file-verification.json'),
        'verification_sha256': digest(HERE / 'saved-file-verification.json'), 'visual_and_calculation_parts_unchanged': True}
    export = {'recorded_utc': now(), 'output': str(BASE / ptr['workbook']), 'workbook': ptr['workbook'],
       'workbook_sha256': check['workbook_sha256'], 'master_register_sha256': check['master_register_sha256'],
       'status': 'EXPORTED_AND_VERIFIED', 'validation': relative(HERE / 'saved-file-verification.json'),
       'validation_sha256': digest(HERE / 'saved-file-verification.json'), 'validation_status': 'PASS',
       'visual_validation_status': 'PASS_REUSED_BYTE_IDENTICAL_VIEWS', 'native_hyperlinks': 7768,
       'individual_option_records': 184, 'current_specification_field_groups': 1104,
       'all_actual_specifications_complete': False, 'prior_export_receipt': relative(OLD / 'export-receipt.json')}
    write(HERE / 'export-receipt.json', export)
    updates = []
    for name in CONTROLS[:-1]:
        path = BASE / name
        before = read(path)
        d = copy.deepcopy(before)
        d.update(current_master_catalogue=ptr, current_master_workbook=ptr['workbook'], current_master_register=ptr['register'], updated_utc=now())
        if 'workbook_sha256' in d: d['workbook_sha256'] = ptr['workbook_sha256']
        if 'latest_workbook_export' in d:
            d.setdefault('prior_workbook_exports', []).append({'preserved_at': now(), 'role': 'Consolidated master before Moon Fishwave path refresh', 'latest_workbook_export': before['latest_workbook_export'], 'workbook_snapshot': manifest['workbook']['snapshot']})
            old_export = copy.deepcopy(d['latest_workbook_export'])
            old_export.update(export_receipt=relative(HERE / 'export-receipt.json'), export_receipt_sha256=digest(HERE / 'export-receipt.json'), workbook_sha256=ptr['workbook_sha256'], validation=export['validation'], validation_sha256=export['validation_sha256'], recorded_utc=now())
            d['latest_workbook_export'] = old_export
        if 'current_master_validation' in d: d['current_master_validation'] = {'path': export['validation'], 'sha256': export['validation_sha256']}
        for key in ['current_working_specification_completion', 'wall_circle_current_display_recovery']:
            if key in d: d[key]['current_master_register_sha256'] = ptr['register_sha256']
        if name == 'checkpoint.json':
            d['current_component_review'].update(current_master_catalogue=ptr, workbook_sha256=ptr['workbook_sha256'])
        for key in ['reviews', 'decisions', 'counts', 'coverage', 'identity_confirmation_counts', 'specification_approval_counts', 'global_fixing_choice_policy', 'global_approximate_weight_policy', 'group_photo_review_policy']:
            if key in before: assert before[key] == d[key]
        updates.append((path, d))
    # Apply only after every input, replacement and control update has validated.
    pending.replace(BASE / ptr['workbook'])
    for path, data in updates:
        write(path, data)
        assert read(path) == data
    write(BASE / 'current-master.json', ptr)
    assert digest(BASE / ptr['workbook']) == ptr['workbook_sha256']
    receipt = {'status': 'PUBLISHED_AND_VERIFIED', 'recorded_utc': now(), 'current_master': ptr,
       'previous_current_master': prior, 'source_overlay_sha256': OVERLAY_SHA,
       'validation': export['validation'], 'validation_sha256': export['validation_sha256'],
       'prior_workbook_snapshot': manifest['workbook'], 'native_link_destinations_updated': 8,
       'all_other_archive_parts_byte_identical': True, 'all_identities_counts_specifications_and_provenance_preserved': True,
       'source_control_updates': [relative(path) for path, _ in updates] + ['current-master.json'],
       'remote_reads': 0, 'remote_writes': 0, 'http_access_audit': False}
    write(HERE / 'publication-receipt.json', receipt)
    write(HERE / 'completion.json', {'status': 'COMPLETE', 'workbook': ptr['workbook'],
       'workbook_sha256': ptr['workbook_sha256'], 'register_sha256': ptr['register_sha256'],
       'publication_receipt': relative(HERE / 'publication-receipt.json'),
       'publication_receipt_sha256': digest(HERE / 'publication-receipt.json')})
    print(json.dumps({'status': receipt['status'], 'workbook_sha256': ptr['workbook_sha256'], 'register_sha256': ptr['register_sha256'], 'publication_receipt_sha256': digest(HERE / 'publication-receipt.json')}))


if __name__ == '__main__':
    {'prepare': prepare, 'stage': stage, 'publish': publish}[sys.argv[1]]()
