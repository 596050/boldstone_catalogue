"""Read serialized outputs and compare them directly with preserved inputs."""
import csv
import hashlib
import html
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
checks = []


def check(name, condition):
    checks.append({'check': name, 'pass': bool(condition)})
    assert condition, name


report = read(H / 'review.json')
seal = read(H / 'sealed-handoff.json')
for name, expected in seal['files'].items():
    check('Sealed output bytes: ' + name, sha(H / name) == expected)
for path, expected in report['source_inputs'].items():
    check('Preserved input bytes: ' + path, sha(path) == expected)
for path, expected in report['local_image_files'].items():
    check('Image bytes retained: ' + path, sha(path) == expected)
pointer = read(B / 'current-master.json')
check('Current pointer still exact reviewed pointer', sha(B / 'current-master.json') == report['source_pointer_sha256'])
register = read(B / pointer['register'])
options = {x['product_id']: x for x in register['options']}
index = read(B / 'components/evidence/offer_review_index.json')
readback = read(B / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json')
with Path(readback['sources'][1]['path']).open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))


class ParsedHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.local, self.ids, self.fragments, self.pres = [], set(), [], []
        self.pre = None

    def handle_starttag(self, tag, attrs):
        if tag == 'pre':
            self.pre = []
        for key, value in attrs:
            if key == 'id':
                self.ids.add(value)
            if key in ['href', 'src'] and value:
                parsed = urlsplit(value)
                if not parsed.scheme and not parsed.netloc:
                    if value.startswith('#'):
                        self.fragments.append(value[1:])
                    else:
                        self.local.append(H / unquote(parsed.path))

    def handle_data(self, data):
        if self.pre is not None:
            self.pre.append(data)

    def handle_endtag(self, tag):
        if tag == 'pre' and self.pre is not None:
            self.pres.append(json.loads(''.join(self.pre)))
            self.pre = None


parsed = ParsedHTML()
parsed.feed((H / 'index.html').read_text())
fields_from_html = [x for x in parsed.pres if isinstance(x, dict) and 'display' in x and 'state' in x and 'proposal_ids' in x]
fields_from_report = [f for c in report['components'] for f in c['master_fields'].values()]
check('Eighteen complete field objects serialized into HTML unchanged', fields_from_html == fields_from_report and len(fields_from_html) == 18)
check('Every local HTML link resolves including verification receipt', all(p.is_file() for p in parsed.local))
check('Every same-page HTML anchor resolves', all(fragment in parsed.ids for fragment in parsed.fragments))
for c in report['components']:
    current = options[c['product_id']]
    check('Whole current option unchanged: ' + c['product_id'], digest(current) == c['whole_option_sha256'])
    check('All full fields copied exactly: ' + c['product_id'], current['master_fields'] == c['master_fields'] and digest(c['master_fields']) == c['working_fields_sha256'])
    check('Related and supported scopes copied exactly: ' + c['product_id'], current['related_platform_offer_refs'] == c['existing_related_offer_refs'] and current['source_supported_platform_scope_refs'] == c['existing_source_supported_offer_refs'])
for c in report['cases']:
    edge = next(x for x in register['source_offer_edges'] if x['offer_ref'] == c['offer_ref'])
    check('Raw source, member order/quantity and source-reference role unchanged: ' + c['offer_ref'], edge['source_offer'] == c['retained_source_offer'] and edge['members'] == c['retained_BOM_members'] and edge['current_primary_reference'] == c['retained_current_source_reference'])
    row = next(x for x in rows if x['Product ID [Non Editable]'] == c['native_product_id'] and x['Variant ID [Non Editable]'] == c['native_variant_id'] and x['SKU'] == c['sku'])
    check('Captured gallery order re-read from export: ' + c['offer_ref'], row['Hosted Image URLs'].split() == [x['url'] for x in c['all_captured_media_records']])
    indexed = next(x for x in index if x['ref'] == c['offer_ref'])
    check('Eight saved views retain source URL order: ' + c['offer_ref'], [x['url'] for x in indexed['images']] == [x['source_url'] for x in c['viewed_source_renditions']])
    for view in c['viewed_source_renditions']:
        if view['source_original_available']:
            check('Re-read original matches declared hash: ' + c['offer_ref'] + ':' + str(view['retained_image_order']), sha(view['path']) == view['declared_original_sha256'])
        else:
            check('Unavailable indexed original remains qualified: ' + c['offer_ref'] + ':' + str(view['retained_image_order']), not Path(view['declared_original_path']).exists() and view['original'] is None and not view['source_original_bytes_verified_against_preserved_index'])
check('Moonwater close-up reference remains distinct from selected photograph', report['cases'][1]['retained_current_source_reference']['file_id'] == 'id:cnqzTNngPVsAAAAAAAs6lA' and report['components'][1]['file_id'] == 'id:cnqzTNngPVsAAAAAAAt4Sw' and not report['cases'][1]['source_reference_is_selected_option_photo'])
check('Bone garden context and close-up remain separate roles', report['cases'][2]['retained_current_source_reference']['file_id'] == 'id:cnqzTNngPVsAAAAAAAyiAg' and report['components'][2]['file_id'] == 'id:cnqzTNngPVsAAAAAAAyiBA')
check('No selected Moonwater whole-frame match claimed', all(x['target_file_id'] != 'id:cnqzTNngPVsAAAAAAAt4Sw' for x in report['photo_comparisons']))
check('Three unviewed gallery records remain explicit', [x['display_index'] for x in report['cases'][2]['all_captured_media_records'] if not x['saved_view_reviewed']] == [3, 4, 5])
check('Local-only boundaries retained', all(report['counts'][k] == 0 for k in ['live_calls', 'new_downloads', 'fresh_native_original_byte_verifications', 'new_physical_verifications', 'new_source_SKU_assignments', 'new_platform_pairs', 'native_or_platform_or_shared_writes', 'new_owner_questions']))
receipt = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'checks_passed': len(checks), 'checks_total': len(checks),
    'checks': checks, 'source_pointer_sha256': report['source_pointer_sha256'], 'review_sha256': sha(H / 'review.json'),
    'sealed_handoff_sha256': sha(H / 'sealed-handoff.json'), 'counts': report['counts']}
(H / 'independent-readback.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
(H / 'sealed-readback.json').write_text(json.dumps({'status': 'SEALED_INDEPENDENT_SERIALIZED_READBACK', 'recorded_utc': receipt['recorded_utc'],
    'sealed_handoff_sha256': sha(H / 'sealed-handoff.json'), 'files': {n: sha(H / n) for n in ['independent_readback.py', 'independent-readback.json']}}, indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'checks_passed': len(checks), 'sealed_handoff_sha256': sha(H / 'sealed-handoff.json'),
    'independent_readback_sha256': sha(H / 'independent-readback.json'), 'sealed_readback_sha256': sha(H / 'sealed-readback.json')}))
