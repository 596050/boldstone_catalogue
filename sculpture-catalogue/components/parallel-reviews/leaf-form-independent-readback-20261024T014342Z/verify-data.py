"""Independent Leaf Form data/report readback; never opens a pending workbook."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
D = ROOT / 'components/reconciliation/leaf-form-owner-display-correction-master-2026-10-24'
OUT = ROOT / 'outputs/leaf-form-owner-display-correction-master-2026-10-24'
REG = D / 'canonical-master-register.json'
AUDIT = D / 'image-coverage-current.json'
SHA_REG = '2205546ab8502b4723d1eb9597c6da4104f8df18e7addcfd1ad9d9a4df328c16'
SHA_AUDIT = '5614cae122df4342f5ec0bf1ac4abeb074b976287498659e3e64d84303a97a10'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
checks = []


def check(name, value, detail=None):
    checks.append({'name': name, 'passed': bool(value), 'detail': detail})


check('Exact main-frozen candidate register bytes', sha(REG) == SHA_REG)
check('Exact main-frozen candidate photo-audit bytes', sha(AUDIT) == SHA_AUDIT)
old = read(D / 'inputs/master_register.before')
new = read(REG)
oa = read(D / 'inputs/audit.before')
na = read(AUDIT)
check('Baseline register is exact752d published predecessor', sha(D / 'inputs/master_register.before') == '752d20c2ed792caed3a0227fae5c1248da812a1a6d57ef6f4bfef6f8c0e79ee6')
owner = read(ROOT / 'components/parallel-reviews/leaf-form-owner-repeated-design-20261024T013207Z/owner-correction.json')
seals = [
    (ROOT / 'components/parallel-reviews/leaf-form-owner-repeated-design-20261024T013207Z/sealed-handoff.json', '35bfdb1dd2102c48569353aafdbc1500d3d819f097a5445d41250af5f6f1640c'),
    (ROOT / 'components/parallel-reviews/leaf-form-owner-repeated-design-scope-20261024T013207Z/sealed-scope-final.json', '770972f7985687436492426f69686f49adac3e8c484f6dceb12fa7822729ccc7'),
]
check('Owner and final scope seals and referenced files remain exact', all(sha(p) == expected and all(sha(Path(f['path'])) == f['sha256'] for f in read(p)['files']) for p, expected in seals))
check('All189 retained option IDs and order unchanged', [o['product_id'] for o in old['options']] == [o['product_id'] for o in new['options']] and len(new['options']) == 189)
check('Active188 and retired lifecycle sets unchanged', old['active_option_ids'] == new['active_option_ids'] and len(new['active_option_ids']) == 188 and old['retired_option_ids'] == new['retired_option_ids'])
check('All six working field objects for every retained option unchanged', all(o['master_fields'] == n['master_fields'] for o, n in zip(old['options'], new['options'])))
check('All legacy specification assertions and commercial policies unchanged', all(all(o.get(k) == n.get(k) for k in ['specifications', 'selling_details', 'current_commercial_policy', 'physical_specifications_verified']) for o, n in zip(old['options'], new['options'])))
check('All188 other option records including Gold untouched', all(o == n for o, n in zip(old['options'], new['options']) if o['product_id'] != 'BSI-6581D83760F1'))
white = new['options'][100]
check('White record adds only exact owner interpretation', white['product_id'] == 'BSI-6581D83760F1' and {k: v for k, v in white.items() if k != 'current_owner_depiction_correction'} == old['options'][100])


def raw_source_preserved(key):
    a, b = old[key], new[key]
    return ([x['offer_ref'] for x in a] == [x['offer_ref'] for x in b] and
            all(x['source_offer'] == y['source_offer'] and
                [m['original_bom'] for m in x['members']] == [m['original_bom'] for m in y['members']] and
                [(m['bom_id'], m['position'], m['quantity'], m['source_component_id']) for m in x['members']] ==
                [(m['bom_id'], m['position'], m['quantity'], m['source_component_id']) for m in y['members']]
                for x, y in zip(a, b)))


check('All81 raw source offers, original BOM rows and positions/quantities unchanged', len(new['source_offer_edges']) == 81 and raw_source_preserved('source_offer_edges'))
check('All28 raw source-set offers and original BOM rows unchanged', len(new['source_sets']) == 28 and raw_source_preserved('source_sets'))
oe = next(x for x in old['source_offer_edges'] if x['offer_ref'] == 'O058')
ne = next(x for x in new['source_offer_edges'] if x['offer_ref'] == 'O058')
check('O058 standalone source edge retained exactly', oe == ne)
check('Original native action drafts and all four existing copy projections unchanged', old['listing_resolution_native_action_drafts'] == new['listing_resolution_native_action_drafts'] and old['current_existing_listing_copy_projections'] == new['current_existing_listing_copy_projections'])
check('Unrelated Gold source edge156 and media111 unchanged', old['current_listing_match_evidence']['edges'][156] == new['current_listing_match_evidence']['edges'][156] and old['source_media_configuration_coverage'][111] == new['source_media_configuration_coverage'][111])

corr = new['current_owner_depiction_corrections'][0]
check('One owner correction with exact original authority and image reference', len(new['current_owner_depiction_corrections']) == 1 and corr['decision_id'] == owner['decision_id'] and corr['authority'] == owner['authority'] and corr['image_reference'] == owner['image_reference'])
check('Exact current interpretation equals sealed owner decision', corr['current_interpretation'] == owner['current_interpretation'])
interpretation = corr['current_interpretation']
check('One existing unique design and two image placements with zero new option', interpretation['unique_designs_depicted'] == 1 and interpretation['depicted_display_occurrences'] == 2 and interpretation['is_two_part_complementary_sculpture'] is False and interpretation['existing_individual_option_id'] == 'BSI-6581D83760F1' and interpretation['new_design_or_option_count_increment'] == 0)
check('Physical cast count, image production and native pack quantity not confirmed', all(interpretation[k] is None for k in ['physical_cast_quantity_verified', 'photograph_origin_or_duplication_method_verified', 'native_offer_sale_quantity_confirmed']) and all(corr[k] is False for k in ['native_offer_sale_quantity_verified', 'physical_cast_quantity_verified', 'photo_production_method_verified', 'new_platform_or_physical_match']))
copies = [white, new['source_sets'][10], new['source_offer_edges'][27], new['source_platform_offer_coverage'][27], new['current_listing_source_links']['offers'][27]]
check('All five current entry points contain identical qualified correction', all(x['current_owner_depiction_correction'] == corr for x in copies))
check('O028 current label and relationship use repeated one-design display', new['source_sets'][10]['current_display_name'] == 'Leaf Form — White, repeated wall display' and 'one existing design' in new['source_sets'][10]['relationship_status'] and 'current sale quantity unconfirmed' in new['source_sets'][10]['relationship_status'])
check('O028 native two-part source and600 price remain historical assertions', new['source_offer_edges'][27]['source_offer']['native_parts'] == 2 and new['source_offer_edges'][27]['source_offer']['native_price'] == '600.00' and 'two-part' in new['source_offer_edges'][27]['source_offer']['native_description'])
check('White edge158 does not restate current set quantity as confirmed', 'set quantity remains two' not in ' '.join(new['current_listing_match_evidence']['edges'][158]['special_join_limits']).lower() and 'unconfirmed' in ' '.join(new['current_listing_match_evidence']['edges'][158]['special_join_limits']).lower())

old_cov, new_cov = oa['coverage'][100], na['coverage'][100]
check('Every unrelated photograph coverage record unchanged', all(o == n for o, n in zip(oa['coverage'], na['coverage']) if o['option_id'] != 'BSI-6581D83760F1'))
check('White individual and separate garden photograph records unchanged', old_cov['individual'] == new_cov['individual'] and old_cov['in_situ'] == new_cov['in_situ'])
check('Exact rqDQ Series image/parent/URLs/status and requirement preserved', old_cov['series']['reference'] == new_cov['series']['reference'] and new_cov['series']['reference'] == owner['image_reference'] | {k: v for k, v in old_cov['series']['reference'].items() if k not in owner['image_reference']} and old_cov['series']['status'] == new_cov['series']['status'] == 'Available' and old_cov['series_required'] == new_cov['series_required'])
check('Current Series basis describes same design twice while preserving unknown origin', 'one unique design' in new_cov['series']['basis'].lower() and 'two depicted placements' in new_cov['series']['basis'].lower() and new_cov['scene_origin'] == old_cov['scene_origin'])
role_keys = ['current_options', 'working_component_identities', 'required_actions', 'active_photograph_roles', 'active_in_situ_cases_reviewed', 'active_series_requests', 'held_in_situ_cases', 'held_series_cases', 'technical_individual_gaps', 'new_physical_verifications']
check('All existing photo-count/hold/physical-verification counters unchanged', all(oa['counts'].get(k) == na['counts'].get(k) for k in role_keys))
check('Photo request queue and physical source-audit content untouched', read(D / 'photo-review-queue.json') == read(D / 'inputs/report_reviews.before') and read(D / 'physical-source-audit.json') == read(ROOT / 'components/reconciliation/spiralmoon-workshop-current-folder-refresh-master-2026-10-24/physical-source-audit.json'))

old_assets = read(D / 'inputs/report_assets.before')
new_assets = read(D / 'current-assets.json')
fid = owner['image_reference']['file_id']
changed_assets = [k for k in set(old_assets) | set(new_assets) if old_assets.get(k) != new_assets.get(k)]
changed_fields = [k for k in set(old_assets[fid]) | set(new_assets[fid]) if old_assets[fid].get(k) != new_assets[fid].get(k)]
check('Only exact rqDQ auxiliary asset display_path/folder_path changed', changed_assets == [fid] and set(changed_fields) == {'display_path', 'folder_path'}, {'changed_assets': changed_assets, 'changed_fields': changed_fields})
native = read(D / 'leaf-current-native-metadata.json')['objects']
file_meta = next(x for x in native if x['id'] == fid)
parent_meta = next(x for x in native if x['id'] == owner['image_reference']['folder_id'])
check('Two auxiliary paths equal retained exact-file native readback', new_assets[fid]['display_path'] == file_meta['path_display'] and new_assets[fid]['folder_path'] == 'ns:202238505/' + parent_meta['path_display'])
check('Native reference map has no new objects or identity changes', read(D / 'current-native-reference-map.json') == read(D / 'inputs/native_map.before'))


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.urls.extend(v for k, v in attrs if k == 'href')


page = OUT / 'leaf-form-owner-display.html'
parser = Links()
parser.feed(page.read_text())
check('Current owner report contains exact reviewed image and folder URLs', all(owner['image_reference'][k] in parser.urls for k in ['image_url', 'folder_url']))
with (OUT / 'Owner_Leaf_Form_Depiction_1.csv').open(newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
check('New owner CSV has one existing White option,1 unique design,2 placements', len(rows) == 1 and rows[0]['option_id'] == 'BSI-6581D83760F1' and rows[0]['unique_designs_depicted'] == '1' and rows[0]['depicted_placements'] == '2' and rows[0]['file_id'] == fid)
check('New owner CSV retains exact links and false physical/native quantity flags', all(rows[0][k] == owner['image_reference'][k] for k in ['image_url', 'folder_url', 'folder_id']) and rows[0]['native_pack_quantity_verified'].lower() == 'false' and rows[0]['physical_cast_quantity_verified'].lower() == 'false')
check('Frozen candidate register and audit remained unchanged through readback', sha(REG) == SHA_REG and sha(AUDIT) == SHA_AUDIT)
result = {'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'status': 'PASS' if all(x['passed'] for x in checks) else 'FAIL',
          'checks_passed': sum(x['passed'] for x in checks), 'checks_total': len(checks),
          'candidate_register_sha256': sha(REG), 'candidate_audit_sha256': sha(AUDIT),
          'checks': checks, 'source_seals': [{'path': str(p), 'sha256': s} for p, s in seals],
          'scope': 'Independent frozen JSON, owner CSV and HTML-link readback only. Did not open the pending workbook; no visual-render, live API, binary-image or physical verification.'}
with (HERE / 'data-report-readback-001.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'status': result['status'], 'passed': result['checks_passed'], 'total': len(checks), 'failed': [x for x in checks if not x['passed']]}))
raise SystemExit(0 if result['status'] == 'PASS' else 1)
