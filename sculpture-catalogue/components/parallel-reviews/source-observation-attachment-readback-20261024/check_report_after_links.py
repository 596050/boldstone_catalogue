"""Check only the source observation report/CSV projections of main's frozen candidate."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
LANE = Path(__file__).resolve().parent
CANDIDATE = ROOT / 'components/reconciliation/wave-moonshadow-mixed-scene-master-2026-10-24/canonical-master-register.json'
SHA = '06acd3dc3abb1146d79845dc5c895ee164f0c87ab97800fbe4d0e04e5be88f96'
OUT = ROOT / 'outputs/wave-moonshadow-mixed-scene-master-2026-10-24'
PAGE = OUT / 'captured-platform-source-observations.html'
SQ_CSV = OUT / 'Captured_Squarespace_Source_Joins_80.csv'
SH_CSV = OUT / 'Historical_Shopify_Current_Squarespace_Source_Pairs_37.csv'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return {'path': str(path), 'sha256': sha(path)}


class Report(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.headings, self.text, self.links = [], [], [], []
        self.table = self.row = self.cell = self.heading = None

    def handle_starttag(self, tag, attrs):
        if tag == 'h2':
            self.heading = []
        if tag == 'table':
            self.table = []
        if self.table is not None and tag == 'tr':
            self.row = []
        if self.row is not None and tag in ['td', 'th']:
            self.cell = []
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href')

    def handle_data(self, data):
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)
        if self.heading is not None:
            self.heading.append(data)

    def handle_endtag(self, tag):
        if tag == 'h2' and self.heading is not None:
            self.headings.append(''.join(self.heading))
            self.heading = None
        if tag in ['td', 'th'] and self.cell is not None:
            self.row.append(''.join(self.cell))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.table.append(self.row)
            self.row = None
        if tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None


assert sha(CANDIDATE) == SHA, 'Main frozen candidate changed.'
inputs_before = [ref(p) for p in [CANDIDATE, PAGE, SQ_CSV, SH_CSV]]
data = json.loads(CANDIDATE.read_text())['current_authenticated_squarespace_inventory_observation']
entries = data['retained_offer_observations']
pairs = data['historical_shopify_comparison']['pairs']
clock = data['squarespace_source_clock']['captured_utc']
with SQ_CSV.open(encoding='utf-8-sig', newline='') as f:
    sq_rows = list(csv.DictReader(f))
with SH_CSV.open(encoding='utf-8-sig', newline='') as f:
    sh_rows = list(csv.DictReader(f))
sq_by_id = {x['offer_ref']: x for x in sq_rows}
sh_by_handle = {x['historical_shopify_handle']: x for x in sh_rows}
sq_exact = []
for e in entries:
    r = sq_by_id[e['offer_ref']]
    ident = e['observed_native_source_tuple']
    sq_exact.append(r['squarespace_product_id'] == ident['product_id']
                    and r['squarespace_variant_id'] == ident['variant_id']
                    and r['source_sku'] == ident['sku_raw']
                    and r['source_capture_utc'] == clock
                    and json.loads(r['source_record_locator']) == e['source_record_locator']
                    and r['existing_related_option_ids'].splitlines() == e['existing_related_option_ids']
                    and r['new_exact_individual_configuration_verified'] == 'False'
                    and r['new_physical_verification'] == 'False')
sh_exact = []
for e in pairs:
    r = sh_by_handle[e['historical_shopify_handle']]
    native = e['fresh_squarespace_variant']
    historical = e['historical_shopify_variant']
    sh_exact.append(r['historical_shopify_sku'] == historical['sku_raw']
                    and r['squarespace_product_id'] == native['product_id']
                    and r['squarespace_variant_id'] == native['variant_id']
                    and r['squarespace_sku'] == native['sku_raw']
                    and json.loads(r['historical_shopify_source']) == historical['source_locator']
                    and r['squarespace_capture_utc'] == clock
                    and r['current_shopify_inventory_verified'] == 'False'
                    and r['exact_individual_configuration_verified'] == 'False')
page = Report()
page.feed(PAGE.read_text())
expected_tables = [[[f['field'], f['current_csv_value_raw'], f['comparison']] for f in e['fields']] for e in entries]
expected_headings = [e['offer_ref'] + ' ' + next(f['current_csv_value_raw'] for f in e['fields'] if f['csv_column'] == 'Title') for e in entries]
all_text = ' '.join(page.text)
checks = {
    'eighty_unique_join_rows_without_omissions_or_extras': len(sq_rows) == len(sq_by_id) == 80 and set(sq_by_id) == {e['offer_ref'] for e in entries},
    'all80_source_tuples_locators_clocks_related_references_and_false_upgrade_flags_exact': all(sq_exact),
    'thirtyseven_unique_historical_pair_rows_without_omissions_or_extras': len(sh_rows) == len(sh_by_handle) == 37 and set(sh_by_handle) == {e['historical_shopify_handle'] for e in pairs},
    'all37_historical_pair_tuples_locators_clocks_and_false_current_verification_flags_exact': all(sh_exact),
    'all80_source_report_headings_exact': page.headings == expected_headings,
    'all720_html_raw_values_and_comparison_methods_exact': page.tables == expected_tables,
    'all10_source_qualification_statements_visible': len(data['qualifications']) == 10 and all(q in all_text for q in data['qualifications']),
    'capture_time_and_separate_historical_shopify_scope_visible': clock in all_text and '37 Shopify comparisons use historical source records.' in all_text,
    'two_csv_download_links_present': all(target in {(PAGE.parent / unquote(urlparse(href).path)).resolve() for href in page.links if not urlparse(href).scheme and not urlparse(href).netloc} for target in [SQ_CSV.resolve(), SH_CSV.resolve()]),
    'frozen_candidate_and_projection_bytes_stable_through_readback': all(sha(x['path']) == x['sha256'] for x in inputs_before),
}
receipt = {
    'schema': 'boldstone.source-observation-projection-readback.v1',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'PASS_SOURCE_REPORT_AND_CSV_BOUNDARY_ONLY' if all(checks.values()) else 'FAIL_SOURCE_REPORT_AND_CSV_BOUNDARY_ONLY',
    'main_frozen_candidate': {'path': str(CANDIDATE), 'sha256': SHA, 'authority_thread': '01a144ab-1a7c-7223-a403-73a4d53d70ff'},
    'inputs': inputs_before,
    'attachment_readback': ref(LANE / 'candidate-readback-06acd3dc.json'),
    'checks': checks, 'passed': sum(checks.values()), 'total': len(checks),
    'scope': 'Source attachment projections only:80 joins,720 raw table fields,37 historical Shopify pairs,10 source qualifications and2CSV download links. No renewed source, native image, workbook, physical or live account audit.',
    'not_covered': ['A-owned Wave/navigation/legacy-data QA', 'Workbook authoring, style, rendering or calculation', 'Final pointer/publication/control closure'],
    'shared_writes': 0, 'native_or_platform_calls': 0,
    'checker': ref(Path(__file__).resolve()),
}
receipt['prior_report_check'] = {**ref(LANE / 'source-report-readback-06acd3dc.json'), 'scope': 'Preserved first pass:9 data checks passed;2CSV navigation links absent.'}
receipt_path = LANE / 'source-report-readback-after-links-06acd3dc.json'
with receipt_path.open('x') as f:
    json.dump(receipt, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'status': receipt['status'], 'passed': receipt['passed'], 'total': receipt['total'], 'receipt': ref(receipt_path)}, indent=2))
if not all(checks.values()):
    raise SystemExit(1)
seal = {'status': 'SEALED_SOURCE_ATTACHMENT_AND_REPORT_QA_ONLY',
        'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'main_frozen_candidate': receipt['main_frozen_candidate'],
        'files': [ref(LANE / p) for p in ['candidate-readback-06acd3dc.json', 'source-report-readback-06acd3dc.json', 'source-report-readback-after-links-06acd3dc.json', 'check_attachment.py', 'check_report.py', 'check_report_after_links.py']],
        'scope': receipt['scope'], 'publication_claim': False, 'shared_writes': 0}
seal_path = LANE / 'sealed-source-readback.json'
with seal_path.open('x') as f:
    json.dump(seal, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'seal': ref(seal_path)}, indent=2))
