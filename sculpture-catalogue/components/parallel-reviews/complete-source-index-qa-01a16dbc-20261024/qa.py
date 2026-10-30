"""Bounded QA of the explicitly handed-off final source-review index freeze."""
import csv
import hashlib
import html
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = B / 'components/reconciliation/source-review-index-completion-2026-10-24'
OUT = Path(__file__).resolve().parent
FREEZE_SHA = 'd14fcea4dcd08a16627ac549f44290762ed083e48df4fbf367b3cf4f26e82083'
COUNTS = {'review_packets': 14, 'retained_source_offers': 46, 'existing_options': 43,
          'full_qualified_working_fields': 258, 'new_platform_pairs': 0,
          'new_physical_verifications': 0, 'new_product_records': 0}
NEW_REFS = {'O005', 'O024', 'O025', 'O049', 'O050', 'O051', 'O052', 'O058',
            'O059', 'O060', 'O063', 'O066', 'O067', 'O068', 'O073', 'O079'}
POINTER_KEYS = {'recorded_utc', 'publication_receipt', 'current_source_photo_review_index', 'latest_master_metadata_change'}
CONTROL_KEYS = {'updated_utc', 'current_master_catalogue', 'current_source_photo_review_index', 'latest_master_metadata_change'}
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())
diff = lambda a, b: {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
checks = []


def check(name, passed, detail=None):
    checks.append({'check': name, 'pass': bool(passed), 'detail': detail})


def files_from_seal(path):
    members = read(path)['files']
    pairs = members.items() if isinstance(members, dict) else [(x['path'], x['sha256']) for x in members]
    return {str(Path(n) if Path(n).is_absolute() else Path(path).parent / n): v if isinstance(v, str) else v['sha256'] for n, v in pairs}


def dropbox_path(url):
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    for prefix in ['/preview', '/home']:
        if path.startswith(prefix + '/'):
            path = path[len(prefix):]
            break
    preview = parse_qs(parsed.query).get('preview')
    return path.rstrip('/') + ('/' + preview[0] if preview else '')


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'href' and value:
                self.links.append(value)
            if value and (key == 'id' or tag == 'a' and key == 'name'):
                self.ids.add(value)


baseline = read(OUT / 'baseline.json')
before = read(OUT / 'baseline/current-master.json')
freeze = read(H / 'candidate-freeze.json')
check('Exact final handed-off freeze identity', sha(H / 'candidate-freeze.json') == FREEZE_SHA)
check('All eleven frozen artifacts exact and nonempty', len(freeze['frozen_artifacts']) == 11 and all(sha(p) == v for p, v in freeze['frozen_artifacts'].items()))
manifest = read(H / 'input-manifest.json')
candidate = read(H / 'prepared-pointer.json')
check('Independent baseline agrees with publisher snapshot', manifest['pointer']['sha256'] == baseline['pointer_sha256'] == sha(OUT / 'baseline/current-master.json') and read(manifest['pointer']['snapshot']) == before)
for label, entry in manifest.items():
    check('Frozen source snapshot and current bytes: ' + label, sha(entry['path']) == sha(entry['snapshot']) == entry['sha256'])
for label, entry in baseline['data_files'].items():
    check('Independent original data hash unchanged: ' + label, sha(entry['path']) == entry['sha256'])
for name, entry in baseline['snapshots'].items():
    check('Independent control/pointer snapshot bytes unchanged: ' + name, sha(entry['snapshot']) == sha(entry['path']) == entry['sha256'])
check('Only four permitted pointer metadata fields change', diff(before, candidate) == POINTER_KEYS, sorted(diff(before, candidate)))
check('Register/workbook hashes match exact freeze and independent baseline', candidate['register_sha256'] == freeze['candidate_register_sha256'] == baseline['data_files']['register']['sha256'] and candidate['workbook_sha256'] == freeze['candidate_workbook_sha256'] == baseline['data_files']['workbook']['sha256'])
check('Both explicit asset/native descriptors unchanged', candidate['current_asset_reference_map'] == before['current_asset_reference_map'] and candidate['current_native_reference_map'] == before['current_native_reference_map'])
check('Metadata declaration preserves five data artifacts', candidate['latest_master_metadata_change']['register_workbook_navigation_and_coverage_audit_unchanged'] is True)
register = read(B / candidate['register'])
options = {x['product_id']: x for x in register['options']}
assets = read(B / candidate['current_asset_reference_map']['path'])
prior = read(B / before['current_source_photo_review_index']['path'])
check('Preceding index descriptor and original bytes retained', sha(B / before['current_source_photo_review_index']['path']) == before['current_source_photo_review_index']['sha256'] and sha(B / before['current_source_photo_review_index']['review']) == before['current_source_photo_review_index']['review_sha256'])
descriptor = candidate['current_source_photo_review_index']
index_path, html_path = B / descriptor['path'], B / descriptor['review']
index = read(index_path)
check('Exact new index JSON and HTML descriptor bytes', sha(index_path) == descriptor['sha256'] and sha(html_path) == descriptor['review_sha256'])
check('Exact fourteen packet and field counts', descriptor['counts'] == index['counts'] == COUNTS)
check('Index uses same register/workbook/asset references', index['source_register_sha256'] == candidate['register_sha256'] and index['source_workbook_sha256'] == candidate['workbook_sha256'] and index['current_asset_map'] == candidate['current_asset_reference_map'])
check('Prior nine packets, index lineage and twelve continuation cards preserved', index['review_packets'][:9] == prior['review_packets'] and index['preceding_index'] == before['current_source_photo_review_index'] and index['continuation_components'][:12] == prior['continuation_components'])
check('Existing one-file navigation observation unchanged', index['one_case_navigation_refresh'] == prior['one_case_navigation_refresh'])
expected_refs = set(prior['retained_source_offer_refs']) | NEW_REFS
source_csv = B.parent / 'reports/catalogue-terminal-walkthrough-20261024/Squarespace_Source_Offers_Without_Historical_Shopify_Pair_43.csv'
with source_csv.open(encoding='utf-8-sig', newline='') as stream:
    unpaired_refs = {x['offer_ref'] for x in csv.DictReader(stream)}
check('Exact independently enumerated forty-six source references', set(index['retained_source_offer_refs']) == expected_refs and len(index['retained_source_offer_refs']) == len(expected_refs) == 46)
check('All forty-two unpaired source records reviewed, Wall Circle stays held', len(unpaired_refs) == 43 and unpaired_refs - expected_refs == {'O001'} and expected_refs - unpaired_refs == {'O024', 'O025', 'O027', 'O047'})
provider_files, refs, option_ids = {}, set(), set()
for packet in index['review_packets']:
    label = Path(packet['seal']).parent.name
    members = files_from_seal(packet['seal'])
    check('Provider seal and all declared artifact bytes: ' + label, sha(packet['seal']) == packet['seal_sha256'] and all(sha(p) == v for p, v in members.items()))
    check('Provider report and verification bound to its seal: ' + label, members.get(packet['review_json']) == packet['review_sha256'] == sha(packet['review_json']) and members.get(packet['verification']) == packet['verification_sha256'] == sha(packet['verification']) and packet['review'] in members and read(packet['verification'])['status'] == 'PASS')
    provider_files.update(members)
    provider_files[packet['seal']] = packet['seal_sha256']
    review = read(packet['review_json'])
    sources = review.get('source_records', review.get('cases', []))
    components = review.get('components', review.get('individual_options', review.get('cases', [])))
    check('Provider source and component scopes unchanged: ' + label, {x.get('offer_ref', x.get('ref')) for x in sources} == set(packet['offer_refs']) and {x.get('product_id', x.get('option_id')) for x in components} == set(packet['option_ids']))
    refs.update(packet['offer_refs'])
    option_ids.update(packet['option_ids'])
check('Provider union matches forty-six sources and forty-three existing options', len(index['review_packets']) == 14 and refs == expected_refs and len(option_ids) == 43)
check('Exactly121 sealed provider artifacts remain separate from directory links', provider_files == index['provider_files'] and len(provider_files) == 121)
records = index['existing_option_records']
check('Exact existing active forty-three option IDs', len(records) == 43 and {x['product_id'] for x in records} == option_ids <= set(register['active_option_ids']))
text = html_path.read_text()
for record in records:
    option, asset = options[record['product_id']], assets[record['file_id']]
    check('Complete unchanged selected record and six qualified field objects: ' + record['product_id'], all(record[k] == option[k] for k in ['name', 'canonical_component_id', 'file_id', 'folder_id', 'image_url', 'folder_url', 'master_fields']) and len(record['master_fields']) == 6 and record['folder_id'] == asset['folder_id'] and all(dropbox_path(record[k]) == dropbox_path(asset[k]) for k in ['image_url', 'folder_url']))
    check('Rendered values retain full state text: ' + record['product_id'], all(html.escape(field['display'], quote=True) in text and html.escape(field['state'], quote=True) in text for field in record['master_fields'].values()))
check('All258 full working-field objects retained', sum(len(x['master_fields']) for x in records) == 258)
check('Original directory descriptor unchanged', index['read_only_directory_review'] == prior['read_only_directory_review'])
directories = [index['read_only_directory_review'], *index['additional_read_only_directory_reviews']]
check('Three separately linked directory observations keep316,160,182 originals', [x['originals'] for x in directories] == [316, 160, 182])
for directory in directories:
    label = ', '.join(directory['families'])
    linked = directory['sealed_link_files']
    members = files_from_seal(directory['seal'])
    check('Four directory link artifacts exact in original seal: ' + label, len(linked) == 4 and all(sha(p) == v and (p == directory['seal'] or members.get(p) == v) for p, v in linked.items()))
    validation = read(directory['validation'])
    check('Directory observations retain zero native and canonical writes: ' + label, validation['native_writes'] == validation['canonical_writes'] == 0 and validation['originals'] == directory['originals'])
check('Pending filing proposals remain unapplied in supplemental observations', read(directories[1]['validation'])['proposed_moves_applied'] == 0 and read(directories[2]['validation'])['pending_Rust12_Bone40_Chiswick015_not_approved_or_applied'] is True)
prepared_paths = read(H / 'prepared-control-paths.json')
expected_controls = {baseline['snapshots'][name]['path'] for name in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']}
check('Exactly three original control destinations', set(prepared_paths) == expected_controls)
for target, prepared in prepared_paths.items():
    original = read(target)
    new = read(prepared)
    check('Exact four control metadata fields change: ' + target, diff(original, new) == CONTROL_KEYS)
    check('Full candidate pointer and metadata synchronized: ' + target, original['current_master_catalogue'] == before and new['current_master_catalogue'] == candidate and new['updated_utc'] == candidate['recorded_utc'] and all(new[k] == candidate[k] for k in ['current_source_photo_review_index', 'latest_master_metadata_change']))
parser = Links()
parser.feed(text)
local, unresolved = [], []
for url in parser.links:
    parsed = urlsplit(url)
    if parsed.scheme in ['', 'file']:
        target = Path(unquote(parsed.path)) if parsed.path else html_path
        target = target if target.is_absolute() else html_path.parent / target
        local.append(target)
        if parsed.fragment and target.is_file():
            anchors = Links()
            anchors.feed(target.read_text())
            if unquote(parsed.fragment) not in anchors.ids:
                unresolved.append(url)
check('All local index/report links and fragments resolve', all(p.is_file() for p in local) and not unresolved, len(local))
check('Fourteen provider and three directory reports linked', {Path(x['review']) for x in index['review_packets'] + directories} <= set(local))
check('All forty-three current image and folder links rendered', all(x[k] in parser.links for x in records for k in ['image_url', 'folder_url']))
anchor_results = []
for card in index['continuation_components']:
    parsed = urlsplit(card['review'])
    target = Path(unquote(parsed.path))
    anchors = Links()
    if target.is_file():
        anchors.feed(target.read_text())
    anchor_results.append({'option_id': card['option_id'], 'review': card['review'], 'resolves': bool(parsed.fragment) and unquote(parsed.fragment) in anchors.ids and card['option_id'] in option_ids})
check('All twenty-eight continuation fragments resolve to existing sections', len(anchor_results) == 28 and all(x['resolves'] for x in anchor_results), anchor_results)
check('Evidence interpretation keeps physical and commercial authority separate', 'No new platform pair, product, stock or actual measurement is certified.' in index['interpretation'])
check('Final frozen identity and eleven artifacts remain unchanged after QA', sha(H / 'candidate-freeze.json') == FREEZE_SHA and all(sha(p) == v for p, v in freeze['frozen_artifacts'].items()))
for label, entry in baseline['data_files'].items():
    check('Original data unchanged at end: ' + label, sha(entry['path']) == entry['sha256'])
result = {'status': 'PASS' if all(x['pass'] for x in checks) else 'FAIL', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'phase': 'FROZEN_CANDIDATE', 'checks_passed': sum(x['pass'] for x in checks), 'checks_total': len(checks), 'checks': checks,
    'candidate_freeze_sha256': FREEZE_SHA, 'candidate_register_sha256': candidate['register_sha256'],
    'candidate_workbook_sha256': candidate['workbook_sha256'], 'candidate_pointer_sha256': sha(H / 'prepared-pointer.json'),
    'frozen_artifacts': freeze['frozen_artifacts'], 'counts': COUNTS, 'source_pointer_sha256': baseline['pointer_sha256'],
    'review_coverage': {'unpaired_sources': 43, 'reviewed_unpaired_source_records': 42, 'held_source_refs': ['O001'],
        'additional_related_source_refs': ['O024', 'O025', 'O027', 'O047'], 'source_csv': str(source_csv), 'source_csv_sha256': sha(source_csv)},
    'new_source_media_reviews': 0, 'live_calls': 0, 'native_or_platform_or_shared_writes': 0,
    'scope': 'Frozen index, sealed proof/link identity and metadata-only pointer/control QA. Provider photograph findings, missing images, exact-version limits and physical qualifications retain original scopes and clocks. No new media review or native call.'}
(OUT / 'candidate-readback.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
seal_files = ['qa.py', 'candidate-readback.json', 'baseline.json', *['baseline/' + Path(x['snapshot']).name for x in baseline['snapshots'].values()]]
(OUT / 'sealed-handoff.json').write_text(json.dumps({'status': result['status'], 'recorded_utc': result['recorded_utc'],
    'files': {n: sha(OUT / n) for n in seal_files}}, indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status', 'checks_passed', 'checks_total', 'candidate_pointer_sha256', 'counts']}, indent=2))
print('QA seal SHA256:', sha(OUT / 'sealed-handoff.json'))
for x in checks:
    if not x['pass']:
        print('FAIL', x)
raise SystemExit(0 if result['status'] == 'PASS' else 1)
