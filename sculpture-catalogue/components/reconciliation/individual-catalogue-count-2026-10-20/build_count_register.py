#!/usr/bin/env python3
"""Build a count projection without changing owner decisions or evidence."""
import collections
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, parse_qs

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
A = BASE / 'components/reconciliation/individual-products-2026-10-20'
B = BASE / 'components/reconciliation/product-register-lane-b-audit-2026-10-20'
FIELDS = ['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability']
SOURCES = {
    'prepared_products': A / 'canonical-products.json',
    'source_model': BASE / 'components/evidence/component_register.json',
    'review97': BASE / 'components/reviews/workbook-refresh-2026-10-19/refresh-data.json',
    'owner_ledger': BASE / 'components/reviews/user_classifications.json',
    'review_progress': BASE / 'components/reviews/specification_review_progress.json',
    'family_arrangement_proof': B / 'FAMILY_AND_ARRANGEMENT_EDGES.json',
    'wall_circle_proof': B / 'WALL_CIRCLE_REGISTER_SUPPLEMENT_VERIFIED.json',
    'current_link_proof': B / 'MCP4_CURRENT_LINK_OVERLAY_VERIFIED.json',
    'source_identity_closure': BASE / 'components/parallel-reviews/source-cases-and-price-closure-2026-10-20/worker-01/closure-proposals.json',
    'current_manual_link_proof': BASE / 'components/reconciliation/product-register-final-readback-2026-10-20/MCP4_MANUAL_CURRENT_LINK_OVERLAY_VERIFIED.json',
    'case_closures': BASE / 'components/parallel-reviews/source-cases-and-price-closure-2026-10-20/CASE_CLOSURES.json',
    'scoped_working_corrections': BASE / 'components/parallel-reviews/source-cases-and-price-closure-2026-10-20/SPECIFICATION_UPDATES.json',
    'case_package_seal': BASE / 'components/parallel-reviews/source-cases-and-price-closure-2026-10-20/SEAL.json',
    'case_package_independent_check': BASE / 'components/parallel-reviews/source-cases-and-price-closure-2026-10-20/worker-03/FINAL_INDEPENDENT_PACKAGE_CHECK.json',
    'family_rename_overlay': BASE.parent / 'reports/dropbox-wall-structure-2026-10-20/step-02-three-family-renames-current-overlay.json',
    'family_rename_verification': BASE.parent / 'reports/dropbox-wall-structure-2026-10-20/step-02-three-family-renames-verification.json',
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def write(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def ident(key):
    return 'BSI-' + sha(key.encode())[:12].upper()

def unique(seq):
    return list(dict.fromkeys(seq))

def main():
    snapshots = HERE / 'inputs'
    snapshots.mkdir(parents=True, exist_ok=True)
    manifest, loaded = {}, {}
    for key, path in SOURCES.items():
        raw = path.read_bytes()
        dest = snapshots / (key + '.json')
        if dest.exists():
            assert dest.read_bytes() == raw, f'Source changed since frozen input: {key}'
        else:
            dest.write_bytes(raw)
        manifest[key] = {'source': str(path), 'snapshot': str(dest), 'sha256': sha(raw)}
        loaded[key] = json.loads(raw)
    a, m, r, u, p, b, wc, old_overlay, closure, overlay, cases, corrections = [loaded[k] for k in list(SOURCES)[:12]]
    assert loaded['case_package_seal']['status'] == 'PASS_SEALED_OWNER_AUTHORIZED_LOCAL_IMPORT_READY'
    assert loaded['case_package_independent_check']['status'] == 'PASS'
    assert len(a['products']) == 173 and len(r['reviews']) == 278
    assert len(m['components']) == 125 and wc['status'] == overlay['status'] == 'PASS'
    models = {c['component_id']: c for c in m['components']}
    source_reviews = {x[0] + '|' + x[1]: x for x in r['reviews']}
    family_edges = {x['product_id']: x for x in b['product_family_edges']}
    option_by_key = {}
    options = []

    # The original product IDs and all source assertions are retained unchanged.
    # Parent identity corrections do not mint replacement product/option IDs.
    for source in a['products']:
        x = copy.deepcopy(source)
        cid = x['canonical_design_id']
        if cid.startswith('AM-'):
            cid = 'BC-AM-' + cid[-1]
        elif cid == 'BC-SPICE':
            panel = x['canonical_key'].split('|')[1].split('-')[2]
            cid = 'CAT-SPICE-' + panel
        x['canonical_component_id'] = cid
        x['option_family_id'] = None
        x['family'] = family_edges[x['product_id']]['family']
        x['identity_basis'] = 'Existing owner-kept individual scope or owner-confirmed catalogue alias'
        x['count_class'] = 'Identified component option'
        x['counted_as_individual_option'] = True
        x['source_product_sha256'] = manifest['prepared_products']['sha256']
        x['size_class'] = ('Small' if x['canonical_key'].startswith('AM-S') else
                           'Large' if x['canonical_key'].startswith('AM-L') else '')
        x['build_class'] = 'Water feature' if 'water feature' in x['name'].lower() else 'As scoped in the retained specification'
        options.append(x)
        option_by_key[x['canonical_key']] = x

    # Identity approval and specification completeness are independent.
    for cid in ['BC-BONE-1', 'BC-BONE-2']:
        key = cid + '|BASE'
        review = source_reviews[key]
        decision = next(x for x in u['decisions'] if x.get('decision_id') == cid + ':identity:keep')
        source_fields = [x for x in r['specifications'] if x[0] == cid and x[1] == 'BASE']
        assert len(source_fields) == 6
        specs = {}
        for f in source_fields:
            specs[f[3]] = {'display': f[4], 'working_accepted': False,
                          'assertions': [{'source_scope': key, 'display': f[4], 'state': f[5],
                                          'basis': f[6], 'image_url': f[7], 'folder_url': f[8],
                                          'file_id': f[9], 'folder_id': f[10], 'proposal_id': f[11]}]}
        x = {'product_id': ident(key), 'canonical_key': key, 'canonical_design_id': cid,
             'canonical_component_id': cid, 'option_family_id': None, 'name': review[2],
             'retained_names': [review[2]], 'source_scopes': [key], 'family': 'Bone Spiral',
             'record_type': 'INDIVIDUAL_IDENTITY_WITH_SPECIFICATION_GAPS',
             'sale_unit': 'One individually listed panel under the owner individual-sale policy',
             'identity_basis': 'Explicit owner name and identity Keep; existing split component photograph',
             'identity_decision': decision, 'count_class': 'Identified component option',
             'counted_as_individual_option': True, 'specifications': specs,
             'six_working_fields_recorded': False, 'physical_specifications_verified': False,
             'orientation_options': [], 'size_class': '', 'build_class': 'As scoped in the retained specification',
             'image_url': review[7], 'folder_url': review[8], 'file_id': review[9], 'folder_id': review[10],
             'readiness_note': 'Counted by approved identity. Individual price and actual component specifications remain unresolved; no set values divided.'}
        options.append(x)
        option_by_key[key] = x

    # Source-supported individual units do not require a new owner name Keep.
    # Cup Ring is identified within a complete paired photo; Long remains a
    # documented size option whose exact current image and geometry parent are
    # unbound. Neither case is excluded because its price is unresolved.
    for cid in ['BC-CR-RING', 'BC-FFL-1']:
        entry = next(x for x in closure['entries'] if x['component_id'] == cid)
        key = cid + '|BASE'
        spec_keys = ['dimensions', 'weight', 'material_finish', 'fixing', 'individual_price', 'availability']
        specs = {field: {'display': entry['specifications'][sk]['display'],
                         'working_accepted': False,
                         'source_closure_proposal': copy.deepcopy(entry['specifications'][sk])}
                 for field, sk in zip(FIELDS, spec_keys)}
        x = {'product_id': ident(key), 'canonical_key': key, 'canonical_design_id': cid,
             'canonical_component_id': cid if cid == 'BC-CR-RING' else None,
             'option_family_id': None, 'unbound_size_option': cid == 'BC-FFL-1',
             'source_component_id': cid, 'name': entry['proposed_name'],
             'retained_names': [entry['proposed_name']], 'source_scopes': [key], 'family': entry['family'],
             'record_type': entry['closure'], 'sale_unit': entry['sale_unit']['kind'],
             'identity_basis': entry['identity_state'] + '; ' + entry['identity_evidence']['visual_finding'],
             'owner_name_keep_recorded': False, 'source_closure_evidence': copy.deepcopy(entry),
             'count_class': 'Source-supported component option' if cid == 'BC-CR-RING' else 'Documented size option; exact image and geometry parent unbound',
             'counted_as_individual_option': True, 'specifications': specs,
             'six_working_fields_recorded': False, 'physical_specifications_verified': False,
             'orientation_options': [], 'size_class': '100 × 22 cm source Long option' if cid == 'BC-FFL-1' else '',
             'build_class': 'Documented standard source option; current cast not verified',
             'image_url': '', 'folder_url': '', 'file_id': '', 'folder_id': '',
             'readiness_note': '; '.join(entry['missing_evidence'])}
        if cid == 'BC-CR-RING':
            asset = next(z for z in m['assets'] if z['id'] == 'id:cnqzTNngPVsAAAAAAA5zqA')
            folder = asset['path'].split('//', 1)[1].rsplit('/', 1)[0]
            x.update(file_id=asset['id'], folder_id=asset['folder_id'],
                     folder_url='https://www.dropbox.com/home' + quote('/' + folder.lstrip('/'), safe='/'),
                     image_role='Right panel in complete paired photograph; not an isolated image or a finish measurement')
            x['image_url'] = x['folder_url'] + '?preview=' + quote(asset['name'], safe='')
        else:
            x['image_role'] = 'Exact current 100 × 22 cm photograph unbound; no shorter photo substituted'
            x['source_related_short_component_id'] = 'BC-FFS-2'
            x['source_size_relationship'] = entry.get('relationship_to_short_design')
        options.append(x)
        option_by_key[key] = x

    # Wall Circle visual names are kept, but neither geometry equality nor an
    # exact mapping to the 144 native pattern/size/lighting rows is established.
    wc_field_names = dict(zip(['dimensions_and_depth', 'weight', 'material_and_finish',
                              'fixings_and_lighting', 'individual_price', 'availability'], FIELDS))
    for visual in wc['visual_working_records']:
        key = 'BC-WALL-CIRCLE|' + visual['review_id']
        specs = {}
        for f in visual['specification_review_items']:
            display = (f.get('confirmed_value') or f.get('accepted_working_value') or
                       f.get('working_guess') or f.get('source_facts') or f.get('status'))
            if f.get('confirmed_material'):
                display = f['confirmed_material'] + ' (owner confirmed); ' + (f.get('working_guess') or '')
            if f.get('confirmed_fixings'):
                display = f['confirmed_fixings'] + '; ' + f.get('confirmed_lighting', '') + ' lighting (owner confirmed for this entry)'
            specs[wc_field_names[f['group']]] = {'display': display, 'working_accepted': True,
                                                'source_field_record': copy.deepcopy(f)}
        x = {'product_id': ident(key), 'canonical_key': key,
             'canonical_design_id': None, 'canonical_component_id': None,
             'option_family_id': 'BC-WALL-CIRCLE', 'name': visual['working_name'],
             'retained_names': [visual['working_name']], 'source_scopes': [key], 'family': 'Wall Circle',
             'record_type': 'OWNER_KEPT_VISUAL_OPTION_NATIVE_ALIAS_UNRESOLVED',
             'sale_unit': 'One individually described Wall Circle appearance; exact native option alias unresolved',
             'identity_basis': 'Owner-kept visual entry under the family approval; not a distinct-form or stock certification',
             'count_class': 'Wall Circle visual option', 'counted_as_individual_option': True,
             'specifications': specs, 'original_visual_record': copy.deepcopy(visual),
             'six_working_fields_recorded': True, 'physical_specifications_verified': False,
             'orientation_options': [], 'size_class': '50 cm working scope; native size alias unresolved',
             'build_class': 'Lighting and mounting retain their own scoped evidence',
             'image_url': visual['image_url'], 'folder_url': visual['folder_url'],
             'file_id': visual['primary_file_id'], 'folder_id': visual['primary_folder_id'],
             'readiness_note': 'Visual working entry kept. Native pattern alias and distinct component-form identity unresolved; no physical-stock count inferred.'}
        options.append(x)
        option_by_key[key] = x

    # Apply current display paths by stable ID, preserving original source links.
    file_moves = {x['file_id']: x for x in overlay['moved_file_replacements']}
    folder_moves = {x['deleted_folder_id']: x for x in overlay['folder_replacements']}
    rename_overlay = loaded['family_rename_overlay']
    assert rename_overlay['status'] == 'PASS_CURRENT_PATH_OVERLAY'
    assert loaded['family_rename_verification']['status'] == 'PASS'
    rename_folders = {x['current_display_path']: x for x in rename_overlay['objects'] if x['object_type'] == 'folder'}
    assert len(rename_overlay['objects']) == 783
    for obj in rename_overlay['objects']:
        if obj['object_type'] == 'folder':
            folder_moves[obj['file_id']] = {'current_folder_id': obj['file_id'],
                                            'current_folder_url': obj['current_native_url']}
        else:
            parent = rename_folders[obj['current_display_path'].rsplit('/', 1)[0]]
            file_moves[obj['file_id']] = {'file_id': obj['file_id'], 'historical_file_path': obj['old_display_path'],
                                         'current_file_path': obj['current_display_path'],
                                         'current_folder_id': parent['file_id'],
                                         'current_folder_url': parent['current_native_url'],
                                         'current_image_url': obj['current_native_url']}
    current_updates = {x['product_id']: x for x in overlay['current_product_link_updates']}
    def native_path(value):
        return '/' + str(value).split('//', 1)[-1].strip('/')
    assets = {x['id']: x for x in m['assets']}
    asset_paths = {native_path(x['path']): x['id'] for x in m['assets']}
    for move in file_moves.values():
        for field in ['historical_file_path', 'current_file_path']:
            asset_paths[native_path(move[field])] = move['file_id']

    def resolve_current_reference(file_id='', folder_id='', image_url='', folder_url=''):
        if not file_id and image_url:
            parsed = urlparse(image_url)
            if parsed.netloc.endswith('dropbox.com'):
                path = unquote(parsed.path)
                for prefix in ['/home', '/preview']:
                    if path.startswith(prefix + '/'):
                        path = path[len(prefix):]
                        break
                preview = parse_qs(parsed.query).get('preview', [])
                if preview:
                    path = path.rstrip('/') + '/' + preview[0]
                file_id = asset_paths.get(path, '')
        if file_id in file_moves:
            move = file_moves[file_id]
            return {'file_id': file_id, 'folder_id': move['current_folder_id'],
                    'image_url': move['current_image_url'],
                    'folder_url': move.get('current_folder_url') or move['current_image_url'].split('?preview=')[0]}
        if folder_id in folder_moves:
            move = folder_moves[folder_id]
            newfolder = move['current_folder_url']
            name = assets.get(file_id, {}).get('name')
            return {'file_id': file_id, 'folder_id': move['current_folder_id'],
                    'image_url': newfolder + '?preview=' + quote(name, safe='') if name else image_url,
                    'folder_url': newfolder}
        return {'file_id': file_id, 'folder_id': folder_id or assets.get(file_id, {}).get('folder_id', ''), 'image_url': image_url, 'folder_url': folder_url}

    def update_current_display(record, file_id='', folder_id=''):
        prior = {k: record.get(k, '') for k in ['file_id', 'folder_id', 'image_url', 'folder_url']}
        current = resolve_current_reference(file_id or prior['file_id'], folder_id or prior['folder_id'], prior['image_url'], prior['folder_url'])
        if current['image_url'] != prior['image_url'] or current['folder_url'] != prior['folder_url']:
            record.setdefault('historical_display_reference', prior)
            record.update(current)
        else:
            record.setdefault('file_id', current['file_id'])
            record.setdefault('folder_id', current['folder_id'])
        return record
    for x in options:
        if x['product_id'] in current_updates:
            x['historical_primary_link'] = {k: x[k] for k in ['image_url', 'folder_url', 'folder_id', 'file_id']}
            x.update(current_updates[x['product_id']]['current_values'])
        elif x.get('file_id') in file_moves:
            move = file_moves[x['file_id']]
            x['historical_primary_link'] = {k: x.get(k) for k in ['image_url', 'folder_url', 'folder_id', 'file_id']}
            x['image_url'], x['folder_id'] = move['current_image_url'], move['current_folder_id']
            x['folder_url'] = move.get('current_folder_url') or move['current_image_url'].split('?preview=')[0]
        elif x.get('folder_id') in folder_moves:
            move = folder_moves[x['folder_id']]
            x['historical_primary_link'] = {k: x.get(k) for k in ['image_url', 'folder_url', 'folder_id', 'file_id']}
            x['folder_id'], x['folder_url'] = move['current_folder_id'], move['current_folder_url']
        x['current_link_basis'] = ('Authorized Dropbox move/deletion terminal receipts, independently read back'
                                   if 'historical_primary_link' in x else 'Preserved reviewed stable IDs and last verified source links')
        x['offered_fixing_choices'] = [z['label'] for z in p['global_fixing_choice_policy']['offered_fixing_options']]
        x['offered_fixing_basis'] = p['global_fixing_choice_policy']['policy_id']
        x['offered_choices_do_not_confirm_current_installed_hardware'] = True
        update_current_display(x)
        if x.get('context_image_url'):
            context = resolve_current_reference(image_url=x['context_image_url'], folder_url=x.get('context_folder_url', ''))
            x['context_image_url'], x['context_folder_url'] = context['image_url'], context['folder_url']

    # The separately authorized four-case reconciliation is an additive current
    # working overlay. Original A assertions and the Review97 file stay intact.
    correction_fields = dict(zip(['dimensions', 'weight', 'material_finish', 'fixing', 'individual_price', 'availability'], FIELDS))
    correction_ids = []
    for record in corrections['records']:
        x = next(y for y in options if y['product_id'] == record['product_id'])
        assert x['canonical_key'] == record['canonical_key']
        for field_key, field in correction_fields.items():
            x['specifications'][field]['prior_working_display'] = x['specifications'][field]['display']
            x['specifications'][field]['display'] = record['specifications'][field_key]['display']
            x['specifications'][field]['scoped_current_working_overlay'] = copy.deepcopy(record['specifications'][field_key])
        x['scoped_working_correction_source'] = manifest['scoped_working_corrections']
        correction_ids.append(x['product_id'])

    overrides = {
        'BC-AC-FULL': 'Acanthus Full / Acanthus and Moon', 'BC-AM-1': 'Ammonite 1 / Left Panel',
        'BC-AM-2': 'Ammonite 2 / Right Panel', 'CAT-SPICE-1': 'Spice Texture 1',
        'CAT-SPICE-2': 'Spice Texture 2', 'BC-DP-SPIRAL': 'Golden Spiral / Timeless Spiral',
        'BC-LEAF-FORM': 'Leaf Form — LF1 / LF2 orientation options',
        'BC-LAVA-1': 'Lava Moon — Left Panel', 'BC-LAVA-2': 'Lava Moon — Centre Panel',
        'BC-LAVA-3': 'Lava Moon — Right Panel', 'BC-GLEN-1': 'Gleneagles Vine and Tendril — Top Left',
        'BC-GLEN-2': 'Gleneagles Vine and Tendril — Top Right', 'BC-GLEN-3': 'Gleneagles Vine and Tendril — Bottom Left',
        'BC-GLEN-4': 'Gleneagles Vine and Tendril — Bottom Right', 'BC-BR-1': 'Brancusi 1 / Meander Light (MLD1)',
        'BC-BR-2': 'Brancusi 2 / Meander Dark (MLD2)', 'BC-RW-SPIRAL1': 'Raked Spiral 1',
        'BC-RW-SPIRAL3': 'Raked Spiral 3', 'BC-RW-WAVE': 'Raked Spiral 2',
        'BC-RIYADH-1': 'Riyadh — Dune Ripple Panel', 'BC-RIYADH-2': 'Riyadh — Shellmoon Panel',
        'BC-RIYADH-3': 'Riyadh — Plain Moon Panel', 'BC-TEXTURE-WIDE': 'Textured Panel — Wide',
        'BC-TEXTURE-TALL': 'Textured Panel — Tall', 'BC-WBMS-MOON': 'Wave Between Moonshadow — Moonshadow Panel',
        'BC-WBMS-WAVE': 'Wave Between Moonshadow — Wave Panel',
        'BC-FP-LEFT': 'Fingerprint — Left Panel', 'BC-FP-RIGHT': 'Fingerprint — Right Panel',
        'BC-CR-RING': 'Cup Ring (CRS2)',
        'BC-DDR-SPIRAL': 'Deco Dune Ripple — Spiral', 'BC-DDR-WAVE': 'Deco Dune Ripple — Wave',
    }
    for cid, detail in p['catalogue_design_aliases'].items():
        overrides[cid] = detail['current_display_name']
    by_component = collections.defaultdict(list)
    for x in options:
        if x['canonical_component_id']:
            by_component[x['canonical_component_id']].append(x)
    components = []
    for cid, children in by_component.items():
        first = children[0]
        name = overrides.get(cid) or first['name'].split(' — ')[0]
        if cid in ['BC-BONE-1', 'BC-BONE-2', 'BC-ICARUS']:
            name = first['name']
        components.append({'component_id': cid, 'name': name, 'family': first['family'],
                           'record_type': 'IDENTIFIED_CATALOGUE_COMPONENT',
                           'option_ids': [x['product_id'] for x in children],
                           'option_count': len(children), 'option_names': [x['name'] for x in children],
                           'image_url': first['image_url'], 'folder_url': first['folder_url'],
                           'file_id': first['file_id'], 'folder_id': first['folder_id'],
                           'scope_note': ('Two independent size options for this same panel identity' if cid.startswith('BC-AM-') else
                                          'Separate owner-kept panel split from the former shared Spice Texture heading' if cid.startswith('CAT-SPICE-') else
                                          'LF1 and LF2 White names retained as opposite-orientation choices; Gold remains a separate finish' if cid == 'BC-LEAF-FORM' else
                                          'Former Concave Moon retained as an alias; four scoped finish options' if cid == 'BC-MCP-4' else
                                          'Approved identity retained despite specification/individual-price gaps' if cid.startswith('BC-BONE-') else
                                          'Distinct catalogue identity; finish, size and build options listed separately'),
                           'physical_mould_count': None, 'physical_stock_quantity': None})
    components.sort(key=lambda x: (x['family'].casefold(), x['name'].casefold()))
    options.sort(key=lambda x: (x['family'].casefold(), x['canonical_component_id'] or x['option_family_id'] or x['source_component_id'], x['name'].casefold()))
    comp_index = {x['component_id']: x for x in components}
    product_index = {x['product_id']: x for x in options}

    source_map = {}
    for cid in models:
        if cid in comp_index:
            targets, treatment = [cid], 'Identified component identity'
        elif cid == 'BC-SPICE':
            targets, treatment = ['CAT-SPICE-1', 'CAT-SPICE-2'], 'Parent split into two identified panels'
        elif cid == 'BC-CONCAVE':
            targets, treatment = ['BC-MCP-4'], 'Historical design alias'
        elif cid.startswith('BC-MP-'):
            targets = unique(x.split(':')[0] for x in p['historical_source_component_to_catalogue_aliases'][cid])
            treatment = 'Historical numbering alias'
        elif cid.startswith('BC-LUCIANO-'):
            targets, treatment = ['BC-LAVA-1', 'BC-LAVA-2', 'BC-LAVA-3'], 'Family alias; exact historical position/finish unresolved'
        elif cid.startswith('BC-MLAVA-WALL-'):
            targets, treatment = ['BC-MLAVA-' + cid[-1]], 'Arrangement position; existing component reused'
        elif cid == 'BC-WALL-CIRCLE':
            targets, treatment = [], 'Wall Circle option family; distinct design count unresolved'
        elif cid == 'BC-FFL-1':
            targets, treatment = [], 'Documented individual Long size option; exact current photo and geometry parent unbound'
        elif cid == 'BC-DR-WAVE3':
            targets, treatment = [], 'Documented source identity; current exact component binding unresolved'
        else:
            assert cid in ['BC-PORTMAN-1', 'BC-PORTMAN-2', 'BC-BAR-STUDY-1', 'BC-BAR-STUDY-2', 'BC-BAR-STUDY-3', 'BC-MIX-SPIRALS'], cid
            targets, treatment = [], 'Group/project reference; individual identity not established'
        source_map[cid] = {'source_component_id': cid, 'source_name': models[cid]['name'],
                           'treatment': treatment, 'component_targets': targets,
                           'option_family_target': 'BC-WALL-CIRCLE' if cid == 'BC-WALL-CIRCLE' else None,
                           'source_folder_ids': models[cid]['folder_ids'].splitlines(),
                           'source_file_ids': models[cid]['example_file_ids'].splitlines()}
    for component in components:
        component['source_component_ids'] = [cid for cid, x in source_map.items() if component['component_id'] in x['component_targets']]
        component['retained_names'] = unique([component['name']] +
                                             [name for oid in component['option_ids'] for name in product_index[oid]['retained_names']] +
                                             [models[cid]['name'] for cid in component['source_component_ids']])

    # Every original review row has one disposition; headers are not new units.
    reconciliation = copy.deepcopy(a['scope_reconciliation'])
    for row in reconciliation:
        key = row['source_scope']
        review = source_reviews[key]
        update_current_display(row, review[9], review[10])
        if key in ['BC-BONE-1|BASE', 'BC-BONE-2|BASE', 'BC-CR-RING|BASE', 'BC-FFL-1|BASE']:
            row['historical_disposition'] = row['disposition']
            row.update(disposition='IDENTIFIED_COMPONENT_OPTION', targets=[option_by_key[key]['product_id']],
                       reason=('Owner-kept individual identity. Missing specifications and price affect readiness, not identity count.'
                               if key.startswith('BC-BONE-') else
                               'Source-supported individual component/size sale unit; source labels and exact photograph limitations retained. No new owner name Keep asserted.'))
        elif key == 'BC-WALL-CIRCLE|BASE':
            row.update(disposition='OPTION_FAMILY_HEADER', targets=['BC-WALL-CIRCLE'],
                       reason='Seven separately kept visual options supplement this heading. The 144 native options overlap and lack an exact name crosswalk; the heading creates no extra sculpture.')
        elif key == 'BC-DR-WAVE3|BASE':
            row.update(disposition='HISTORICAL_SOURCE_CODE_REFERENCE', targets=['CAND-DR-WAVE3'],
                       reason='The source illustration matches the selected image already counted as DR1 White. Historical three-mould code conflict is retained; no additional current unit or whole-code alias is inferred.')
        row['individual_count_increment'] = (1 if row['disposition'] in ['INDIVIDUAL_PRODUCT', 'IDENTIFIED_COMPONENT_OPTION'] else 0)
        # The orientation alias contributes no extra option.
        row['component_targets'] = unique(product_index[t]['canonical_component_id'] for t in row['targets']
                                           if t in product_index and product_index[t]['canonical_component_id'])

    aliases = []
    def alias(source, target, relation, reason, image_url='', folder_url='', file_id='', folder_id='', evidence=''):
        aliases.append({'alias_id': 'AL-' + sha((source + '|' + relation).encode())[:12].upper(),
                        'source': source, 'targets': target, 'relationship': relation, 'reason': reason,
                        'image_url': image_url, 'folder_url': folder_url, 'file_id': file_id, 'folder_id': folder_id,
                        'evidence': evidence, 'individual_count_increment': 0})
    for x in m['aliases']:
        targets = source_map[x['component_id']]['component_targets']
        alias(x['alias'], targets, x['relationship'], x['canonical'] + '; ' + x.get('rotation', ''), evidence=x['source'])
    for x in a['historical_alias_reconciliation']:
        alias(x['source_scope'], x['targets'], x['disposition'], x['reason'], evidence=x['source_locator'])
        cid, scope = x['source_scope'].split('|', 1)
        old = p['reviews'].get(cid, {}).get('size_finish_variants', {}).get(scope, {})
        aliases[-1]['source_name'] = old.get('canonical_name') or old.get('proposed_name') or ('Concave Moon' if cid == 'BC-CONCAVE' and scope == 'BASE' else x['source_title'])
        for target in x['targets']:
            if target in product_index:
                product_index[target]['retained_names'] = unique(product_index[target]['retained_names'] + [aliases[-1]['source_name']])
    for cid in p['historical_source_component_to_catalogue_aliases']:
        alias(cid, source_map[cid]['component_targets'], 'Historical Moonphase numbering',
              'Four current designs; historic maker IDs and original names retained. No physical mould or stock merger.')
    for key, x in p['source_identity_consolidations'].items():
        alias(x['previous_source_label'], [x['canonical_component_id']], 'Owner-confirmed source design alias',
              'Same catalogue design as Chelsea Moonwave; source-specific dimensions and specifications remain separate.',
              file_id=x['primary_file_id'], folder_id=x['primary_folder_id'], evidence=x['approval_record'] if 'approval_record' in x else key)
    for cid in ['BC-LUCIANO-1', 'BC-LUCIANO-2', 'BC-LUCIANO-3']:
        alias(cid, ['BC-LAVA-1', 'BC-LAVA-2', 'BC-LAVA-3'], 'Family alias with unresolved position',
              'Luciano Moonshell Lava is the Lava Moon family. Exact historical panel and finish association is not inferred.')
    alias('Luciano Moonshell Lava', ['Lava Moon'], 'Owner-confirmed family alias',
          'One catalogue family; this does not establish exact historical project-position or finish matches.')
    for x in reconciliation:
        if x['disposition'] in ['SELECTED_IMAGE_REFERENCE_ALIAS', 'SAME_DESIGN_SOURCE_ALIAS', 'ORIENTATION_OPTION']:
            review = source_reviews[x['source_scope']]
            alias(x['source_scope'], x['targets'], x['disposition'], x['reason'],
                  review[7], review[8], review[9], review[10], x['source_locator'])
    for source, x in a['reference_aliases'].items():
        alias(source, [x['target_reference_id']], 'Historical context reference alias',
              x['reason'], evidence='Prepared reconciliation reference_aliases')
    for x in aliases:
        update_current_display(x)

    boms = collections.defaultdict(list)
    for x in m['bom']:
        boms[x['offer_ref']].append(x)
    source_sets, all_offer_edges = [], []
    for offer in m['platform_records']:
        members = []
        for bom in boms[offer['offer_ref']]:
            members.append({'bom_id': bom['bom_id'], 'source_component_id': bom['component_id'],
                            'canonical_component_targets': source_map[bom['component_id']]['component_targets'],
                            'position': bom['position'], 'quantity': bom['quantity'],
                            'relationship_status': 'Preserved source/proposed BOM association; exact finish, size and specimen remain scoped',
                            'original_bom': copy.deepcopy(bom)})
        edge = {'offer_ref': offer['offer_ref'], 'source_offer': copy.deepcopy(offer), 'members': members,
                'individual_count_increment': 0}
        asset = assets.get(offer.get('image_file_id'))
        if asset:
            folderpath = native_path(asset['path']).rsplit('/', 1)[0]
            folderurl = 'https://www.dropbox.com/home' + quote(folderpath, safe='/')
            edge['current_primary_reference'] = resolve_current_reference(
                asset['id'], asset['folder_id'], folderurl + '?preview=' + quote(asset['name'], safe=''), folderurl)
        all_offer_edges.append(edge)
        if len(members) > 1 or float(offer.get('native_parts') or 1) > 1:
            edge['relationship_status'] = ('Native multi-piece offer; source BOM retained'
                                           if float(offer.get('native_parts') or 1) > 1 else
                                           'Proposed multi-component offer; native piece count differs or is unspecified')
            source_sets.append(edge)

    arrangements = copy.deepcopy(b['other_group_references'])
    arrangement_edges = copy.deepcopy(b['explicit_arrangement_member_edges'])
    for x in arrangements:
        update_current_display(x)
        x['counted_as_individual_option'] = False
        x['individual_count_increment'] = 0
        x['confirmed_member_option_ids'] = [e['product_id'] for e in arrangement_edges if e['reference_id'] == x['reference_id']]
    for x in options:
        x['confirmed_arrangement_ids'] = [e['reference_id'] for e in arrangement_edges if e['product_id'] == x['product_id']]

    exceptions = [copy.deepcopy(x) for x in a['source_candidates'] if x['component_id'] == 'BC-DR-WAVE3']
    for x in exceptions:
        x['name'] = 'Historical Dune Ripple 3 (DR3) source-code reference'
        x['exception_type'] = 'Selected image already counted; historical code conflict retained'
        x['required_information'] = 'Maker picture043 matches the selected image already owner-aliased to DR1 White. No extra current unit is supported. A separate three-mould source statement remains as historical counterevidence; no whole-code or physical-mould equivalence is asserted.'
        x['case_status'] = 'Closed as a source illustration reference; historical code conflict retained'
        x['count_treatment'] = 'Not added to the identified component or individual option counts'
    for cid in ['BC-CR-RING', 'BC-FFL-1']:
        x = option_by_key[cid + '|BASE']
        exceptions.append({'candidate_id': 'GAP-' + cid, 'name': x['name'],
                           'exception_type': 'Photograph / parent identity gap on an included sale option',
                           'required_information': x['readiness_note'],
                           'count_treatment': ('Included once as an identified component and individual option; missing isolated photo does not remove its identity'
                                               if cid == 'BC-CR-RING' else
                                               'Included once as a documented source size option; no extra unique design claimed'),
                           'source_scopes': x['source_scopes'], 'image_url': x['image_url'], 'folder_url': x['folder_url']})
    case_index = {x['case_id']: x for x in cases['cases']}
    for x in a['additional_source_candidates']:
        x = copy.deepcopy(x)
        case = case_index[x['candidate_id']]
        payload = case['payload']
        assert payload['new_product_count'] == 0
        x['exception_type'] = 'Closed as detail / scene / group context'
        x['required_information'] = payload['exact_reason']
        x['case_status'] = case['review_outcome']
        x['case_evidence'] = copy.deepcopy(case)
        x['count_treatment'] = 'Reference only; no extra individual finish record or alias inferred. No further confirmation requested in this scope.'
        exceptions.append(x)
    exceptions.append({'candidate_id': 'EX-WALL-CIRCLE-CROSSWALK', 'name': 'Wall Circle native pattern / size / lighting crosswalk',
                       'exception_type': 'Option family crosswalk',
                       'required_information': 'Map the seven approved visual names to the 18 native pattern names and their four diameters and two lighting choices. A unique component-design total for this family is unresolved.',
                       'count_treatment': 'Seven visual option records included; 144 native source rows kept separately and never added to seven',
                       'source_scopes': ['BC-WALL-CIRCLE|BASE'], 'image_url': wc['visual_working_records'][0]['image_url'],
                       'folder_url': wc['visual_working_records'][0]['folder_url']})
    for x in exceptions:
        update_current_display(x)

    option_families = [{'option_family_id': 'BC-WALL-CIRCLE', 'name': 'Wall Circle',
                        'visual_option_ids': [x['product_id'] for x in options if x['option_family_id']],
                        'visual_options': 7, 'native_source_options': 144,
                        'identified_component_design_count': None,
                        'count_treatment': 'Option-family heading; no extra individual sculpture and no certified distinct-design total'}]
    summary = {'identified_component_identities': len(components),
               'individual_options_on_identified_components': sum(x['option_count'] for x in components),
               'documented_individual_size_options_exact_photo_unbound': 1,
               'wall_circle_kept_visual_options': 7, 'individual_named_working_options': len(options),
               'wall_circle_option_families_distinct_design_count_unresolved': 1,
               'wall_circle_native_source_combinations_not_added': len(wc['native_options']),
               'source_set_or_proposed_multi_component_offers': len(source_sets),
               'arrangement_and_context_references': len(arrangements),
               'confirmed_arrangement_member_edges': len(arrangement_edges),
               'alias_relationship_records_not_added': len(aliases),
               'source_identity_exceptions_not_added': 1, 'finish_references_closed_as_context_not_added': 9,
               'scoped_current_working_corrections_applied': len(correction_ids),
               'individual_options_with_dropbox_reference': sum(bool(x.get('file_id')) for x in options),
               'source_model_component_rows_disposed': len(source_map),
               'source_review_rows_disposed': len(reconciliation),
               'original_review_specification_assertions_preserved': len(r['specifications']),
               'source_platform_offers_preserved': len(all_offer_edges),
               'source_media_configurations_preserved': len(a['source_configuration_coverage']),
               'physical_stock_quantity': None, 'physical_mould_count': None,
               'catalogue_wide_unique_design_total_including_unresolved_sources': None}
    assert summary['identified_component_identities'] == 111
    assert summary['individual_options_on_identified_components'] == 176
    assert len(options) == len({x['product_id'] for x in options}) == 184
    assert len(source_map) == 125 and len(reconciliation) == 278
    assert len(r['specifications']) == 1668
    assert sum(x['individual_count_increment'] for x in reconciliation) == 177
    assert set(x['product_id'] for x in a['products']) <= set(product_index)
    assert all(x.get('file_id') and x.get('folder_id') and x.get('image_url') and x.get('folder_url') for x in options if not x.get('unbound_size_option'))
    assert len([x for x in options if not x.get('file_id')]) == 1
    assert all(len(x['specifications']) == 6 for x in options)
    assert all(t in comp_index for x in source_map.values() for t in x['component_targets'])
    assert all(e['product_id'] in product_index for e in arrangement_edges)
    assert len(wc['native_options']) == 144
    graph = {'schema': 'boldstone.individual-catalogue-count.v1',
             'created_utc': datetime.now(timezone.utc).isoformat(),
             'count_definition': 'A component is a distinct identified catalogue member. Finish, size, build and orientation choices are separate option records. An approved identity is not excluded for missing specifications or price. Counts describe catalogue records, not physical casts, moulds or stock.',
             'scope_status': 'All current review rows and source component IDs classified; exact counts for the identified catalogue and documented sale options. Nine extra finish sources are closed as context only. One Long size option has no exact current photograph/geometry parent. Historical DR3 code conflict, Wall Circle design equality/native aliases and group-only component identities remain explicit limits on a catalogue-wide unique-design total.',
             'summary': summary, 'components': components, 'options': options, 'option_families': option_families,
             'source_component_dispositions': list(source_map.values()), 'source_review_reconciliation': reconciliation,
             'aliases': aliases, 'source_sets': source_sets, 'arrangement_context_references': arrangements,
             'confirmed_arrangement_member_edges': arrangement_edges,
             'source_offer_edges': all_offer_edges, 'source_media_configuration_coverage': a['source_configuration_coverage'],
             'wall_circle_native_options': wc['native_options'], 'exceptions': exceptions,
             'original_review_specification_assertions': r['specifications'],
             'source_only_assertions_not_applied_to_options': a['source_only_assertions_not_applied_to_products'],
             'current_link_overlay': overlay, 'historical_current_link_overlay': old_overlay, 'input_manifest': manifest,
             'current_family_rename_overlay': {'source': manifest['family_rename_overlay'],
                                              'status': rename_overlay['status'], 'summary': rename_overlay['summary'],
                                              'identity_guard': rename_overlay['catalogue_identity_guard']},
             'case_closure_dispositions': cases['cases'],
             'scoped_working_corrections': corrections, 'scoped_working_correction_option_ids': correction_ids,
             'normalization_decisions': [
                 {'case': 'Ammonite', 'before': 4, 'after': 2, 'basis': 'Two panel IDs, each with Small and Large options; existing model size_variants and owner-kept names.'},
                 {'case': 'Spice Texture', 'before': 1, 'after': 2, 'basis': 'Two separately kept panel layout identities; old parent retained as a source heading.'},
                 {'case': 'Bone Spiral', 'before': 0, 'after': 2, 'basis': 'Explicit owner-kept identities; missing full working specifications and individual price do not negate identity.'},
                 {'case': 'Cup Ring', 'before': 0, 'after': 1, 'basis': 'Maker-labelled complete ring and one-cast source match the complete right panel in Dropbox paired photo007. Count once; isolated photo remains missing.'},
                 {'case': 'Frozen Fish Long', 'before': 0, 'after': 1, 'basis': 'Documented separately sold100×22 cm source option; no exact current photograph or additional unique geometry asserted.'},
                 {'case': 'Leaf Form White', 'before': 2, 'after': 1, 'basis': 'Existing source documents LF2 opposite LF1 orientation. Both original owner names and assertions retained. Gold remains another finish option.'},
                 {'case': 'Wall Circle', 'before': 0, 'after': 7, 'basis': 'Seven approved visual option entries. The family header contributes no additional component identity; 144 native rows overlap and are not summed.'},
             ],
             'source_integrity_policy': 'Sealed A and B packets, owner ledgers and original specifications are immutable sources. This additive projection changes count dispositions and current link display only; no new owner decisions or exact platform matches are asserted.'}
    write('input-manifest.json', manifest)
    write('canonical-count-register.json', graph)
    write('build-checks.json', {'status': 'PASS', 'summary': summary,
                              'assertion_eligibility_policy': 'Identity count independent of six-field completeness',
                              'original_product_ids_retained': len(a['products']),
                              'options_with_stable_media_ids_and_links': sum(bool(x.get('file_id')) for x in options),
                              'explicit_null_image_for_unbound_long_size_option': True,
                              'all125_source_component_ids_disposed_once': True,
                              'all278_review_rows_disposed_once': True,
                              'all1668_original_field_assertions_retained': True})
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
