"""Prepare the next source evidence index; data, navigation and holds stay intact."""
import copy
import hashlib
import html
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
OUT = B / 'outputs/source-review-index-completion-2026-10-24'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda x: html.escape(str(x), quote=True)
def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def normalized(url):
    u = urlparse(url)
    path = unquote(u.path)
    for prefix in ['/preview', '/home']:
        if path.startswith(prefix + '/'):
            path = path[len(prefix):]
            break
    preview = parse_qs(u.query).get('preview')
    return path.rstrip('/') + ('/' + preview[0] if preview else '')
class Anchors(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids = set()
        self.feed(Path(path).read_text())
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])

assert not (H / 'publication-receipt.json').exists()
assert sha(B / 'current-master.json') == '0864dc18f3496f3172b5430de48c1bbfa972858d84bbd38abd13ade424154966'
old = read(B / 'current-master.json')
assert sha(B / old['register']) == old['register_sha256']
assert sha(B / old['current_asset_reference_map']['path']) == old['current_asset_reference_map']['sha256']
assert sha(B / old['current_native_reference_map']['path']) == old['current_native_reference_map']['sha256']
g = read(B / old['register'])
options = {x['product_id']: x for x in g['options']}
assets = read(B / old['current_asset_reference_map']['path'])
prior = read(B / old['current_source_photo_review_index']['path'])
packets = copy.deepcopy(prior['review_packets'])
specs = [
 ('Moon Crater Phase 3, Dune Ripple Copper/Rust and Azure', B / 'components/parallel-reviews/mcp3-dune-copper-rust-azure-source-review-20261024-B',
  ['O005', 'O052', 'O068', 'O073'], '316ea2284e27a35a4254d13f67ccb5dd3e36c8653f0635cd3c27318d4307a996',
  'Four existing options;24 fields. Copper landscape frame remains unbound in the scoped cache. Azure alternate file versions and unviewed gallery records remain qualified.'),
 ('Frozen Fish finishes and Rust/Verdigris Panel', B / 'components/parallel-reviews/frozenfish-finishes-rust-panel-source-review-20261024-B',
  ['O049', 'O063', 'O066'], '17ce0790ef655c04d7a11e7cef7eb0a4ca51921a928ae1400337ff1fdc9804cc',
  'Three existing options;18 fields. Frozen Fish stays70 ×15cm; legacy identity deferred. Low-resolution frames, alternate image versions and the unapplied Rust filing proposal remain qualified.'),
 ('Decowaves individual members and two-/three-panel arrangements', ROOT / 'reports/decowaves-arrangement-component-review-20261024-root',
  ['O024', 'O025', 'O050', 'O060'], '707834472ad9d734a8bcfb8a44950c7a0b73d4a43ea66c1064cc4a13a20601d6',
  'Five existing options;30 fields. White three-panel arrangement is1–2–1, using two designs. Hero colour/framing differences, multiple current file candidates and set-level prices/weights remain separate.'),
 ('Dune Ripple 1 Rust: both retained source offers', B / 'components/parallel-reviews/dune-ripple1-rust-two-source-review-20261024-B',
  ['O051', 'O067'], '03d9c9012a1c7cdaa56cfca6d8e3a67e3cf3df7c5e6e2049d165cd578d8d0214',
  'One existing option;6 fields. Both distinct source tuples share a SKU; price, weight and stock observations remain separate. Reused Verdigris rear image does not certify Rust hardware.'),
 ('Leaf Form, Moon Water Catcher and Bone Water Spiral', B / 'components/parallel-reviews/leaf-moonwater-bone-source-review-01a16dbc-20261024',
  ['O058', 'O059', 'O079'], 'fc6597653c81bc84c6d800eb4020fcfaa72ccaaa5b06108e67d9dc6094249a2e',
  'Three existing options;18 fields. Four photograph correspondences, qualified source versions and Leaf display placements retained. Bone images are thumbnail-only; fitted fixing and physical specifications remain unverified.'),
]
new_packets = []
for title, folder, refs, seal_sha, scope in specs:
    assert sha(folder / 'sealed-handoff.json') == seal_sha
    review = read(folder / 'review.json')
    represented = review.get('components', review.get('individual_options', []))
    ids = [x['product_id'] for x in represented]
    packet = {'title': title, 'review': str(folder / 'index.html'), 'review_json': str(folder / 'review.json'),
        'review_sha256': sha(folder / 'review.json'), 'seal': str(folder / 'sealed-handoff.json'), 'seal_sha256': seal_sha,
        'verification': str(folder / 'verification.json'), 'verification_sha256': sha(folder / 'verification.json'),
        'offer_refs': refs, 'option_ids': ids, 'scope': scope}
    packets.append(packet)
    new_packets.append(packet)

provider_files = {}
for packet in packets:
    assert sha(packet['seal']) == packet['seal_sha256']
    assert sha(packet['review_json']) == packet['review_sha256']
    assert sha(packet['verification']) == packet['verification_sha256']
    files = read(packet['seal'])['files']
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
            assert c.get('master_fields', c.get('qualified_working_fields')) == options[c['product_id']]['master_fields']

refs = sorted({ref for x in packets for ref in x['offer_refs']}, key=lambda x: int(x[1:]))
ids = sorted({oid for x in packets for oid in x['option_ids']})
assert len(packets) == 14 and len(refs) == 46 and len(ids) == 43
components = []
for oid in ids:
    o = options[oid]
    assert oid in g['active_option_ids'] and len(o['master_fields']) == 6
    assert o['folder_id'] == assets[o['file_id']]['folder_id']
    assert all(normalized(o[k]) == normalized(assets[o['file_id']][k]) for k in ['image_url', 'folder_url'])
    components.append({k: o[k] for k in ['product_id', 'name', 'canonical_component_id', 'file_id', 'folder_id', 'image_url', 'folder_url', 'master_fields']})

# Keep the first12 entries in place; terminal item78 remains the earlier Flower case correction.
continuation = copy.deepcopy(prior['continuation_components'])
assert len(continuation) == 12
for packet in new_packets:
    r = read(packet['review_json'])
    represented = r.get('components', r.get('individual_options', []))
    anchors = Anchors(packet['review']).ids
    for c in represented:
        oid = c['product_id']
        cases = [x for x in r.get('cases', r.get('source_records', [])) if oid in x.get('related_option_ids', x.get('option_ids', [x.get('option_id')]))]
        fragment = oid if oid in anchors else next(x.get('ref', x.get('offer_ref')) for x in cases if x.get('ref', x.get('offer_ref')) in anchors)
        assert fragment in anchors
        continuation.append({'option_id': oid, 'review': packet['review'] + '#' + fragment, 'title': packet['title'],
            'offer_refs': packet['offer_refs'], 'finding': c.get('finding', ' '.join(x['finding'] for x in cases)), 'scope': packet['scope']})
assert len(continuation) == 28

directories = []
for folder, expected, count, families, link_file in [
 (ROOT / 'reports/dropbox-wall-only-textured-rust-review-20261024T203841Z', 'e30a81717ad6a3d4a438f5b46f714d46e2ba423d438c03bddd6b7fb3a83ae57b', 160, ['Textured Panels', 'Wall Panel Rust and Verdigris'], 'all-160-image-folder-links-and-review.json'),
 (ROOT / 'reports/dropbox-wall-only-deco-dune-ripple-review-20261024T204816Z', '7efd05eb9740ab603f4b47aee6c8b6b7fd8b8747b306fe86d78976d3a340c465', 182, ['Deco Dune Ripple'], 'all-182-image-folder-links-and-review.json')]:
    assert sha(folder / 'review-seal.json') == expected
    files = read(folder / 'review-seal.json')['files']
    members = {x['path']: x['sha256'] for x in files}
    linked = {}
    for name in ['validation.json', 'review-findings-and-all-family-links.html', link_file]:
        assert sha(folder / name) == members[name]
        linked[str(folder / name)] = members[name]
    linked[str(folder / 'review-seal.json')] = expected
    v = read(folder / 'validation.json')
    assert v['originals'] == count and v['native_writes'] == v['canonical_writes'] == 0
    directories.append({'review': str(folder / 'review-findings-and-all-family-links.html'), 'validation': str(folder / 'validation.json'),
        'seal': str(folder / 'review-seal.json'), 'sealed_link_files': linked, 'originals': count, 'families': families,
        'scope': 'Read-only filing observations. Existing proposed moves remain unapplied; photographs do not establish sculpture or physical stock counts.'})

counts = {'review_packets': len(packets), 'retained_source_offers': len(refs), 'existing_options': len(ids),
    'full_qualified_working_fields': len(ids) * 6, 'new_platform_pairs': 0, 'new_physical_verifications': 0, 'new_product_records': 0}
index = {'status': 'CURRENT_LINKED_SOURCE_COMPONENT_REVIEW_EVIDENCE', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'source_register_sha256': old['register_sha256'], 'source_workbook_sha256': old['workbook_sha256'],
    'current_asset_map': old['current_asset_reference_map'], 'review_packets': packets, 'retained_source_offer_refs': refs,
    'existing_option_records': components, 'continuation_components': continuation, 'counts': counts,
    'provider_files': provider_files, 'read_only_directory_review': prior['read_only_directory_review'],
    'additional_read_only_directory_reviews': directories, 'one_case_navigation_refresh': prior['one_case_navigation_refresh'],
    'interpretation': 'Existing source records and individual options are linked to checked photograph evidence. Design, finish, gallery composition, original-file identity, exact variant applicability and physical specifications retain separate evidence states. No new platform pair, product, stock or actual measurement is certified.',
    'review_baseline_scope': 'Each sealed packet keeps its original clocks and baseline hashes. All included field objects and current selected file/parent links have been checked against the current register and explicit navigation map.',
    'preceding_index': old['current_source_photo_review_index']}
write(H / 'source-photo-review-index.json', index)
OUT.mkdir(exist_ok=True)
cards = ''.join('<article><h2><a href="' + esc(x['review']) + '">' + esc(x['title']) + '</a></h2><p>' + esc(x['scope']) + '</p><p>Source records: ' + esc(', '.join(x['offer_refs'])) + '</p></article>' for x in packets)
rows = ''
for o in components:
    fields = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v['display']) + '<p class="qualification">' + esc(v['state']) + '</p></td></tr>' for k, v in o['master_fields'].items())
    rows += '<details id="' + esc(o['product_id']) + '"><summary>' + esc(o['name']) + '</summary><p><a href="' + esc(o['image_url']) + '">Individual image</a> · <a href="' + esc(o['folder_url']) + '">Containing folder</a></p><p><small>' + esc(o['file_id']) + ' / ' + esc(o['folder_id']) + '</small></p><table>' + fields + '</table></details>'
directory_links = ''.join('<article><h2><a href="' + esc(x['review']) + '">' + esc(', '.join(x['families'])) + ': all ' + str(x['originals']) + ' image/folder links</a></h2><p>' + esc(x['scope']) + '</p></article>' for x in [prior['read_only_directory_review'], *directories])
(OUT / 'index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Individual sculpture source reviews</title><style>body{font:17px Arial;line-height:1.5;max-width:1050px;margin:40px auto;padding:0 20px;color:#222}article,details{border-top:1px solid #bbb;padding:20px 0}summary{font-size:20px;cursor:pointer}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd;overflow-wrap:anywhere}th{width:23%}.qualification{font-size:13px;color:#555}</style></head><body><h1>Individual sculpture source reviews</h1><p>14 completed review packets cover46 retained source offers and43 existing options, preserving258 full qualified fields. These are evidence counts, not a count of sculptures or new platform matches.</p><p>' + esc(index['interpretation']) + '</p>' + cards + '<h2>Read-only folder reviews</h2>' + directory_links + '<h2>Existing individual options</h2>' + rows + '</body></html>')

controls = [B / x for x in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']]
inputs = {'pointer': B / 'current-master.json', 'register': B / old['register'], 'workbook': B / old['workbook'],
    'native_map': B / old['current_native_reference_map']['path'], 'asset_map': B / old['current_asset_reference_map']['path'],
    'audit': Path(old['latest_image_coverage_audit']['path']), **{f'control_{i}': x for i, x in enumerate(controls)}}
(H / 'inputs').mkdir(exist_ok=True)
manifest = {}
for key, path in inputs.items():
    snapshot = H / 'inputs' / (key + '.before')
    snapshot.write_bytes(path.read_bytes())
    manifest[key] = {'path': str(path), 'snapshot': str(snapshot), 'sha256': sha(path)}
write(H / 'input-manifest.json', manifest)
p = copy.deepcopy(old)
p.update(recorded_utc=index['recorded_utc'], publication_receipt=str((H / 'publication-receipt.json').relative_to(B)),
    current_source_photo_review_index={'path': str((H / 'source-photo-review-index.json').relative_to(B)),
        'sha256': sha(H / 'source-photo-review-index.json'), 'review': str((OUT / 'index.html').relative_to(B)),
        'review_sha256': sha(OUT / 'index.html'), 'counts': counts},
    latest_master_metadata_change={'status': 'SOURCE_COMPONENT_EVIDENCE_INDEX_ONLY',
        'path': str((H / 'publication-receipt.json').relative_to(B)), 'preceding_publication_receipt': old['publication_receipt'],
        'register_workbook_navigation_and_coverage_audit_unchanged': True})
write(H / 'prepared-pointer.json', p)
prepared = {}
for i, dest in enumerate(controls):
    d = read(dest)
    assert d['current_master_catalogue'] == old
    d.update(updated_utc=p['recorded_utc'], current_master_catalogue=copy.deepcopy(p),
        **{k: copy.deepcopy(p[k]) for k in ['current_source_photo_review_index', 'latest_master_metadata_change']})
    target = H / f'prepared-control-{i}.json'
    write(target, d)
    prepared[str(dest)] = str(target)
write(H / 'prepared-control-paths.json', prepared)
assert all(sha(x['path']) == x['sha256'] for x in manifest.values())
verification = {'status': 'PASS', 'counts': counts, 'all43_selected_links_and258_full_fields_preserved': True,
    'all_source_seals_and_members_checked': True, 'all28_terminal_option_fragments_exist': True,
    'prior12_terminal_entries_preserved': continuation[:12] == prior['continuation_components'],
    'all_five_data_artifacts_byte_identical': True, 'native_or_platform_writes': 0,
    'added_read_only_directory_reviews': [x['originals'] for x in directories]}
write(H / 'candidate-verification.json', verification)
frozen = [Path(__file__), H / 'publish_metadata.py', H / 'source-photo-review-index.json', OUT / 'index.html',
    H / 'input-manifest.json', H / 'prepared-pointer.json', H / 'prepared-control-paths.json',
    H / 'candidate-verification.json', *map(Path, prepared.values())]
write(H / 'candidate-freeze.json', {'status': 'FROZEN_SOURCE_COMPONENT_EVIDENCE_INDEX_ONLY',
    'candidate_register_sha256': old['register_sha256'], 'candidate_workbook_sha256': old['workbook_sha256'],
    'frozen_artifacts': {str(x): sha(x) for x in frozen}})
print(json.dumps({**verification, 'candidate_freeze_sha256': sha(H / 'candidate-freeze.json')}))
