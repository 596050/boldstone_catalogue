"""Independently verify the frozen evidence index; never write shared state."""
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = B / 'components/reconciliation/source-photo-evidence-index-2026-10-24'
OUT = Path(__file__).resolve().parent
EXPECTED_FREEZE = '85b04546aecfd9b80e7e04cbc67b494dcb50eba1fefa533f5e1a975d0358e0b8'
EXPECTED_REFS = {'O002', 'O003', 'O004', 'O006', 'O007', 'O008', 'O009', 'O011', 'O027', 'O047', 'O053', 'O054', 'O055', 'O056', 'O064'}
EXPECTED_COUNTS = {'review_packets': 5, 'retained_source_offers': 15, 'existing_options': 11,
                   'full_qualified_working_fields': 66, 'new_platform_pairs': 0,
                   'new_physical_verifications': 0, 'new_product_records': 0}
EXPECTED_SEALS = {
    'source-photo-finish-review-20261024-root': '84ef2ad1019ea683daefcf0a29098193778b495dd84b0ae566f4f8c997ddd869',
    'o006-o007-source-photo-review-20261024-B': '7f40036e2122cd475c5ca18a2bbc0fe7b50baedf6176322377ebe976f1633cbd',
    'mcp4-three-source-review-20261024-B': '5f3660ae0d0503e60a8896b64b25a501636cd9efa568ae4eca7dd726ca32ec03',
    'o002-o004-source-photo-review-01a16dbc-20261024': '2f273f727cdb58f188160aff148c480a929c77cd94f84dd8d01d62aae6088ff1',
    'palm-form-component-review-20261024-root': '9732c2cd3fe75dc171b1a52261ea49ecc613b7112da62ffc397c48cc84e1728b',
}
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
checks = []


def check(name, passed, detail=None):
    checks.append({'check': name, 'pass': bool(passed), 'detail': detail})


def differences(before, after):
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


freeze_path = H / 'candidate-freeze.json'
freeze = read(freeze_path)
check('Exact frozen candidate identity', sha(freeze_path) == EXPECTED_FREEZE)
check('Explicit metadata-only frozen status', freeze['status'] == 'FROZEN_SOURCE_PHOTO_EVIDENCE_INDEX_METADATA')
check('All ten frozen artifact hashes', len(freeze['frozen_artifacts']) == 10 and all(sha(path) == expected for path, expected in freeze['frozen_artifacts'].items()))
manifest = read(H / 'input-manifest.json')
baseline = read(OUT / 'pre-index-baseline.json')
before = read(manifest['pointer']['snapshot'])
candidate = read(H / 'prepared-pointer.json')
index_path = H / 'source-photo-review-index.json'
index = read(index_path)
register = read(manifest['register']['path'])
options = {o['product_id']: o for o in register['options']}
assets = read(manifest['asset_map']['path'])
native = read(manifest['native_map']['path'])['current_objects']
check('Source pointer agrees with independent pre-index baseline', manifest['pointer']['sha256'] == baseline['pointer_sha256'] == sha(OUT / 'pointer.before.json'))
for key, value in manifest.items():
    check('Frozen source snapshot: ' + key, sha(value['snapshot']) == value['sha256'])
    check('Unchanged current source: ' + key, sha(value['path']) == value['sha256'])
for key in ['register', 'workbook', 'audit', 'native_map', 'asset_map']:
    baseline_key = 'assets' if key == 'asset_map' else key
    check('Protected data agrees with independent baseline: ' + key,
          baseline['data_files'][baseline_key] == {k: manifest[key][k] for k in ['path', 'sha256']})
check('Exact four pointer fields changed', differences(before, candidate) == ['current_source_photo_review_index', 'latest_master_metadata_change', 'publication_receipt', 'recorded_utc'], differences(before, candidate))
descriptor = candidate['current_source_photo_review_index']
check('Index descriptor hash/path/counts', B / descriptor['path'] == index_path and descriptor['sha256'] == sha(index_path) and descriptor['counts'] == EXPECTED_COUNTS)
html_path = B / descriptor['review']
check('HTML descriptor hash/path', html_path == B / 'outputs/source-photo-evidence-index-2026-10-24/index.html' and sha(html_path) == descriptor['review_sha256'])
check('Exact metadata publication receipt scope', candidate['publication_receipt'] == 'components/reconciliation/source-photo-evidence-index-2026-10-24/publication-receipt.json'
      and candidate['latest_master_metadata_change'] == {
          'status': 'COMPLETED_SOURCE_PHOTO_EVIDENCE_INDEXED_METADATA_ONLY',
          'path': candidate['publication_receipt'],
          'preceding_publication_receipt': before['publication_receipt'],
          'catalogue_register_workbook_audit_and_native_asset_maps_unchanged': True})
check('Register and workbook descriptors unchanged', index['source_register_sha256'] == candidate['register_sha256'] == before['register_sha256'] == manifest['register']['sha256']
      and index['source_workbook_sha256'] == candidate['workbook_sha256'] == before['workbook_sha256'] == manifest['workbook']['sha256'])
check('Explicit current asset descriptor retained', index['current_asset_map'] == candidate['current_asset_reference_map'] == before['current_asset_reference_map'])
check('Exact index counts with no authority upgrades', index['counts'] == EXPECTED_COUNTS)
check('Exact fifteen retained source references', set(index['retained_source_offer_refs']) == EXPECTED_REFS and len(index['retained_source_offer_refs']) == 15)
check('All source references remain in current register', EXPECTED_REFS <= {e['offer_ref'] for e in register['source_offer_edges']})
packet_refs, packet_options, provider_files = set(), set(), {}
for packet in index['review_packets']:
    seal_path = Path(packet['seal'])
    seal = read(seal_path)
    name = seal_path.parent.name
    check('Exact existing provider seal: ' + name, packet['seal_sha256'] == EXPECTED_SEALS.get(name) == sha(seal_path))
    paths = {(Path(path) if Path(path).is_absolute() else seal_path.parent / path): expected for path, expected in seal['files'].items()}
    check('All provider sealed members: ' + name, all(sha(path) == expected for path, expected in paths.items()), len(paths))
    provider_files.update({str(path): expected for path, expected in paths.items()})
    provider_files[str(seal_path)] = sha(seal_path)
    check('Review/verification are the sealed versions: ' + name,
          paths.get(Path(packet['review_json'])) == packet['review_sha256'] == sha(packet['review_json'])
          and paths.get(Path(packet['verification'])) == packet['verification_sha256'] == sha(packet['verification'])
          and Path(packet['review']) in paths and Path(packet['review']).is_file())
    check('Provider reports passed: ' + name, read(packet['verification'])['status'] == 'PASS')
    review = read(packet['review_json'])
    source_refs = {x['offer_ref'] for x in review.get('source_records', review.get('cases', []))}
    option_ids = {x.get('option_id', x.get('product_id')) for x in review.get('components', review.get('cases', []))}
    check('Provider source and option coverage preserved: ' + name, source_refs == set(packet['offer_refs']) and option_ids == set(packet['option_ids']))
    packet_refs.update(packet['offer_refs'])
    packet_options.update(packet['option_ids'])
check('Exactly five expected provider packets', len(index['review_packets']) == 5 and {Path(x['seal']).parent.name for x in index['review_packets']} == set(EXPECTED_SEALS))
check('Provider union gives fifteen sources and eleven existing options', packet_refs == EXPECTED_REFS and len(packet_options) == 11)
check('Provider manifest has all29 members plus5 seals, without extras', len(provider_files) == 34 and index['provider_files'] == provider_files)
records = index['existing_option_records']
check('Exactly the eleven existing option records', len(records) == 11 and {x['product_id'] for x in records} == packet_options)
for record in records:
    oid = record['product_id']
    option = options[oid]
    asset = assets[record['file_id']]
    check('Complete selected record and qualified fields: ' + oid,
          all(record[k] == option[k] for k in ['name', 'file_id', 'folder_id', 'image_url', 'folder_url', 'canonical_component_id', 'master_fields']) and len(record['master_fields']) == 6)
    check('Explicit asset and actual native parent: ' + oid,
          all(record[k] == asset[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url'])
          and native[record['file_id']]['parent_id'] == record['folder_id']
          and native[record['file_id']]['display_path'].startswith('/BOLDSTONE MASTER/'))
check('All66 complete field objects retained', sum(len(x['master_fields']) for x in records) == 66)
check('Unresolved bindings and physical count qualification retained',
      'not15new confirmed matches' in index['interpretation'] and 'not a new physical sculpture count' in index['interpretation']
      and 'unresolved' in next(x['scope'] for x in index['review_packets'] if 'O006' in x['offer_refs']))
controls = read(H / 'prepared-control-paths.json')
check('Exactly the three existing control destinations', set(controls) == {x['path'] for x in baseline['controls'].values()})
for target, prepared in controls.items():
    source = next(x for x in manifest.values() if x['path'] == target)
    old = read(source['snapshot'])
    new = read(prepared)
    check('Only four control fields changed: ' + target, differences(old, new) == ['current_master_catalogue', 'current_source_photo_review_index', 'latest_master_metadata_change', 'updated_utc'])
    check('Prepared control synchronized with complete candidate pointer: ' + target,
          new['current_master_catalogue'] == candidate and new['current_source_photo_review_index'] == descriptor
          and new['latest_master_metadata_change'] == candidate['latest_master_metadata_change']
          and new['updated_utc'] == candidate['recorded_utc'])


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.image_sources = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'href' and value:
                self.links.append(value)
            if tag == 'img' and key == 'src' and value:
                self.image_sources.append(value)


parser = Links()
parser.feed(html_path.read_text())
local = []
for link in parser.links:
    parsed = urlsplit(link)
    if parsed.scheme in ['', 'file']:
        path = Path(unquote(parsed.path))
        local.append(path if path.is_absolute() else html_path.parent / path)
check('All local index links exist', all(x.is_file() for x in local), len(local))
check('All five provider reviews are linked', {Path(x['review']) for x in index['review_packets']} <= set(local))
check('All eleven selected image and folder URLs are linked', all(x[key] in parser.links for x in records for key in ['image_url', 'folder_url']))
check('Index automatically loads no remote images', not any(urlsplit(x).scheme in ['http', 'https'] for x in parser.image_sources))
check('Freeze unchanged after QA', sha(freeze_path) == EXPECTED_FREEZE and all(sha(path) == expected for path, expected in freeze['frozen_artifacts'].items()))
report = {'status': 'PASS' if all(x['pass'] for x in checks) else 'FAIL',
          'recorded_utc': datetime.now(timezone.utc).isoformat(), 'phase': 'FROZEN_CANDIDATE',
          'candidate_freeze_sha256': EXPECTED_FREEZE, 'candidate_pointer_sha256': sha(H / 'prepared-pointer.json'),
          'source_pointer_sha256': baseline['pointer_sha256'], 'checks_passed': sum(x['pass'] for x in checks),
          'checks_total': len(checks), 'checks': checks, 'counts': EXPECTED_COUNTS,
          'protected_data_files': baseline['data_files'],
          'new_source_photo_reviews_or_original_binary_reads': 0, 'live_calls': 0,
          'native_or_platform_or_shared_writes': 0,
          'scope': 'Index, provider seals, exact field/navigation projections and prepared pointer/control references only; no source-photo conclusions rejudged.'}
(OUT / 'candidate-readback.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
(OUT / 'sealed-candidate-handoff.json').write_text(json.dumps({'status': report['status'], 'recorded_utc': report['recorded_utc'],
    'candidate_freeze_sha256': EXPECTED_FREEZE, 'files': {n: sha(OUT / n) for n in ['qa.py', 'pre-index-baseline.json', 'pointer.before.json', 'candidate-readback.json']}}, indent=2) + '\n')
print(json.dumps({k: report[k] for k in ['status', 'checks_passed', 'checks_total', 'counts', 'candidate_pointer_sha256']}, indent=2))
print('QA receipt:', OUT / 'candidate-readback.json')
print('QA seal SHA256:', sha(OUT / 'sealed-candidate-handoff.json'))
for failed in [x for x in checks if not x['pass']]:
    print('FAIL', failed)
raise SystemExit(0 if report['status'] == 'PASS' else 1)
