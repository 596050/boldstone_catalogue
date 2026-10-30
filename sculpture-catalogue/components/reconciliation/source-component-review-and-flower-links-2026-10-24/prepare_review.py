"""Prepare an expanded source index and one same-ID capitalization correction."""
import copy
import hashlib
import html
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
OUT = B / 'outputs/source-component-review-and-flower-links-2026-10-24'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda x: html.escape(str(x), quote=True)
def write(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')

assert not (H / 'publication-receipt.json').exists()
assert sha(B / 'current-master.json') == '35fb7101714072786442d2cc04823ebcd6c7399eceea44fa8d98759199e2af49'
old = read(B / 'current-master.json')
g = read(B / old['register'])
options = {x['product_id']: x for x in g['options']}
old_assets = read(B / old['current_asset_reference_map']['path'])
old_native = read(B / old['current_native_reference_map']['path'])
assets, native = copy.deepcopy(old_assets), copy.deepcopy(old_native)
root_review = ROOT / 'reports/acanthus-source-component-review-20261024-root'
correction = read(root_review / 'prepared-flower-case-link-refresh.json')
observed = read(root_review / 'native-readback.json')
observations = {x['id']: x for x in observed['records']}
fid, parent = correction['file_id'], correction['folder_id']
assert fid == 'id:cnqzTNngPVsAAAAAAAyh5Q' and parent == 'id:cnqzTNngPVsAAAAAAAyh5A'
file_meta, parent_meta = observations[fid], observations[parent]
assert file_meta['path_display'].rsplit('/', 1)[0] == parent_meta['path_display']
assert file_meta['size'] == assets[fid]['bytes'] and assets[fid]['folder_id'] == parent
a = assets[fid]
a.update(path=correction['fresh_reference']['path'], display_path=file_meta['path_display'],
    folder_path='ns:202238505/' + parent_meta['path_display'],
    image_url=correction['fresh_reference']['image_url'], folder_url=correction['fresh_reference']['folder_url'],
    latest_scoped_navigation_observation={'source': str(root_review / 'native-readback.json'),
        'sha256': sha(root_review / 'native-readback.json'), 'observed_utc': observed['observed_utc'],
        'file_id': fid, 'parent_id': parent, 'rev': file_meta['rev'], 'server_modified': file_meta['server_modified'],
        'original_content_hash_reverified': False, 'scope': 'Exact same-ID file and actual parent; capitalization only.'})
native['current_objects'][fid].update(path=correction['fresh_reference']['path'], display_path=file_meta['path_display'])
assert native['current_objects'][fid]['parent_id'] == parent
assert native['current_objects'][parent]['path'] == 'ns:202238505/' + parent_meta['path_display']
native['verified_path_change_history'].append({'status': 'SAME_ID_CAPITALIZATION_ONLY_NO_MOVE',
    'source': str(root_review / 'native-readback.json'), 'source_sha256': sha(root_review / 'native-readback.json'),
    'file_id': fid, 'parent_id': parent, 'old_path': old_assets[fid]['path'], 'current_path': a['path'],
    'actual_parent_changes': 0, 'native_writes': 0})
assert set(assets) == set(old_assets) and set(native['current_objects']) == set(old_native['current_objects'])
assert [k for k in assets if assets[k] != old_assets[k]] == [fid]
assert [k for k in native['current_objects'] if native['current_objects'][k] != old_native['current_objects'][k]] == [fid]
write(H / 'current-assets.json', assets)
write(H / 'current-native-reference-map.json', native)
write(H / 'flower-case-navigation.json', correction)
asset_ref = {'path': str((H / 'current-assets.json').relative_to(B)), 'sha256': sha(H / 'current-assets.json'),
    'scope': 'Cumulative asset navigation. One Flower display-image path capitalized to match its verified existing parent; selected photographs and roles unchanged.',
    'preceding_reference': old['current_asset_reference_map']}
native_ref = {'path': str((H / 'current-native-reference-map.json').relative_to(B)), 'sha256': sha(H / 'current-native-reference-map.json'),
    'scope': 'Cumulative native navigation; one existing Flower image path capitalization corrected. Prior Echo and other native observations retained.',
    'cumulative_object_count': len(native['current_objects']), 'latest_scope': 'Acanthus Flower White In Situ',
    'same_id_file_paths_refreshed_in_latest_scope': 1, 'actual_file_parent_changes_in_latest_scope': 0,
    'actual_folder_parent_changes_in_latest_scope': 0, 'new_native_objects': 0, 'native_writes_by_master_import': 0,
    'fresh_original_content_hash_verifications_in_latest_scope': 0, 'preceding_reference': old['current_native_reference_map']}

prior = read(B / old['current_source_photo_review_index']['path'])
packets = copy.deepcopy(prior['review_packets'])
new_specs = [
 ('Echo Pattern White and Verdigris source scope', B / 'components/parallel-reviews/echo-pattern-two-source-review-20261024-B',
  ['O057', 'O072'], ['BSI-BF85B0E4D43E', 'BSI-F8398FA248EE', 'BSI-0BE032939501', 'BSI-EF421C1D2C92'],
  '68f25c4f8d1a78a423d06c025f3ec0fad25d1f814440e2ea0e2db6f27ab3effb',
  'White group reference retained; three of twenty-one Verdigris frames show component Two. Source sale-unit and per-member prices/weights remain qualified.'),
 ('Four Acanthus individual source reviews', root_review,
  ['O069', 'O071', 'O076', 'O077'], ['BSI-A9FE7D79863A', 'BSI-2CA935C1A57A', 'BSI-9C7406B46836', 'BSI-C02D6DF365D3'], None,
  'Fifteen photograph correspondences checked. Shared rear imagery, White display placements and Flower garden context retain their limits. Seven files and six parents checked by stable ID.'),
 ('Moonphase White members and Silver orientation', B / 'components/parallel-reviews/moonphase-five-source-review-01a16dbc-20261024',
  ['O010', 'O065', 'O070', 'O074', 'O075'], ['BSI-8C0D9152DF73', 'BSI-41E5370B1314', 'BSI-93FC0B4F78DA', 'BSI-DF431D2D9F15'],
  'adc9986e40eab22a85103f2fa7503586a1e243764f8d7a4144f70a7d19ade0ce',
  'Four existing options retained. Group sale quantity and exact variant allocation remain unresolved; Silver cached-original evidence is distinct from saved White renditions.'),
 ('Icarus, Strata, Barbados Wave and Brancusi Totem', B / 'components/parallel-reviews/icarus-strata-barbados-brancusi-source-review-20261024-B',
  ['O061', 'O062', 'O078', 'O080'], ['BSI-PLACEHOLDER'],
  'b62f9a4449a026b7b6d35d65553a2c39887d29631aab7a0a966672c2d7864472',
  'Four individual source reviews. Barbados workshop frame has two current file candidates. Icarus lead-time/material differences and source dimensions/weights remain qualified.')]
for title, folder, refs, ids, expected_seal, scope in new_specs:
    if ids == ['BSI-PLACEHOLDER']:
        ids = [x['product_id'] for x in read(folder / 'review.json')['individual_options']]
    if expected_seal:
        assert sha(folder / 'sealed-handoff.json') == expected_seal
    packets.append({'title': title, 'review': str(folder / 'index.html'), 'review_json': str(folder / 'review.json'),
        'review_sha256': sha(folder / 'review.json'), 'seal': str(folder / 'sealed-handoff.json'),
        'seal_sha256': sha(folder / 'sealed-handoff.json'), 'verification': str(folder / 'verification.json'),
        'verification_sha256': sha(folder / 'verification.json'), 'offer_refs': refs, 'option_ids': ids, 'scope': scope})
provider_files = {}
for packet in packets:
    assert sha(packet['seal']) == packet['seal_sha256']
    assert sha(packet['review_json']) == packet['review_sha256']
    assert sha(packet['verification']) == packet['verification_sha256']
    seal = read(packet['seal'])
    files = seal['files']
    members = files.items() if isinstance(files, dict) else [(x['path'], x['sha256']) for x in files]
    for path, expected in members:
        path = Path(path)
        path = path if path.is_absolute() else Path(packet['seal']).parent / path
        expected = expected if isinstance(expected, str) else expected['sha256']
        assert sha(path) == expected, path
        provider_files[str(path)] = expected
    provider_files[packet['seal']] = packet['seal_sha256']
    v = read(packet['verification'])
    assert v['status'] == 'PASS'
    if 'checks_total' in v:
        assert v['checks_passed'] == v['checks_total']
    if 'total' in v:
        assert v['passed'] == v['total']
    r = read(packet['review_json'])
    represented = r.get('components', r.get('individual_options', r.get('existing_option_records', [])))
    for c in represented:
        if c['product_id'] in packet['option_ids']:
            fields = c.get('master_fields', c.get('qualified_working_fields'))
            assert fields == options[c['product_id']]['master_fields']

refs = sorted({ref for x in packets for ref in x['offer_refs']}, key=lambda x: int(x[1:]))
ids = sorted({oid for x in packets for oid in x['option_ids']})
assert len(packets) == 9 and len(refs) == 30 and len(ids) == 27
components = []
for oid in ids:
    o = options[oid]
    assert oid in g['active_option_ids'] and len(o['master_fields']) == 6
    assert all(o[k] == assets[o['file_id']][k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url'])
    components.append({k: o[k] for k in ['product_id', 'name', 'canonical_component_id', 'file_id', 'folder_id', 'image_url', 'folder_url', 'master_fields']})

continuation = []
class PageAnchors(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids = set()
        self.feed(Path(path).read_text())
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'id' in values:
            self.ids.add(values['id'])
for packet in packets[-3:]:
    r = read(packet['review_json'])
    records = r.get('components', r.get('individual_options', []))
    anchors = PageAnchors(packet['review']).ids
    for oid in packet['option_ids']:
        c = next(x for x in records if x['product_id'] == oid)
        findings = [x['finding'] for x in r.get('cases', []) if oid in x.get('related_option_ids', x.get('option_ids', [x.get('option_id')]))]
        fragment = oid if oid in anchors else next(x['ref'] for x in r['cases'] if x.get('option_id') == oid)
        assert fragment in anchors
        continuation.append({'option_id': oid, 'review': packet['review'] + '#' + fragment, 'title': packet['title'],
            'offer_refs': packet['offer_refs'], 'finding': c.get('finding', ' '.join(findings)), 'scope': packet['scope']})
assert len(continuation) == 12

directory = ROOT / 'reports/dropbox-wall-only-leaf-growth-fountain-palm-review-20261024T201625Z'
assert sha(directory / 'review-seal.json') == 'efda7c4cbd13a39249fb8d6932bfd81c141b549351d94bc11d6ba701ae08e0d5'
directory_paths = ['review-seal.json', 'validation.json', 'review-findings-and-all-family-links.html', 'all-316-image-folder-links-and-review.json']
directory_sealed_members = {x['path']: x['sha256'] for x in read(directory / 'review-seal.json')['files']}
for name in directory_paths[1:]:
    assert sha(directory / name) == directory_sealed_members[name]
dv = read(directory / 'validation.json')
assert dv['originals'] == 316 and dv['native_writes'] == dv['canonical_writes'] == 0
assert dv['observations_are_not_move_approval']
directory_ref = {'review': str(directory / 'review-findings-and-all-family-links.html'),
    'validation': str(directory / 'validation.json'), 'seal': str(directory / 'review-seal.json'),
    'sealed_link_files': {str(directory / x): sha(directory / x) for x in directory_paths},
    'originals': 316, 'families': ['Leaf Growth', 'Fountain Palm'], 'scope': 'Read-only filing observations; no move approval or new product/specification inference.'}

counts = {'review_packets': 9, 'retained_source_offers': 30, 'existing_options': 27, 'full_qualified_working_fields': 162,
    'new_platform_pairs': 0, 'new_physical_verifications': 0, 'new_product_records': 0}
index = {'status': 'CURRENT_LINKED_SOURCE_COMPONENT_REVIEW_EVIDENCE', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'source_register_sha256': old['register_sha256'], 'source_workbook_sha256': old['workbook_sha256'],
    'current_asset_map': asset_ref, 'review_packets': packets, 'retained_source_offer_refs': refs,
    'existing_option_records': components, 'continuation_components': continuation, 'counts': counts,
    'provider_files': provider_files, 'read_only_directory_review': directory_ref,
    'interpretation': 'The index covers retained source records and existing individual options. Photograph correspondences, source-variant applicability and physical verification have separate evidence states. No new platform pairs, products or physical specifications are certified.',
    'one_case_navigation_refresh': correction,
    'review_baseline_scope': 'Each sealed packet retains its original source clocks and map hashes. Its included individual fields and current image/parent links are checked again against the current register and new navigation map.'}
write(H / 'source-photo-review-index.json', index)
OUT.mkdir(exist_ok=True)
cards = ''.join('<article><h2><a href="' + esc(x['review']) + '">' + esc(x['title']) + '</a></h2><p>' + esc(x['scope']) + '</p><p>Source records: ' + esc(', '.join(x['offer_refs'])) + '</p></article>' for x in packets)
rows = ''
for o in components:
    fields = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v['display']) + '<p class="qualification">' + esc(v['state']) + '</p></td></tr>' for k, v in o['master_fields'].items())
    rows += '<details id="' + esc(o['product_id']) + '"><summary>' + esc(o['name']) + '</summary><p><a href="' + esc(o['image_url']) + '">Individual image</a> · <a href="' + esc(o['folder_url']) + '">Containing folder</a></p><p><small>' + esc(o['file_id']) + ' / ' + esc(o['folder_id']) + '</small></p><table>' + fields + '</table></details>'
(OUT / 'index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Individual sculpture source reviews</title><style>body{font:17px Arial;line-height:1.5;max-width:1050px;margin:40px auto;padding:0 20px;color:#222}article,details{border-top:1px solid #bbb;padding:20px 0}summary{font-size:20px;cursor:pointer}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd;overflow-wrap:anywhere}th{width:23%}.qualification{font-size:13px;color:#555}</style></head><body><h1>Individual sculpture source reviews</h1><p>Nine completed reviews cover 30 retained source offers and 27 existing individual options, with 162 full qualified specification fields.</p><p>' + esc(index['interpretation']) + '</p>' + cards + '<article><h2><a href="' + esc(directory_ref['review']) + '">Leaf Growth and Fountain Palm: all 316 photographs and containing folders</a></h2><p>' + esc(directory_ref['scope']) + '</p></article><h2>Current Flower display-folder link</h2><p><a href="' + esc(correction['fresh_reference']['image_url']) + '">Display image</a> · <a href="' + esc(correction['fresh_reference']['folder_url']) + '">Containing folder</a>. Capitalization corrected using the same file and parent IDs.</p><h2>Existing individual options</h2>' + rows + '</body></html>')

controls = [B / x for x in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']]
inputs = {'pointer': B / 'current-master.json', 'register': B / old['register'], 'workbook': B / old['workbook'],
    'native_map': B / old['current_native_reference_map']['path'], 'asset_map': B / old['current_asset_reference_map']['path'],
    'audit': Path(old['latest_image_coverage_audit']['path']), **{f'control_{i}': x for i, x in enumerate(controls)}}
(H / 'inputs').mkdir(exist_ok=True)
manifest = {}
for key, path in inputs.items():
    snap = H / 'inputs' / (key + '.before')
    snap.write_bytes(path.read_bytes())
    manifest[key] = {'path': str(path), 'snapshot': str(snap), 'sha256': sha(path)}
write(H / 'input-manifest.json', manifest)
p = copy.deepcopy(old)
p.update(recorded_utc=index['recorded_utc'], publication_receipt=str((H / 'publication-receipt.json').relative_to(B)),
    current_asset_reference_map=asset_ref, current_native_reference_map=native_ref,
    current_source_photo_review_index={'path': str((H / 'source-photo-review-index.json').relative_to(B)),
        'sha256': sha(H / 'source-photo-review-index.json'), 'review': str((OUT / 'index.html').relative_to(B)),
        'review_sha256': sha(OUT / 'index.html'), 'counts': counts},
    latest_acanthus_flower_case_navigation={'path': str(H / 'flower-case-navigation.json'), 'sha256': sha(H / 'flower-case-navigation.json'),
        'file_id': fid, 'folder_id': parent, 'actual_parent_changes': 0, 'native_writes': 0},
    latest_master_metadata_change={'status': 'SOURCE_COMPONENT_INDEX_AND_ONE_SAME_ID_CASE_LINK_REFRESH',
        'path': str((H / 'publication-receipt.json').relative_to(B)), 'preceding_publication_receipt': old['publication_receipt'],
        'register_workbook_and_coverage_audit_unchanged': True})
write(H / 'prepared-pointer.json', p)
prepared = {}
for i, dest in enumerate(controls):
    d = read(dest)
    assert d['current_master_catalogue'] == old
    d.update(updated_utc=p['recorded_utc'], current_master_catalogue=copy.deepcopy(p),
        **{k: copy.deepcopy(p[k]) for k in ['current_asset_reference_map', 'current_native_reference_map', 'current_source_photo_review_index', 'latest_acanthus_flower_case_navigation', 'latest_master_metadata_change']})
    target = H / f'prepared-control-{i}.json'
    write(target, d)
    prepared[str(dest)] = str(target)
write(H / 'prepared-control-paths.json', prepared)
assert all(sha(x['path']) == x['sha256'] for x in manifest.values())
verification = {'status': 'PASS', 'counts': counts, 'all27_selected_links_and162_full_fields_preserved': True,
    'asset_ID_population_unchanged': len(assets), 'native_ID_population_unchanged': len(native['current_objects']),
    'changed_asset_records': [fid], 'changed_native_objects': [fid], 'actual_parent_changes': 0,
    'old_published_artifacts_unchanged': True, 'register_workbook_and_audit_unchanged': True, 'native_or_platform_writes': 0}
write(H / 'candidate-verification.json', verification)
frozen = [Path(__file__), H / 'publish_metadata.py', H / 'source-photo-review-index.json', OUT / 'index.html',
    H / 'current-assets.json', H / 'current-native-reference-map.json', H / 'flower-case-navigation.json',
    H / 'input-manifest.json', H / 'prepared-pointer.json', H / 'prepared-control-paths.json',
    H / 'candidate-verification.json', *map(Path, prepared.values())]
write(H / 'candidate-freeze.json', {'status': 'FROZEN_SOURCE_COMPONENT_AND_ONE_CASE_METADATA',
    'candidate_register_sha256': old['register_sha256'], 'candidate_workbook_sha256': old['workbook_sha256'],
    'frozen_artifacts': {str(x): sha(x) for x in frozen}})
print(json.dumps({**verification, 'candidate_freeze_sha256': sha(H / 'candidate-freeze.json')}))
