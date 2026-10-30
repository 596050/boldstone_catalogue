#!/usr/bin/env python3
"""Prepare a keyed, qualified local catalogue and non-executable import bundle."""
from __future__ import annotations

import copy
import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path('/Users/tprice/Documents/boldstone')
CAT = ROOT / 'sculpture-catalogue'
WORK = Path(__file__).resolve().parent
OUT = CAT / 'outputs/01a13fe6-495b-7253-b923-31823b4cbca8/matched-listing-2026-10-25'
REGISTER = CAT / 'components/reconciliation/coral-depth-wording-master-2026-10-25/canonical-master-register.json'
CROSSWALK = ROOT / 'reports/local-platform-crosswalk-corrected-20261024-root/local-platform-crosswalk.json'
FINDINGS = CAT / 'components/parallel-reviews/specification-double-check-after-depth-20261025T013835Z-B/findings.json'
CASES65 = CAT / 'components/parallel-reviews/all-record-image-matching-20261024-B/published-projections/20261025T014714043538Z/source-association-review/all-65-case-dispositions.json'
OVERLAPS = CAT / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/OVERLAP_PROPOSALS.json'
GALLERY = CAT / 'components/parallel-reviews/all-record-image-matching-20261024-B/published-projections/20261025T014714043538Z'
FIELDS = ['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability']
STAMP = datetime.now(timezone.utc).isoformat()


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def digest(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def write(p, v):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')


def csvwrite(p, rows):
    with Path(p).open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for row in rows:
            safe = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in row.items()}
            assert not any(isinstance(v, str) and v.startswith(('=', '+', '@', '\t', '\r')) for v in safe.values())
            w.writerow(safe)


def plain(s):
    return re.sub(r'\s+', ' ', str(s).replace('**', '')).strip()


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def url_link(u, label):
    return '<a href="' + html.escape(u, quote=True) + '">' + html.escape(label) + '</a>' if u else ''


def source_ref(p):
    return {'path': str(p), 'sha256': sha(p)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    base = read(REGISTER)
    pointer = read(CAT / 'current-master.json')
    assert pointer['status'] == 'CURRENT_MASTER188_CORAL_ACCEPTANCE_WORDING_ALIGNED', 'Publisher changed baseline; reconcile first.'
    active = set(base['active_option_ids'])
    before_options = {o['product_id']: o for o in base['options'] if o['product_id'] in active}
    assert len(before_options) == 188
    options = copy.deepcopy(before_options)
    cases65 = {r['product_id']: r for r in read(CASES65)}
    findings = read(FINDINGS)['missing_working_specifications']
    crosswalk = read(CROSSWALK)
    ss = {r['offer_ref']: r for r in crosswalk['squarespace_source_records']}
    source_offers = {r['offer_ref']: r['source_offer'] for r in base['source_offer_edges']}
    source_edges = base['current_listing_match_evidence']['edges']
    edges_by_option = defaultdict(list)
    for e in source_edges:
        if e['product_id'] in active:
            edges_by_option[e['product_id']].append(e)
    group_map = {pid: g['working_design_group_id'] for g in base['current_working_design_group_projection']['groups'] for pid in g['active_option_ids']}
    for pid, o in options.items():
        if pid not in group_map:
            assert o.get('option_family_id') == 'BC-WALL-CIRCLE'
            group_map[pid] = o['option_family_id']

    sources = [REGISTER, CROSSWALK, FINDINGS, CASES65, OVERLAPS, GALLERY / 'per-product-image-lists.json']
    manifest = {'prepared_utc': STAMP, 'baseline_pointer': source_ref(CAT / 'current-master.json'),
                'inputs': [source_ref(p) for p in sources], 'current_live_platform_verification': False,
                'source_scope': 'Current local canonical catalogue plus dated local Squarespace/Shopify evidence.'}
    write(WORK / 'input-manifest.json', manifest)

    changes = []
    material_ids = {x['option_id'] for x in findings['base_material_options']}
    for pid in sorted(material_ids):
        o = options[pid]
        before = copy.deepcopy(o['master_fields']['Material / finish'])
        if o['family'] in ('Lava Moon', 'Moonphases') or o['name'].startswith('Knightsbridge Fountain'):
            proposed = 'Jesmonite AC730'
            analogy = 'Related Moonphase maker-standard and accepted water-feature working records name Jesmonite AC730. Using that material here is a new working proposal, not proof that the photographed item uses it.'
        else:
            proposed = 'Plaster/gypsum composite'
            analogy = 'A plaster/gypsum composite is a working construction proposal consistent with other approved cast-relief entries. Finish appearance alone does not establish this substrate.'
        after = copy.deepcopy(before)
        after['display'] = proposed + ' — proposed base material (guess; not verified). Retained finish evidence: ' + plain(before['display'])
        after['state'] = 'Working base-material proposal under the owner instruction to complete missing specifications; not individually confirmed or physically verified. Prior finish qualifications retained.'
        after['basis'] = (before.get('basis', '') + '\n25 October 2026 completion proposal: ' + analogy + ' No recipe, reinforcement, water sealing, outdoor suitability or fire classification is inferred.').strip()
        after['working_recorded'] = 1
        after['physical_verification'] = 0
        after['prior_display'] = before['display']
        after['proposal_ids'] = list(dict.fromkeys(before.get('proposal_ids', []) + [pid + ':BASE-MATERIAL-PROPOSAL:20261025']))
        after['completion_proposal'] = {'base_material': proposed, 'basis_type': 'ANALOGY_WORKING_PROPOSAL', 'maker_confirmed': False, 'owner_confirmed_specific_value': False}
        o['master_fields']['Material / finish'] = after
        changes.append({'product_id': pid, 'name': o['name'], 'field': 'Material / finish', 'before': before, 'after': after,
                        'basis_type': 'Working material proposal', 'range': None, 'physical_verification_added': False,
                        'image_url': o['image_url'], 'folder_url': o['folder_url']})

    size_proposals = {
        'BSI-65A93033A200': {'height_cm': 35, 'width_cm': 35, 'face_range_cm': [33, 40], 'depth_cm': 6, 'depth_range_cm': [5, 8],
                           'basis': 'The existing 30 cm core and 35 cm outer weight-model reference, with the square bordered depiction inspected on 25 October. The old model assumption is now explicitly proposed as a working overall size; it is not promoted to a maker measurement.'},
        'BSI-4515726BBC18': {'height_cm': 35, 'width_cm': 35, 'face_range_cm': [33, 40], 'depth_cm': 6, 'depth_range_cm': [5, 8],
                           'basis': 'The existing 30 cm core and 35 cm outer weight-model reference, with the square bordered depiction inspected on 25 October. The old model assumption is now explicitly proposed as a working overall size; it is not promoted to a maker measurement.'},
        'BSI-3C849B547D50': {'height_cm': 100, 'width_cm': 16, 'height_range_cm': [80, 120], 'width_range_cm': [14, 20], 'depth_cm': 3, 'depth_range_cm': [2, 5],
                           'basis': 'The inspected panel has an approximately six-to-one tall/narrow face. 100 × 16 cm is a low-confidence working size selected at the scale of the historical shipping record. Shipping values remain shipping evidence, and the photograph has no calibrated scale; this is an explicit new estimate, not a measured artwork dimension.'}
    }
    assert set(size_proposals) == {x['option_id'] for x in findings['face_size_options']}
    for pid, proposal in size_proposals.items():
        o = options[pid]
        before = copy.deepcopy(o['master_fields']['Dimensions / depth'])
        after = copy.deepcopy(before)
        if pid == 'BSI-3C849B547D50':
            display = 'Approximately 100 cm high × 16 cm wide — low-confidence working face-size estimate; plausible working ranges 80–120 cm high and 14–20 cm wide. Overall sculpture-body depth approximately 3 cm, range 2–5 cm — existing estimate retained. Artwork unmeasured; historical 100 × 16 × 4 cm shipping fields remain shipping evidence only.'
        else:
            display = 'Approximately 35 × 35 cm overall, including border — working face-size estimate; plausible working range 33–40 cm on each side. Overall sculpture-body depth approximately 6 cm, range 5–8 cm — existing estimate retained. Historical core reference approximately 30 × 30 cm; actual bordered panel unmeasured.'
        after.update(display=display, state='Working face-size estimate under the owner instruction to complete missing specifications; not individually confirmed or physically measured. Existing depth estimate retained.',
                     basis=(before.get('basis', '') + '\n25 October 2026 face-size proposal: ' + proposal['basis']).strip(),
                     prior_display=before['display'], working_recorded=1, physical_verification=0)
        after['proposal_ids'] = list(dict.fromkeys(before.get('proposal_ids', []) + [pid + ':FACE-SIZE-ESTIMATE:20261025']))
        after['completion_proposal'] = proposal | {'owner_confirmed_specific_value': False, 'measurement': False}
        o['master_fields']['Dimensions / depth'] = after
        changes.append({'product_id': pid, 'name': o['name'], 'field': 'Dimensions / depth', 'before': before, 'after': after,
                        'basis_type': 'Working face-size estimate', 'range': proposal,
                        'physical_verification_added': False, 'image_url': o['image_url'], 'folder_url': o['folder_url']})
    write(WORK / 'specification-completion-packet.json', {'schema': 'boldstone.scoped-working-specification-completion.v1',
          'baseline_register': source_ref(REGISTER), 'authority': 'Owner requested these 27 materials and three face sizes be completed, retaining labelled estimates; standing instruction permits clearly labelled guesses.',
          'changes': changes, 'changed_field_count': 30, 'unchanged_active_field_count': 1098,
          'new_physical_verifications': 0, 'estimates_are_not_measurements': True})

    # Historical duplicate/version decisions choose one source for an import row.
    preferred = {
        'BSI-947F365275C5': 'O067', 'BSI-59530C6155C2': 'O004', 'BSI-09C1A55D460D': 'O038',
        'BSI-70C7029C1DB1': 'O059', 'BSI-0922347CC6AE': 'O002', 'BSI-1AF0A83FAA37': 'O003',
        'BSI-46F6DB226213': 'O006'
    }
    overlap_cases = read(OVERLAPS)['proposals']
    supported = {}
    for pid, o in options.items():
        resolution = o.get('current_listing_resolution', {})
        if not resolution.get('source_supported_individual_record_present'):
            continue
        candidates = []
        for platform, detail in o.get('current_listing_reconciliation', {}).get('platforms', {}).items():
            if platform == 'Squarespace':
                candidates.extend(v['offer_ref'] for v in detail.get('supported_individual_native_variants', []))
        candidates.extend(v['offer_ref'] for v in resolution.get('new_supported_source_matches', []) if v.get('platform') == 'Squarespace')
        candidates = list(dict.fromkeys(candidates))
        ref = preferred.get(pid) or (candidates[0] if len(candidates) == 1 else None)
        assert ref and ref in candidates and ref in ss, (pid, candidates)
        assert source_offers[ref]['sale_unit_state'] == 'Sale component', (pid, ref)
        supported[pid] = ref
    assert len(supported) == 47

    # Four pattern correspondences were visually rechecked; assign only a working
    # logical pattern/size/lighting tuple. Physical cast and recipe remain unverified.
    patterns = {
        'BSI-C87B4CF945C7': ('Cracked Malachite', 'review-image.png', '769e704d7d8a8df84ca82a94bcc5c2b6b2d353f8c117768098b1bff6130a7693.webp'),
        'BSI-67B24409A253': ('Tropical Shards', 'wc-02-turquoise-marbled/review-image.png', 'b3e3b456de50da69288574f82918d785b6853bbf0891cd52d6fe0c60e9167bd0.webp'),
        'BSI-D5A939264C82': ('Terra Cotta Shatter', str(ROOT / 'reports/dropbox-wall-circle-finish-names-review-2026-10-23/originals/wall-circle__wall-circle-marbled-4__019.png'), 'b4428e09ec2e6da99e61786690c40f2357ca64cd838931aba3ce1f500380453f.webp'),
        'BSI-65520F070145': ('Ochre Veins', str(ROOT / 'reports/dropbox-wall-circle-finish-names-review-2026-10-23/originals/wall-circle__wall-circle-yellow-and-grey-pattern-studies__012.webp'), '5a00bfe8fb27eac13f3b53dcd047cd16408807910a5c248fadd86c6cc54256a3.webp')
    }
    pattern_reviews = []
    wp = CAT / 'components/parallel-reviews/wall-circle-2026-10-17'
    for pid, (pattern, visual, swatch) in patterns.items():
        t = options[pid]['current_listing_resolution']['conditional_native_tuple']
        original = next(v for v in base['wall_circle_native_options'] if v['variant_id'] == t['native_variant_id'])
        assert original['sku'] == t['sku']
        assert original['attributes']['Diameter Size'] == t['diameter_option'] == '50cm/19.7in'
        assert original['attributes']['Lighting'] == t['lighting_option'] == 'RGB Color Light'
        assert original['attributes']['Pattern'] == t['pattern']
        imagepath = Path(visual) if Path(visual).is_absolute() else wp / visual
        swatchpath = wp / 'family-keep/native-pattern-images' / swatch
        pattern_reviews.append({'product_id': pid, 'name': options[pid]['name'], 'pattern': pattern,
              'image': source_ref(imagepath), 'native_swatch': source_ref(swatchpath), 'native_tuple': t,
              'review': 'The depicted colour distribution and broken-vein marbling correspond to this named swatch. Circular reference and rectangular swatch inspected side by side.',
              'scope': 'Working logical pattern mapping to the recorded 50 cm / RGB tuple. Not exact-byte, same-cast, installed-lighting, formulation or measured-size certification.',
              'classification': 'REVIEWER_SUPPORTED_WORKING_PATTERN_MAPPING', 'prior_conditional_mapping_preserved': True})
    write(WORK / 'wall-circle-working-mappings.json', {'reviewed_utc': STAMP, 'entries': pattern_reviews})

    related_sibling = defaultdict(list)
    for pid, ref in supported.items():
        related_sibling[options[pid]['canonical_component_id']].append((pid, ref))

    treatments, rows, media, audits = [], [], [], []
    native_assignments = defaultdict(list)
    for pid, o in options.items():
        prior = before_options[pid]
        rec = o.get('current_listing_reconciliation', {})
        res = o.get('current_listing_resolution', {})
        refs = sorted(set(o.get('related_platform_offer_refs', [])) | {e['offer_ref'] for e in edges_by_option[pid]})
        ref = supported.get(pid)
        ssid = ssvid = sku = sh_handle = ''
        target_parent = ''
        reason = ''
        caveats = []
        status = 'LOCAL_WORKING_LISTING_COMPLETE; NATIVE_EXECUTION_NOT_PERFORMED'
        if ref:
            t = ss[ref]['squarespace_native_tuple']
            ssid, ssvid, sku = t['native_product_id'], t['native_variant_id'], t.get('sku_raw', '')
            sh = ss[ref].get('shopify_local_product') or {}
            shv = ss[ref].get('shopify_local_variant') or {}
            sh_handle = sh.get('handle', '')
            if sh_handle:
                assert shv.get('sku_raw', '').strip() == sku.strip(), (pid, ref, 'Shopify SKU mismatch')
                assert ss[ref]['retained_source_offer']['sale_unit_state'] == 'Sale component'
            action = 'REUSE_EXISTING_INDIVIDUAL_RECORD'
            reason = 'Retain the supported single-sculpture source record and identifiers. Use the current approved/qualified specifications in the local listing; do not inherit set prices or source stock.'
            if res.get('correction_case_id') or res.get('current_source_resolution_disposition') == 'EXISTING_RECORD_WORKING_COPY_CORRECTION_PREPARED':
                action = 'UPDATE_EXISTING_INDIVIDUAL_RECORD_COPY'
                caveats.append('Existing copy differs from the working specification; update draft text while preserving native IDs and legacy source assertions.')
            for case in overlap_cases:
                if pid in case.get('existing_canonical_product_ids', []):
                    caveats.append(case['case_id'] + ': ' + case['canonical_alias_proposal'].get('recommended_mapping_correction', case['conclusion']))
            # Historical Shopify O038/O039/O015 never become exact matches to a
            # different selected Squarespace offer by family or title alone.
            native_assignments['Squarespace:' + ssvid].append(pid)
            if sh_handle:
                native_assignments['Shopify:' + sh_handle + ':' + (shv.get('variant_key') or sku)].append(pid)
        elif pid in patterns:
            t = res['conditional_native_tuple']
            ref = 'O001'
            ssid, ssvid, sku = t['native_product_id'], t['native_variant_id'], t['sku']
            action = 'REUSE_RECORDED_PATTERN_VARIANT_WORKING_MAPPING'
            reason = 'Visual pattern review supports ' + t['pattern_short_name'] + '; the saved native tuple explicitly selects 50 cm and RGB. Keep the owner display name as an alias and retain all source price/material qualifications.'
            caveats.append('Working pattern mapping, not an exact photograph/cast match. No claim about the current live variant or installed lighting.')
            native_assignments['Squarespace:' + ssvid].append(pid)
        elif o['family'] == 'Wall Circle':
            action = 'ADD_NAMED_PATTERN_VARIANT'
            target_parent = '68dc0a35a7ac865209b39248'
            reason = 'Add the owner-named pattern as a distinct 50 cm / RGB option in the Wall Circle family. No exact existing named pattern is supported in the saved native options.'
        elif pid == 'BSI-04D6E8690F30':
            action = 'RETAIN_LEGACY_REFERENCE_NO_DUPLICATE_CREATION'
            reason = 'FFL1 and FFS2 share the owner-confirmed relief and current 70 × 15 cm face. Retain this legacy catalogue row and its own evidence, price and specifications. Do not create a second indistinguishable White SKU without evidence of a separate offered build.'
            caveats.append('A shared design is not authority to merge commercial/specification fields. The FFS2 White row supplies the new White offer draft; this legacy row remains separately auditable.')
            status = 'LOCAL_REFERENCE_COMPLETE; ADDITIONAL_NATIVE_VARIANT_HELD_TO_AVOID_DUPLICATION'
        elif pid == 'BSI-EBD43DF0704F':
            action = 'RETAIN_EXISTING_CANDIDATE_PENDING_EXACT_BINDING'
            target_parent = ss['O007']['squarespace_native_tuple']['native_product_id']
            reason = 'O007 is a single 25 × 25 × 6 cm verdigris/copper relief candidate. Exact binding to the selected Verdigris and Rust reference remains unestablished. Keep the candidate and completed local listing together; create or overwrite neither blindly.'
            status = 'LOCAL_LISTING_COMPLETE; EXACT_EXISTING_CANDIDATE_BINDING_UNRESOLVED'
        elif 'water feature' in o['name'].lower() or o['name'].startswith('Knightsbridge Fountain'):
            action = 'CREATE_SEPARATE_WATER_FEATURE_PRODUCT'
            reason = 'Separate water-feature build as instructed; retain design/family links without inheriting an ordinary wall-panel SKU or claiming plumbing/sealing specifications.'
        elif related_sibling.get(o['canonical_component_id']):
            candidates = sorted(related_sibling[o['canonical_component_id']])
            parent_pid, parent_ref = candidates[0]
            action = 'ADD_DISTINCT_FINISH_OR_BUILD_VARIANT'
            target_parent = ss[parent_ref]['squarespace_native_tuple']['native_product_id']
            reason = 'An existing individual product supports this same canonical component design (' + options[parent_pid]['name'] + '). Add this distinct finish/size/build option, retaining its own image, price and specification. Parent copy may need broadening to a design-level title.'
        elif rec.get('overall_disposition') == 'SET_OR_ARRANGEMENT_ASSOCIATION_ONLY':
            action = 'CREATE_INDIVIDUAL_PRODUCT_LINKED_TO_ARRANGEMENT'
            reason = 'Existing source sells an arrangement. Create the separately purchasable component and keep the set relationship; do not reuse the whole-set variant ID, SKU, dimensions or price.'
        else:
            action = 'CREATE_INDIVIDUAL_PRODUCT_IN_LOCAL_PLAN'
            reason = 'No supported exact individual sale record in the checked local evidence. Prepare a separate individual product, retaining its design/family and photograph links. Historical non-match does not prove absence from the current account.'

        fields = o['master_fields']
        sales = o['selling_details']
        old_sources = [source_offers[x] for x in refs if x in source_offers]
        dimension_claims = [e.get('compatibility', {}).get('size', {}) for e in edges_by_option[pid] if e['offer_ref'] == ref]
        source_dimensions = [x for d in dimension_claims for x in d.get('source_dimension_claims', [])]
        source_material = source_offers.get(ref or '', {}).get('native_description', '')
        proposed_sku = sku if sku else ('BOLD-' + pid.removeprefix('BSI-') if 'NO_DUPLICATE' not in action and 'PENDING_EXACT' not in action else '')
        proposed_handle = urlparse(source_offers[ref]['source_url']).path.rsplit('/', 1)[-1] if ref and ref in source_offers else 'boldstone-' + slug(o['name']) + '-' + pid[-6:].lower()
        matched_source_refs = [ref] if ref else []
        reference = {k: o.get(k, '') for k in ['file_id', 'folder_id', 'image_url', 'folder_url']}
        if o['photo_coverage']['individual'] == 'Shared design reference':
            reference = {k: o['owner_confirmed_design_reference'][k] for k in reference}
        current_context = o['photo_coverage']['in_situ'] == 'Available'
        product_reader = str(GALLERY / 'products' / (pid + '.html'))
        assert Path(product_reader).exists()
        source_offer = source_offers.get(ref or '', {})
        native_description = source_offer.get('native_description', '')
        field_reviews = {f: {'current_display': fields[f]['display'], 'qualification': fields[f]['state'],
                            'source_equality_claimed': False, 'physical_verification': False} for f in FIELDS}
        field_reviews['Dimensions / depth']['retained_source_size_comparisons'] = dimension_claims
        field_reviews['Material / finish']['new_working_material_proposal'] = pid in material_ids
        field_reviews['Individual price']['current_working_numeric_gbp'] = sales['estimated_price']
        field_reviews['Individual price']['source_amount_raw'] = source_offer.get('native_price')
        field_reviews['Individual price']['source_currency_raw'] = source_offer.get('native_currency')
        field_reviews['Availability']['current_lead_time_weeks'] = [sales['lead_time_min_weeks'], sales['lead_time_max_weeks']]
        field_reviews['Availability']['retained_source_stock_setting'] = source_offer.get('stock')
        field_reviews['Availability']['stock_setting_is_not_manufactured_inventory'] = True
        field_reviews['Fixing']['choice'] = ['Keyhole fixing', 'French cleat']
        field_reviews['Fixing']['existing_installed_hardware_certified'] = False
        treatment = {
            'product_id': pid, 'name': o['name'], 'canonical_component_id': o['canonical_component_id'],
            'working_design_group_id': group_map[pid], 'family': o['family'],
            'group_scope': 'OPTION_FAMILY_NOT_CERTIFIED_DESIGN_COUNT' if o.get('option_family_id') else 'WORKING_COMPONENT_DESIGN_GROUP',
            'historical_queue': '65_WITHOUT_DIRECT_SOURCE_EDGE' if pid in cases65 else '123_WITH_SOURCE_ASSOCIATION',
            'listing_treatment': action, 'reason': reason, 'status': status,
            'selected_source_offer_refs': matched_source_refs, 'related_source_offer_refs': refs,
            'selected_squarespace_product_id': ssid, 'selected_squarespace_variant_id': ssvid,
            'suggested_existing_parent_product_id': target_parent,
            'selected_existing_source_sku': sku, 'proposed_listing_sku': proposed_sku,
            'proposed_sku_state': 'RETAIN_EXISTING_SOURCE_SKU' if sku else ('LOCAL_NEW_SKU_PROPOSAL' if proposed_sku else 'NO_NEW_SKU_PENDING_BINDING'),
            'selected_local_shopify_handle': sh_handle, 'shopify_numeric_product_id': None, 'shopify_numeric_variant_id': None,
            'shopify_match_scope': 'EXACT_LOCAL_SOURCE_SKU_AND_SINGLE_UNIT_LINK; HISTORICAL_CONFIG_QUALIFIED' if sh_handle else 'NO_EXACT_INDIVIDUAL_LOCAL_SHOPIFY_ASSIGNMENT',
            'proposed_handle': proposed_handle, 'accepted_working_fields': fields,
            'selected_image': reference | {'role': o['photo_coverage']['individual'], 'is_separate_primary': bool(o.get('file_id'))},
            'all_images_review': product_reader,
            'confirmed_arrangement_ids': o.get('confirmed_arrangement_ids', []),
            'retained_names': o.get('retained_names', []),
            'retained_configuration_qualifications': caveats,
            'current_field_review': field_reviews,
            'selected_source_description_retained': native_description,
            'verification': {'current_option_name_used': True, 'all_six_fields_checked': all(fields.get(f, {}).get('display') for f in FIELDS),
                             'selected_source_sale_unit_checked': bool(ref), 'local_native_id_readback': bool(ssvid),
                             'current_live_account_verified': False, 'physical_specifications_verified': False,
                             'prior_photography_holds_reopened': False},
            'native_execution_allowed': False
        }
        treatments.append(treatment)
        description_fields = [('Dimensions and depth', fields['Dimensions / depth']['display']), ('Approximate weight', fields['Weight']['display']),
                              ('Material and finish', fields['Material / finish']['display']), ('Fixing choices', fields['Fixing']['display']),
                              ('Individual price', fields['Individual price']['display']), ('Availability', fields['Availability']['display'])]
        description = '<p>' + html.escape(o['name']) + '. One individually offered sculpture or panel.</p><dl>' + ''.join('<dt>' + html.escape(k) + '</dt><dd>' + html.escape(plain(v)) + '</dd>' for k, v in description_fields) + '</dl>'
        rows.append({
            'catalogue_option_id': pid, 'product_name': o['name'], 'family': o['family'], 'working_design_group_id': group_map[pid],
            'canonical_component_id': o['canonical_component_id'], 'sale_unit': o['sale_unit'],
            'dimensions_and_depth': plain(fields['Dimensions / depth']['display']), 'dimensions_status': plain(fields['Dimensions / depth']['state']),
            'weight': plain(fields['Weight']['display']), 'weight_status': plain(fields['Weight']['state']),
            'material_and_finish': plain(fields['Material / finish']['display']), 'material_status': plain(fields['Material / finish']['state']),
            'fixing_choices': 'Keyhole fixing or French cleat', 'fixing_detail': plain(fields['Fixing']['display']),
            'individual_price_gbp': sales['estimated_price'], 'price_upper_gbp': sales.get('estimated_price_upper'), 'price_status': sales['price_status'],
            'price_display': plain(fields['Individual price']['display']), 'availability': sales['availability'],
            'lead_time_min_weeks': sales['lead_time_min_weeks'], 'lead_time_max_weeks': sales['lead_time_max_weeks'],
            'availability_detail': plain(fields['Availability']['display']),
            'image_url': reference['image_url'], 'folder_url': reference['folder_url'], 'image_file_id': reference['file_id'], 'folder_id': reference['folder_id'],
            'individual_image_role': o['photo_coverage']['individual'], 'installation_image_status': o['photo_coverage']['in_situ'], 'series_image_status': o['photo_coverage']['series'],
            'installation_image_url': o.get('context_image_url', '') if current_context else '', 'installation_folder_url': o.get('context_folder_url', '') if current_context else '',
            'all_images_review': product_reader,
            'listing_treatment': action, 'listing_treatment_reason': reason, 'listing_status': status,
            'selected_source_offer_ref': ref or '', 'related_source_offer_refs': '; '.join(refs),
            'squarespace_product_id': ssid, 'squarespace_variant_id': ssvid, 'suggested_existing_parent_product_id': target_parent,
            'existing_source_sku': sku, 'proposed_listing_sku': proposed_sku, 'sku_state': treatment['proposed_sku_state'],
            'local_shopify_handle': sh_handle, 'shopify_numeric_product_id': '', 'shopify_numeric_variant_id': '',
            'proposed_handle': proposed_handle, 'aliases': '; '.join(o.get('retained_names', [])), 'arrangement_ids': '; '.join(o.get('confirmed_arrangement_ids', [])),
            'source_and_configuration_notes': '\n'.join(caveats), 'physical_verification': False, 'native_execution_allowed': False,
            'listing_description_html': description
        })
        media.append({'catalogue_option_id': pid, 'product_name': o['name'], 'role': 'selected_primary_reference' if o.get('file_id') else 'owner_confirmed_shared_design_reference',
                      'image_role_qualification': o['photo_coverage']['individual'], **reference, 'native_variant_image_assignment_verified': False,
                      'importable_public_binary_url': '', 'media_delivery_state': 'DROPBOX_REVIEW_REFERENCE; NOT_AN_ASSUMED_PUBLIC_BINARY_URL'})
        for e in edges_by_option[pid]:
            c = e.get('compatibility', {})
            audits.append({'product_id': pid, 'name': o['name'], 'offer_ref': e['offer_ref'],
                           'retained_relationship': e['relationship'], 'selected_for_individual_listing': e['offer_ref'] == ref,
                           'recorded_sale_unit_state': c.get('sale_unit', {}).get('state'),
                           'design_scope': c.get('design', {}).get('state'), 'finish_scope': c.get('finish', {}).get('state'),
                           'size_comparison': c.get('size', {}).get('state'), 'current_working_dimensions': fields['Dimensions / depth']['display'],
                           'old_dimension_comparison_retained_as_dated_evidence': c.get('size', {}).get('option_working_dimensions'),
                           'build_scope': c.get('build', {}).get('state'), 'image_binding': e.get('media_evidence'),
                           'source_id': source_offers.get(e['offer_ref'], {}).get('sq_id', ''),
                           'source_sku': source_offers.get(e['offer_ref'], {}).get('sku', ''),
                           'retained_source_qualifications': e.get('special_join_limits', []) + e.get('source_match_flags_retained', []),
                           'local_review_result': 'Use only at the selected scope; do not promote related family/arrangement links to exact individual variants.'})

    # Make the creation plan explicit at product/variant level. A new component
    # with Cream and White options becomes one proposed product with two variants.
    new_product_groups = defaultdict(list)
    for t, row in zip(treatments, rows):
        action = t['listing_treatment']
        if action.startswith('CREATE_'):
            suffix = ':WATER' if action == 'CREATE_SEPARATE_WATER_FEATURE_PRODUCT' else ':SCULPTURE'
            group_key = 'NEW:' + (t['canonical_component_id'] or t['product_id']) + suffix
            new_product_groups[group_key].append(t['product_id'])
        elif t['suggested_existing_parent_product_id']:
            group_key = 'EXISTING:' + t['suggested_existing_parent_product_id']
        elif t['selected_squarespace_product_id']:
            group_key = 'EXISTING:' + t['selected_squarespace_product_id']
        else:
            group_key = 'REFERENCE:' + t['product_id']
        t['proposed_product_group_key'] = row['proposed_product_group_key'] = group_key
        t['variant_label'] = row['variant_label'] = row['product_name']
        t['product_creation_role'] = row['product_creation_role'] = 'Existing product, proposed variant or reference'
    for key, pids in new_product_groups.items():
        ordered = sorted(pids)
        for t, row in zip(treatments, rows):
            if t['product_id'] in pids:
                value = 'Create product and first variant' if t['product_id'] == ordered[0] else 'Add variant to the same proposed product'
                t['product_creation_role'] = row['product_creation_role'] = value

    all_media = []
    image_lists = read(GALLERY / 'per-product-image-lists.json')
    for pid, images in image_lists.items():
        for a in images:
            all_media.append({'catalogue_option_id': pid, 'product_name': options[pid]['name'], 'file_id': a['file_id'],
                              'filename': a['name'], 'visual_role': a['visual_role'], 'image_url': a['image_url'], 'folder_url': a['folder_url'],
                              'native_status': a['native_status'], 'association_statuses': '; '.join(a['association_statuses']),
                              'intended_uses': '; '.join(sorted({x['intended_use'] for x in a['evidence']})),
                              'public_binary_import_url': '', 'native_variant_image_assignment_verified': False})
    assert len(all_media) == 10847
    collisions = {k: v for k, v in native_assignments.items() if len(v) > 1}
    assert not collisions, collisions
    assert len(rows) == len(treatments) == len(media) == 188
    assert len({r['catalogue_option_id'] for r in rows}) == 188
    assert sum(t['historical_queue'].startswith('65_') for t in treatments) == 65
    assert all(r['individual_price_gbp'] > 0 for r in rows)
    assert all(r['lead_time_min_weeks'] > 0 and r['lead_time_max_weeks'] >= r['lead_time_min_weeks'] for r in rows)
    assert sum(r['lead_time_max_weeks'] == 1 for r in rows) == 1
    assert all(o['master_fields']['Fixing'] == before_options[pid]['master_fields']['Fixing'] for pid, o in options.items())
    assert all(o['master_fields']['Weight'] == before_options[pid]['master_fields']['Weight'] for pid, o in options.items())
    assert all(o['master_fields']['Individual price'] == before_options[pid]['master_fields']['Individual price'] for pid, o in options.items())
    changed = [(pid, f) for pid in active for f in FIELDS if options[pid]['master_fields'][f] != before_options[pid]['master_fields'][f]]
    assert len(changed) == 30
    summary = {
        'created_utc': STAMP, 'active_option_count': 188, 'working_design_groups': len(base['current_working_design_group_projection']['groups']),
        'additional_option_families': 1,
        'working_specification_fields': 1128, 'base_material_proposals_added': 27, 'face_size_estimates_added': 3,
        'remaining_blank_working_materials': 0, 'remaining_blank_working_face_sizes': 0,
        'new_physically_verified_specifications': 0, 'source_supported_existing_individual_options': 47,
        'additional_working_wall_pattern_mappings': 4,
        'listing_treatments': dict(Counter(t['listing_treatment'] for t in treatments)),
        'historical_65_dispositions': dict(Counter(t['listing_treatment'] for t in treatments if t['product_id'] in cases65)),
        'historical_123_dispositions': dict(Counter(t['listing_treatment'] for t in treatments if t['product_id'] not in cases65)),
        'source_match_edges_reviewed': len(audits), 'existing_native_assignment_collisions': collisions,
        'new_proposed_product_groups': len(new_product_groups),
        'new_product_option_rows': sum(map(len, new_product_groups.values())),
        'all_qualified_option_image_associations': len(all_media),
        'selected_local_shopify_single_unit_links': sum(bool(t['selected_local_shopify_handle']) for t in treatments),
        'primary_references': dict(Counter(r['individual_image_role'] for r in rows)),
        'owner_held_installation_gaps': 22, 'owner_held_series_gaps': 1,
        'exact_native_binding_exceptions': [t['product_id'] for t in treatments if t['listing_treatment'] in ('RETAIN_LEGACY_REFERENCE_NO_DUPLICATE_CREATION', 'RETAIN_EXISTING_CANDIDATE_PENDING_EXACT_BINDING')],
        'platform_writes': 0, 'public_binary_media_urls_created': 0,
        'import_scope': 'Complete neutral working catalogue CSV. Platform-specific write/import payloads are not executable without current-account identity/media readback and release of existing write holds.'
    }
    write(WORK / 'listing-treatment-register.json', {'schema': 'boldstone.all-option-listing-treatment.v1', 'baseline': manifest, 'summary': summary, 'options': treatments})
    write(WORK / 'all-source-association-audit.json', {'options_reviewed': 188, 'entries': audits, 'legacy_source_edges_unchanged': True})
    write(WORK / 'prepared-working-options.json', {'options': list(options.values()), 'parent_register': source_ref(REGISTER)})
    write(WORK / 'summary.json', summary)
    write(OUT / 'listing-data.json', {'summary': summary, 'products': rows, 'treatments': treatments, 'changes': changes, 'media': media})
    csvwrite(OUT / 'Boldstone_All_188_Products_2026-10-25.csv', rows)
    csvwrite(OUT / 'Product_Image_Assignments_188.csv', media)
    csvwrite(OUT / 'All_Product_Image_Associations_10847.csv', all_media)
    csvwrite(OUT / 'Listing_Treatments_188.csv', [{k: v for k, v in t.items() if k not in ['accepted_working_fields', 'verification', 'selected_image', 'current_field_review', 'selected_source_description_retained']} for t in treatments])
    csvwrite(OUT / 'Specification_Changes_30.csv', [{'catalogue_option_id': x['product_id'], 'product_name': x['name'], 'field': x['field'], 'previous_working_detail': x['before']['display'], 'new_working_detail': x['after']['display'], 'qualification': x['after']['state'], 'basis': x['after']['basis'], 'image_url': x['image_url'], 'folder_url': x['folder_url']} for x in changes])
    cards = []
    for r in rows:
        pid = r['catalogue_option_id']
        specs = [(k, options[pid]['master_fields'][k]['display']) for k in FIELDS]
        cards.append('<article id="' + pid + '" data-search="' + html.escape((r['product_name'] + ' ' + r['family'] + ' ' + r['listing_treatment']).lower(), quote=True) + '"><h2>' + html.escape(r['product_name']) + '</h2><p>' + url_link(r['image_url'], 'Individual reference' if r['individual_image_role'] == 'Available' else r['individual_image_role']) + ' · ' + url_link(r['folder_url'], 'Containing folder') + ' · ' + url_link(r['all_images_review'], 'All related photographs') + '</p><p class="meta">' + html.escape(pid + ' · ' + r['family'] + ' · ' + r['individual_image_role']) + '</p><table><tbody>' + ''.join('<tr><th>' + html.escape(k) + '</th><td>' + html.escape(plain(v)) + '</td></tr>' for k, v in specs) + '</tbody></table><p><strong>Listing treatment:</strong> ' + html.escape(r['listing_treatment'].replace('_', ' ').capitalize()) + '</p><p>' + html.escape(r['listing_treatment_reason']) + '</p><details><summary>Existing records and qualifications</summary><p>' + html.escape('Selected source: ' + (r['selected_source_offer_ref'] or 'No exact selected source') + '. Related sources: ' + r['related_source_offer_refs']) + '</p><p>' + html.escape(r['source_and_configuration_notes']) + '</p><p>' + html.escape('Native execution: not performed. Specifications are working records with their individual qualifications.') + '</p></details></article>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone product listing — 188 options</title><style>body{font:16px/1.5 Arial,sans-serif;max-width:1100px;margin:36px auto;padding:0 24px;color:#20302b;background:#faf9f6}h1{font-size:30px}h2{font-size:22px}a{color:#175c65}article{background:white;border:1px solid #ddd9cf;border-radius:6px;padding:24px;margin:22px 0;break-inside:avoid}table{border-collapse:collapse;width:100%}th,td{padding:9px 12px;border-bottom:1px solid #e3e4df;vertical-align:top;text-align:left}th{width:22%}.meta{color:#59645f;font-size:13px}input{width:95%;padding:13px;font-size:17px}details{margin-top:16px}nav{margin:20px 0}#count{font-weight:bold}</style><h1>Boldstone product listing</h1><p>188 individually offered sculpture options across 110 working design groups. All working specifications are included. New material proposals and face-size estimates remain labelled; no physical verification is implied.</p><p>47 options retain supported individual source records, and four Wall Circle options have working pattern mappings. One legacy Frozen Fish row is retained without creating a duplicate, and the MCP1 native candidate remains qualified.</p><nav><a href="Boldstone_Matched_Product_List_2026-10-25.xlsx">Excel listing</a> · <a href="Boldstone_All_188_Products_2026-10-25.csv">Complete catalogue CSV</a> · <a href="Listing_Treatments_188.csv">Listing treatments</a> · <a href="Product_Image_Assignments_188.csv">Image assignments</a> · <a href="Specification_Changes_30.csv">30 specification changes</a></nav><p>The CSV is a neutral catalogue file. Dropbox links are review references; current shop identifiers and public media delivery require checking before a platform import. Existing platform write holds remain in place.</p><label for="q">Find a sculpture or listing treatment</label><input id="q" placeholder="e.g. Fingerprint, Azure or existing"><p id="count">188 options</p>''' + ''.join(cards) + '''<script>const q=document.getElementById('q');q.addEventListener('input',()=>{let n=0;document.querySelectorAll('article').forEach(a=>{a.hidden=!a.dataset.search.includes(q.value.toLowerCase());if(!a.hidden)n++});document.getElementById('count').textContent=n+' options'});</script></html>'''
    (OUT / 'index.html').write_text(page)
    page = page.replace('188 individually offered sculpture options across 110 working design groups.', '188 individually offered sculpture options: 110 working component-design groups plus the Wall Circle option family.')
    page = page.replace('<a href="Product_Image_Assignments_188.csv">Image assignments</a>', '<a href="Product_Image_Assignments_188.csv">Primary references</a> · <a href="All_Product_Image_Associations_10847.csv">All 10,847 qualified image associations</a>')
    (OUT / 'index.html').write_text(page)
    write(WORK / 'preliminary-validation.json', {'status': 'PASS_LOCAL_PREPARATION', 'active_rows': 188, 'changes': len(changed), 'other_active_fields_unchanged': 1098,
          'unique_selected_native_assignments': len(native_assignments), 'collisions': collisions, 'actual_measurements_added': 0, 'source_manifest': manifest})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
