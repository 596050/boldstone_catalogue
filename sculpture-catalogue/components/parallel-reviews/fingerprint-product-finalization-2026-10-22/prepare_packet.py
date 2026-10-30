"""Prepare a bounded Fingerprint update for the single catalogue writer."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import html
import json

ROOT = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
JOB = Path(__file__).resolve().parent
OUT = ROOT / 'outputs/fingerprint-product-finalization-2026-10-22'
OUT.mkdir(parents=True, exist_ok=True)
STAMP = datetime.now(timezone.utc).isoformat()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

pointer_path = ROOT / 'current-master.json'
pointer = json.loads(pointer_path.read_text())
register_path = ROOT / pointer['register']
assert sha(register_path) == pointer['register_sha256']
register = json.loads(register_path.read_text())
numbered = register['latest_fingerprint_numbered_reconciliation']['numbered_folder_finish_inventory']
legacy_options = [x for x in register['options'] if x['family'] == 'Fingerprint']
legacy_components = [x for x in register['components'] if x['family'] == 'Fingerprint']
assert len(numbered) == 6 and len(legacy_options) == 4 and len(legacy_components) == 2
save(JOB / 'preparation-pointer.json', pointer)
save(JOB / 'legacy-records-preserved.json', {'components': legacy_components, 'options': legacy_options})
save(JOB / 'numbered-source-records.json', numbered)

owner = {
    'thread_id': '01a13fe6-495b-7253-b923-31823b4cbca8',
    'recorded_utc': STAMP,
    'latest_exact_text': '2. Finalize the product records. Connect Concentric 1–3 and their Cream/White finishes to the product register, using that decision to avoid duplicates.\n3. Complete their specifications. Record dimensions, depth, estimated weight, material, fixing choices, price and availability, keeping estimates labelled. Then refresh the sculpture count and image-gap list.',
    'preceding_exact_text': 'fingerprint is now fine, move on to:\n3. Complete their specifications. Record dimensions, depth, estimated weight, material, fixing choices, price and availability, keeping estimates labelled.',
    'standing_instructions': [
        'All sculptures should have a choice of keyhole fixing/french cleat',
        'The approximate weights are good, for all sculptures, if they do not have estimates, you should estimate them, otherwise accept the approximate',
        'answer affirmative to all questions fo this nature',
    ],
    'interpretation': 'Use the three current owner-numbered designs, each with Cream and White, as the active Fingerprint catalogue. Retain the superseded Left/Right records and source assertions as history without counting four additional current offers. This is a current-record disposition, not proof of exact historical mould or finish equivalence.',
    'exact_legacy_physical_alias_confirmed': False,
    'physical_specification_confirmation': False,
}
save(JOB / 'owner-instruction.json', owner)

fields = {
    'Dimensions / depth': {
        'display': '40 × 40 cm face — working proposal by family analogy. Approximately 3 cm overall relief depth, planning range 2–4 cm — estimate. Current numbered panels have not been measured.',
        'state': 'Working proposal and estimate; not a measured current specification',
        'basis': 'The prior Left Verdigris record contains the owner\'s 40 × 40 face dimension; it is used only as a size proposal for the current square numbered panels. Current original JPEGs show square relief panels but contain no measured scale or depth view. The 3 cm depth is an explicit planning guess, not a measurement from bricks or a transfer of legacy physical identity. The 2 cm average solid material assumption used for weight is distinct from overall relief depth.',
    },
    'Weight': {
        'display': 'Approximately 6 kg per panel; working range 4–9 kg — conditional estimate, not weighed. Excludes packaging and installation hardware.',
        'state': 'Working estimate accepted under the standing weight instruction; not weighed',
        'basis': 'Retains the family\'s accepted approximate 6 kg planning model, conditional on a proposed 40 × 40 cm face and roughly 2 cm average solid mineral-composite material. That previous model used a Jesmonite-like dry density; this is not a claim that the current panels are Jesmonite. Material, backing, relief profile and actual thickness remain unverified. The range is a planning allowance, not a measured or statistical bound.',
    },
    'Material / finish': {
        'display': '{finish} finish — current owner folder label and photographed appearance. Cast plaster/gypsum-based mineral composite — working material guess; binder, reinforcement, coating and formulation unconfirmed.',
        'state': 'Owner-numbered finish label; substrate and coating are working guesses',
        'basis': 'Finish identity follows the current owner-managed Cream/White folder and its verified original JPEG. A cast mineral-composite substrate is a family planning assumption; the photo cannot establish chemical formulation or finish process.',
    },
    'Fixing': {
        'display': 'Choice of keyhole fixing or French cleat — owner instruction. Fitted hardware, attachment details and load rating remain unverified.',
        'state': 'Owner-confirmed offered choice; installed hardware unverified',
        'basis': 'Standing owner instruction applies to all sculptures. The wall-mounted photo does not identify the concealed installed fixing.',
    },
    'Individual price': {
        'display': 'Quote required per individual panel — working pricing policy. No verified numeric single-panel price is available in the checked sources.',
        'state': 'Working quote policy; numeric selling price unconfirmed',
        'basis': 'Existing accepted Fingerprint records use a quote-only policy. The retained trade-price data, local product-price CSV and current source-offer associations provide no supported numeric Fingerprint individual price. No live platform price or tax/delivery treatment is asserted.',
    },
    'Availability': {
        'display': 'Made to order — working proposal for individual supply. Current stock, production capacity and lead time remain unconfirmed.',
        'state': 'Working supply proposal; stock and lead time unconfirmed',
        'basis': 'Current original photographs document the numbered appearance references. The owner has instructed individually purchasable working records. Made-to-order availability is a catalogue proposal, not an inventory or manufacturing-capacity check.',
    },
}

products = []
components = []
for src in numbered:
    number, finish = src['number'], src['finish']
    cid = f'BC-FP-CONCENTRIC-{number}'
    scope = f'FP-CONCENTRIC-{number}-{finish.upper()}'
    key = cid + '|' + scope
    pid = 'BSI-' + hashlib.sha256(key.encode()).hexdigest()[:12].upper()
    specs = {}
    for label, field in fields.items():
        entry = {k: v.format(finish=finish) for k, v in field.items()}
        entry.update({'working_accepted': True, 'physical_verification': False,
                      'acceptance_basis': 'Current owner completion instruction plus standing acceptance of labelled working proposals; no claim of a fresh individual physical-specification approval',
                      'proposal_id': scope + '-' + label.upper().replace(' / ', '-').replace(' ', '_')})
        specs[label] = entry
    products.append({
        'product_id': pid, 'canonical_key': key, 'canonical_component_id': cid,
        'canonical_design_id': cid, 'source_inventory_id': src['inventory_id'],
        'source_scope': scope, 'name': src['name'], 'number': number, 'finish': finish,
        'family': 'Fingerprint', 'subfamily': 'Fingerprint Concentric',
        'sale_unit': 'One Fingerprint Concentric panel in the stated finish',
        'specifications': specs, 'six_working_fields_recorded': True,
        'physical_specifications_verified': False,
        'specification_values': {
            'height_cm': {'value': 40, 'status': 'working proposal'},
            'width_cm': {'value': 40, 'status': 'working proposal'},
            'overall_depth_cm': {'value': 3, 'planning_range': [2, 4], 'status': 'estimate'},
            'weight_kg': {'value': 6, 'planning_range': [4, 9], 'status': 'conditional estimate'},
            'material': {'value': 'Cast plaster/gypsum-based mineral composite', 'status': 'working guess'},
            'fixing_choices': {'value': ['Keyhole fixing', 'French cleat'], 'status': 'owner-instructed offered choices'},
            'price': {'value': None, 'policy': 'Quote required per individual panel', 'status': 'working quote policy'},
            'availability': {'value': 'Made to order', 'status': 'working proposal'},
        },
        'component_folder': src['component_folder'],
        'original_individual_photo': src['original_individual_photo'],
        'original_image_folder': src['original_image_folder'],
        'original_photo_sha256': src['original_photo_sha256'],
        'group_example': src['group_example'],
        'context_photo_ids': src['context_photo_ids'],
        'photo_coverage': {'individual': 'Available', 'in_situ': 'Available', 'series': 'Available'},
        'photo_role_basis': {
            'individual': 'Complete standalone original JPEG of the owner-numbered panel and finish; all edges visible.',
            'in_situ': 'The original standalone JPEG shows the panel mounted against a brick wall. This is staged wall context; concealed hardware and room-scale installation are unverified.',
            'series': 'Verified complete original group JPEG with component membership and rotation recorded in the placement overlay. Group photographs remain context and are not additional products.',
        },
        'isolated_png_provenance': 'Unconfirmed; original JPEG remains the qualified primary reference',
        'current_platform_offer_verified': False,
        'legacy_exact_alias': None,
    })

for number in (1, 2, 3):
    members = [x for x in products if x['number'] == number]
    components.append({'component_id': members[0]['canonical_component_id'],
                       'name': f'Fingerprint Concentric {number}', 'family': 'Fingerprint',
                       'option_ids': [x['product_id'] for x in members],
                       'option_names': [x['name'] for x in members], 'option_count': 2,
                       'physical_stock_quantity': None, 'physical_mould_count': None})

packet = {
    'schema': 'boldstone.fingerprint-current-products.v1', 'recorded_utc': STAMP,
    'status': 'PREPARED_FOR_SINGLE_WRITER_MASTER_INTEGRATION',
    'owner_instruction': owner, 'preparation_baseline': pointer,
    'components': components, 'options': products,
    'legacy_disposition': {
        'component_ids': [x['component_id'] for x in legacy_components],
        'product_ids': [x['product_id'] for x in legacy_options],
        'disposition': 'Archive as superseded current-record history; do not count as four additional active options',
        'exact_old_records_preserved': str(JOB / 'legacy-records-preserved.json'),
        'source_assertions_must_survive': True,
        'exact_physical_alias_or_verdigris_to_cream_equivalence_asserted': False,
        'archive_pending_identity_review': 'Historical comparison may be reopened later if needed; it does not block the owner-selected current three-design/six-finish register.',
    },
    'count_change': {'active_components_removed': 2, 'active_components_added': 3,
                     'active_options_removed': 4, 'active_options_added': 6,
                     'net_component_change': 1, 'net_option_change': 2,
                     'conditional_projected_components_from_preparation_baseline': len(register['components']) + 1,
                     'conditional_projected_options_from_preparation_baseline': len(register['options']) + 2,
                     'count_rule': 'Recalculate from the latest published master after any concurrent Lava Moon update; these are working identities/options, not physical stock or mould counts.'},
    'image_gap_change': {
        'new_options_missing_individual_images': 0,
        'old_option_actions': 'Archive the four old individual capture actions as superseded scope, not as photographs found for those historical Verdigris/White records. Retain already-resolved historical context actions in history.',
        'new_current_role_actions': [],
        'count_rule': 'Recalculate the active image-gap list from current options. Do not retain old excluded offers as active gaps or erase their historical evidence.'},
    'writer_contract': ['Merge only this Fingerprint scope against a freshly checked master pointer.',
                        'Update component/option sheets, specification formulas, counts, native links and current photo coverage together.',
                        'Retain unrelated records, source assertions, old record IDs and their exact prior contents in history.',
                        'Keep all proposed dimensions, estimated depth/weight and material/availability guesses explicitly labelled.',
                        'Do not assert an exact historical alias, a numeric selling price, physical stock, or a live Squarespace/Shopify match.'],
}
save(JOB / 'product-update-packet.json', packet)

esc = html.escape
common_rows = ''.join(f'<tr><th>{esc(k)}</th><td>{esc(v["display"].format(finish="Cream or White"))}</td></tr>' for k, v in fields.items())
cards = []
for x in products:
    pic = x['original_individual_photo']
    image_name = pic['file_id'].split(':', 1)[1] + '.jpeg'
    cards.append(f'<article><h2>{esc(x["name"])}</h2><img alt="{esc(x["name"])}" src="../fingerprint-numbered-master-refresh-2026-10-22/images/{image_name}"><p><a href="{esc(pic["url"], quote=True)}">Original individual photograph</a> · <a href="{esc(x["component_folder"]["url"], quote=True)}">Product folder</a> · <a href="{esc(x["group_example"]["file"]["url"], quote=True)}">Arrangement photograph</a></p><p>Individual, brick-wall context and series images available. Record: {esc(x["product_id"])}.</p></article>')
page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fingerprint Concentric — working product records</title><style>body{font:17px/1.55 system-ui;margin:32px auto;max-width:1150px;padding:0 22px;color:#243735;background:#faf8f3}h1,h2{line-height:1.2}h1{font-size:34px}h2{font-size:23px}table{border-collapse:collapse;width:100%;background:white}th,td{padding:14px;border:1px solid #d8ded6;text-align:left;vertical-align:top}th{width:20%}a{color:#176865}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}article{background:white;padding:20px;border:1px solid #d8ded6;border-radius:8px}img{width:100%;height:auto}.status{background:#e8eee4;padding:15px;border-radius:6px}</style><h1>Fingerprint Concentric</h1><p class="status" id="publication-status">Three current numbered designs, each in Cream and White: six working individual product records. Prepared for master integration; publication verification pending.</p><p>The old Left/Right records remain historical evidence and are excluded from the current-offer count. This does not assert that an old physical cast or Verdigris finish is identical to a current Cream or White panel.</p><p>These common working specifications apply to each of the six records. Estimates are retained as estimates; current measurements, formulation, price and stock have not been physically verified.</p><table><thead><tr><th>Specification</th><th>Working detail</th></tr></thead><tbody>' + common_rows + '</tbody></table><h2>Current records and photographs</h2><div class="grid">' + ''.join(cards) + '</div></html>'
(OUT / 'index.html').write_text(page)

inputs = [register_path, JOB / 'owner-instruction.json', JOB / 'legacy-records-preserved.json',
          JOB / 'numbered-source-records.json', JOB / 'product-update-packet.json',
          Path('/Users/tprice/Documents/boldstone/reports/dropbox-fingerprint-flat-placement-2026-10-22/catalogue-placement-overlay.json'),
          ROOT / 'components/reconciliation/individual-products-2026-10-20/worker-03/quote-only-price-scopes.json']
seal = {'status': 'SEALED', 'recorded_utc': STAMP, 'files': [{'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in inputs]}
save(JOB / 'packet-seal.json', seal)
assert len({x['product_id'] for x in products}) == 6
assert len({x['canonical_component_id'] for x in products}) == 3
assert all(len(x['specifications']) == 6 for x in products)
assert not ({x['product_id'] for x in products} & {x['product_id'] for x in register['options']})
assert all((ROOT / 'outputs/fingerprint-numbered-master-refresh-2026-10-22/images' / (x['original_individual_photo']['file_id'].split(':', 1)[1] + '.jpeg')).exists() for x in products)
print(json.dumps({'packet': str(JOB / 'product-update-packet.json'), 'packet_sha256': sha(JOB / 'product-update-packet.json'), 'seal_sha256': sha(JOB / 'packet-seal.json'), 'components': len(components), 'options': len(products), 'working_fields': sum(len(x['specifications']) for x in products), 'new_individual_image_gaps': 0, 'report': str(OUT / 'index.html')}, indent=2))
