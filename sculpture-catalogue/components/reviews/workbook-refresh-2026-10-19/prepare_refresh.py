"""Freeze catalogue evidence and prepare review views without changing source records."""
import copy
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
paths = {'reviews': ROOT / 'components/reviews/specification_review_progress.json',
         'decisions': ROOT / 'components/reviews/user_classifications.json',
         'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json',
         'component_checkpoint': ROOT / 'components/checkpoint.json', 'root_checkpoint': ROOT / 'checkpoint.json',
         'model': ROOT / 'components/evidence/component_register.json',
         'workbook_manifest': ROOT / 'components/evidence/component_workbook_manifest.json'}
docs = {key: read(path) for key, path in paths.items()}
p, u, model = docs['reviews'], docs['decisions'], docs['model']
assert sha(paths['model']) == 'ba65d17e6182ba6b89f30400d2f0236bc22a1478c29fb39be4d362a48d24fb61'
assert docs['root_checkpoint']['current_component_review'] == docs['component_checkpoint']
assert p['group_photo_review_policy']['group_photo_component_questions_required'] is False
source_files = []
new_working_projection_nodes = {}
for batch in range(92,98):
    receipt_path = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{batch}/import-receipt.json'
    if not receipt_path.exists(): continue
    source_files.append({'source':str(receipt_path),'sha256':sha(receipt_path)})
    for item in read(receipt_path)['scopes']:
        cid,scope = item['component_id'],item['size_finish_variant_id']
        locator = item.get('model_locator') or ['reviews',cid,'build_variants' if item['review_scope']=='BUILD' else 'size_finish_variants',scope]
        node = p
        for part in locator: node = node[part]
        new_working_projection_nodes[cid+'|'+scope] = node
for key, path in paths.items():
    dest = HERE / 'snapshot' / (key + '.json')
    dest.parent.mkdir(exist_ok=True)
    dest.write_bytes(path.read_bytes())
    source_files.append({'source': str(path), 'snapshot': str(dest), 'sha256': sha(dest)})
previous = Path(docs['workbook_manifest']['output'])
assert sha(previous) == '02532ec7664b39caa7b62755c8a45748d937045e801ce7fcd985a859faf62f6f'
source_files.append({'source': str(previous), 'sha256': sha(previous)})
if p.get('global_approximate_weight_policy'):
    resolution_path = ROOT / 'components/reviews/parallel-import-2026-10-19-batch90/current-primary-reference-resolution.json'
    resolution = read(resolution_path)
    assert resolution['same_native_revision_and_size_as_replacement_receipt'] and resolution['cached_current_original_rehashed_and_visually_inspected']
    for path in [resolution_path, Path(resolution['replacement_receipt']['path']), Path(resolution['cached_current_original']['path'])]:
        source_files.append({'source': str(path), 'sha256': sha(path)})
source_assets = {x['id']: x for x in model['assets']}
assets = copy.deepcopy(source_assets)
folders = {x['id']: copy.deepcopy(x) for x in model['groups']}
components = {x['component_id']: x for x in model['components']}
consolidations = p.get('canonical_component_consolidations', {})
for batch in range(92,97):
    metadata_path = ROOT/f'components/reviews/parallel-import-2026-10-19-batch{batch}/current-reference-check.json'
    if not metadata_path.exists(): continue
    source_files.append({'source':str(metadata_path),'sha256':sha(metadata_path)})
    for entry in read(metadata_path)['metadata']:
        head=entry[entry['metadata_type']]
        if entry['metadata_type']=='file' and head['id'] in assets:
            assets[head['id']].update(path=head['path_display'],name=head['name'])
        elif entry['metadata_type']=='folder':
            folders.setdefault(head['id'],{'id':head['id']})
            folders[head['id']].update(path=head['path_display'],name=head['name'])
for overlay in p.get('live_dropbox_metadata_overlays', {}).values():
    for fid, folder in overlay.get('folders', {}).items():
        folders.setdefault(fid, {'id': fid})
        folders[fid].update({'name': folder['name'], 'path': folder['path_display']})
for fid, override in p.get('asset_assignment_overrides', {}).items():
    if fid in assets:
        a = assets[fid]
        for field, target in [('path_display', 'path'), ('folder_id', 'folder_id'), ('family', 'family')]:
            if override.get(field):
                a[target] = override[field]
        if override.get('path_display'):
            a['name'] = override['path_display'].rsplit('/', 1)[-1]
            a['group'] = override['path_display'].rsplit('/', 2)[-2]
for review in p['reviews'].values():
    for item in [review, *review.get('size_finish_variants', {}).values(), *review.get('build_variants', {}).values(), *[item for item in review.get('component_layouts', {}).values() if item.get('working_acceptance_basis') == 'DERIVED_FROM_STANDING_OWNER_POLICY']]:
        ref = item.get('current_dropbox_reference', {})
        if ref.get('file_id') in assets and ref.get('file_path'):
            assets[ref['file_id']]['path'] = ref['file_path']
            assets[ref['file_id']]['name'] = ref['file_path'].rsplit('/', 1)[-1]
for item in [*p.get('catalogue_alias_reviews', {}).values(), *p.get('source_design_reviews', {}).values()]:
    if item.get('working_acceptance_basis') != 'DERIVED_FROM_STANDING_OWNER_POLICY': continue
    ref = item.get('current_dropbox_reference', {})
    if ref.get('file_id') in assets and ref.get('file_path'):
        assets[ref['file_id']]['path'] = ref['file_path']
        assets[ref['file_id']]['name'] = ref['file_path'].rsplit('/', 1)[-1]


def first(value):
    if isinstance(value, list):
        return next((str(v) for v in value if v), '')
    return str(value or '').split('\n')[0]


def clean_path(value):
    return '/' + value.split('//', 1)[1].lstrip('/') if value.startswith('ns:') else value


def references(node, source=None):
    source = source or {}
    bindings = node.get('historical_name_keep_bindings', [])
    ref = node.get('current_dropbox_reference', {}) or (bindings[0].get('current_dropbox_reference', {}) if bindings else {})
    if node.get('current_primary_image_id') and node.get('image_reference_refresh'):
        refresh = read(ROOT / node['image_reference_refresh'])
        head = refresh['current_file_metadata']['file']
        parent = refresh['containing_folder_metadata']['folder']
        assert head['id'] == node['current_primary_image_id'] and parent['id'] == node['current_primary_folder_id']
        assert head['path_display'].rsplit('/', 1)[0] == parent['path_display']
        ref = {'file_id': head['id'], 'folder_id': parent['id'], 'file_path': head['path_display'],
               'folder_path': parent['path_display'], 'image_url': node['current_primary_image_link']}
    fid = first(ref.get('file_id') or node.get('primary_image_id') or node.get('primary_file_id')
                or node.get('source_asset_id') or node.get('primary_file_ids') or source.get('example_file_ids'))
    folder = first(ref.get('folder_id') or node.get('primary_folder_id') or node.get('source_folder_id')
                   or node.get('containing_folder_ids') or assets.get(fid, {}).get('folder_id') or source.get('folder_ids'))
    file_path = clean_path(ref.get('file_path') or node.get('source_path_display') or assets.get(fid, {}).get('path', ''))
    folder_path = clean_path(ref.get('folder_path') or node.get('source_folder_path_display')
                            or folders.get(folder, {}).get('path', '') or file_path.rsplit('/', 1)[0])
    image = ref.get('image_url') or ref.get('image_link') or node.get('image_link', '')
    folder_url = ref.get('folder_url') or ref.get('folder_link') or node.get('folder_link', '')
    if not image and file_path:
        image = 'https://www.dropbox.com/home' + quote(file_path.rsplit('/', 1)[0], safe='/') + '?preview=' + quote(file_path.rsplit('/', 1)[-1])
    if not folder_url and folder_path:
        folder_url = 'https://www.dropbox.com/home' + quote(folder_path, safe='/')
    return {'file_id': fid, 'folder_id': folder, 'image': image, 'folder': folder_url}


def field_group(value):
    text = str(value).lower()
    if any(s in text for s in ['dimension', 'depth', 'size']): return 'Dimensions / depth'
    if any(s in text for s in ['weight', 'mass']): return 'Weight'
    if any(s in text for s in ['material', 'finish']): return 'Material / finish'
    if any(s in text for s in ['fixing', 'mounting', 'support']): return 'Fixing'
    if any(s in text for s in ['price', 'selling']): return 'Individual price'
    if any(s in text for s in ['availability', 'lead time', 'leadtime', 'stock']): return 'Availability'
    return ''


def human(value):
    if isinstance(value, str): return value
    if isinstance(value, (int, float)): return str(value)
    if isinstance(value, list): return '\n'.join(human(v) for v in value)
    if isinstance(value, dict):
        for key in ['display', 'displayed_detail', 'proposal', 'value', 'description']:
            if value.get(key) is not None: return human(value[key])
        return '; '.join(str(k).replace('_', ' ') + ': ' + human(v) for k, v in value.items()
                         if not isinstance(v, bool) and v is not None and k not in ['path', 'sha256'])
    return ''


def statement(decision):
    return decision.get('user_statement') or decision.get('authoritative_user_evidence', {}).get('text') or decision.get('owner_evidence', {}).get('text', '')


def same_scope(decision, cid, scope):
    if decision.get('component_id') != cid: return False
    variant = decision.get('size_finish_variant_id') or decision.get('build_variant_id') or decision.get('component_layout_id')
    return (not variant and scope == 'BASE') or variant == scope


approved_ids = set()
for ledger in ['specification_decisions', 'size_finish_variant_specification_decisions', 'build_variant_decisions']:
    for item in u.get(ledger, []):
        approved_ids.update(item.get('approved_proposal_ids', []))
partial_ledgers = {'Dimensions / depth': ['dimension_decisions', 'design_size_target_decisions'],
                   'Weight': ['specification_decisions', 'size_finish_variant_specification_decisions', 'weight_decisions'],
                   'Material / finish': ['material_detail_decisions'], 'Fixing': ['fixing_detail_decisions']}
aliases = {}
for alias in p.get('catalogue_design_aliases', {}).values():
    for cid in alias.get('historical_component_ids', []): aliases[cid] = alias['current_display_name']
reviews, specifications, name_updates = [], [], {}
fixing_choice_overlays = []
weight_policy_overlays = []
seen = set()
fields = ['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability']


def context_columns(node):
    coverage = node.get('photo_coverage')
    if not isinstance(coverage, dict):
        return ['Review pending', 'Context images have not been classified for this exact scope; this does not mean they are absent.', '', '']
    vid = node.get('size_finish_variant_id', '')
    chosen = None
    if coverage.get('contextual_source_status'):
        status = coverage['contextual_source_status']
        detail = coverage['contextual_source_description']
        chosen = first(coverage.get('contextual_file_ids', []))
    elif vid == 'BR-1-GOLD-LEAF':
        chosen = coverage['room']['representative'][0]['file_id']
        status = 'Available: detail and shared family context'
        detail = '31 room presentations show a rectangular detail; full folded outline unconfirmed. Shared Gold pair room images also exist. Dedicated full-panel wider-room coverage remains unestablished.'
    elif vid == 'BR-2-GOLD-LEAF':
        chosen = next((fid for fid, item in p.get('media_coverage_observations_by_file_id', {}).items() if item.get('group_ref') == 'G033'), None)
        status = 'Available: shared family room context'
        detail = 'Dedicated individual G039 In Situ folder is empty. Gold pair room images exist as family context; full-panel individual wider-room coverage remains unestablished.'
    else:
        wider_keys = ['wider_room', 'wider_room_or_garden', 'room_context', 'garden_context', 'room_or_garden_context', 'room_setting_available', 'room_setting_reference_available', 'indoor_context_image_available', 'indoor_room_setting_established', 'outdoor_display_context_available', 'outdoor_wall_display', 'native_outdoor_workshop_context', 'workshop_context_available', 'in_situ_image_observed', 'room_display', 'context', 'in_situ']
        series_keys = ['series_arrangement', 'series', 'series_arrangement_image_available', 'series_arrangement_established', 'series_image_observed', 'series_arrangement_reference_available', 'paired_family_display_available', 'matching_finish_series_arrangement_identified', 'series_reference_available']
        wall_keys = ['on_wall', 'wall_display', 'wall_mounted_front_reference', 'single_wall_display', 'product_on_stone_wall_photo', 'wall_display_image_observed', 'wall_display_images_observed', 'outdoor_wall_display', 'standalone_outdoor_wall_display']
        kinds = []
        if any(coverage.get(k) is True for k in wider_keys): kinds.append('room/garden/workshop presentation')
        if any(coverage.get(k) is True for k in series_keys): kinds.append('series/arrangement context')
        if any(coverage.get(k) is True for k in wall_keys): kinds.append('on-wall presentation')
        if coverage.get('contextual_images_available') is True: kinds.append(coverage.get('context_image_type', 'context presentation'))
        text_context = [coverage[k] for k in ['context', 'series', 'room_context', 'room_display', 'room_or_garden_context'] if isinstance(coverage.get(k), str)]
        if kinds:
            status = 'Available: reviewed contextual depiction'
            detail = '; '.join(dict.fromkeys(kinds)) + '. Exact cast correspondence and installation provenance remain subject to the scoped review.'
        elif text_context:
            status = 'Scoped context evidence: classification pending'
            detail = ' '.join(text_context)[:450]
        elif any(k in coverage for k in wider_keys + series_keys + wall_keys):
            status = 'Not established in reviewed packet'
            detail = 'Review scope only; no whole-library absence claim. Consult the existing photo review before treating another finish or a family scene as an individual match.'
        else:
            status = 'Review pending'
            detail = 'Photo evidence exists but contextual-image coverage has not been normalised for this exact scope.'
        ids = coverage.get('contextual_file_ids', [])
        chosen = first(ids) or coverage.get('outdoor_context_reference_id') or coverage.get('room_candidate_file_id')
        if vid == 'MCP4-VERDIGRIS-RUST':
            detail = 'Complete panel on a plain wall in source003; no wider-room or series view established in the three-file folder. Scene provenance unconfirmed.'
    if chosen and chosen in assets:
        ref = references({'primary_image_id': chosen})
        detail += '\nContext file: ' + ref['file_id'] + '\nContext folder: ' + ref['folder_id']
        return [status, detail + '\nDepictions do not verify stock or installation authenticity.', ref['image'], ref['folder']]
    return [status, detail + '\nDepictions do not verify stock or installation authenticity.', '', '']


def add_review(cid, scope, node, source=None, kind='Individual review'):
    key = cid + '|' + scope
    assert key not in seen, key
    seen.add(key)
    # Some older parent and nested finish nodes share a visible scope. Project
    # the exact node that was imported, without merging their source evidence.
    node = new_working_projection_nodes.get(key,node)
    source = source or components.get(cid, {})
    name = node.get('canonical_name') or node.get('individual_listing_name') or node.get('proposed_name') or source.get('name') or cid
    if scope == 'BASE' and cid in aliases: name = aliases[cid] + ' (historical source ' + cid + ')'
    identity = node.get('identity_decision_display') or ('Owner kept this name' if node.get('identity_confirmed') else 'Proposed / unconfirmed')
    if not node: identity = 'Source register; owner review pending'
    if kind == 'Catalogue alias' and not node.get('identity_decision_display'): identity = 'Current catalogue alias; historical IDs retained'
    deferred = cid == 'BC-MIX-SPIRALS'
    if deferred: identity = 'Collection reference; individual review deferred'
    ref = references(node, source if scope == 'BASE' else {})
    proposals = node.get('specification_proposals', []) or []
    if isinstance(proposals, dict): proposals = [dict(v, field=k) if isinstance(v, dict) else {'field': k, 'display': str(v)} for k, v in proposals.items()]
    if node.get('working_specifications_approval_scope') in ['EXACT_FINISH_ALL_SIX_WORKING_VALUES', 'EXACT_FINISH_PRICE_AVAILABILITY_ONLY'] and node.get('accepted_working_specifications'):
        proposals = copy.deepcopy(proposals)
        working = {field_group(key): item for key, item in node['accepted_working_specifications'].items()}
        if not proposals:
            # Legacy structured cards need a view projection. Their original
            # source dictionaries remain unchanged in the saved model.
            proposals = [dict(copy.deepcopy(item), field=field) for field,item in working.items()]
        for proposal in proposals:
            overlay = working.get(field_group(proposal.get('field') or proposal.get('group') or proposal.get('label')), {})
            for attribute in ['display', 'basis', 'status']:
                if attribute in overlay: proposal[attribute] = overlay[attribute]
            if key in new_working_projection_nodes and overlay.get('proposal_id'):
                proposal['proposal_id'] = overlay['proposal_id']
            if cid == 'BC-BAR-WAVE' and scope == 'BASE' and proposal.get('status'):
                proposal['status'] = proposal['status'].replace('UNAPPROVED WORKING PROPOSAL','ACCEPTED WORKING SUPPORT PROPOSAL')
            if cid == 'BC-AC-TWO' and scope == 'AC-TWO-WHITE-BLACK' and field_group(proposal.get('field')) == 'Individual price':
                proposal['basis'] = 'Historical proposal used the separately accepted White working price as a comparison. Owner subsequently accepted £175 for this White and Black finish as a working proposal; a current exact-finish platform offer and costed quote remain unconfirmed. Original pre-approval wording is retained in the source dictionaries and sealed decision.'
    if not proposals and kind == 'Catalogue alias':
        proposals = [dict(v, field=k) for k, v in node.get('historical_specification_proposals', {}).items() if isinstance(v, dict)]
    by_field = {field: [] for field in fields}
    for proposal in proposals:
        field = field_group(proposal.get('field') or proposal.get('group') or proposal.get('label'))
        if field: by_field[field].append(proposal)
    own_approved = set(node.get('approved_proposal_ids', []))
    reference_disposition = p.get('working_review_reference_dispositions', {}).get(cid+'|'+scope)
    any_accepted = False
    spec_rows = []
    for field in fields:
        values, states, basis, pids = [], [], [], []
        for proposal in by_field[field]:
            detail = proposal.get('display') or proposal.get('displayed_detail') or proposal.get('proposal') or proposal.get('value')
            values.append(human(detail))
            pid = proposal.get('proposal_id', '')
            if pid: pids.append(pid)
            accepted = bool(pid and pid in approved_ids | own_approved) or proposal.get('owner_approved') is True
            if node.get('proposals_approved') is True and scope == 'BASE' and node.get('specification_approval'): accepted = True
            if node.get('proposals_approved') is True and node.get('specification_approval') and node.get('working_specifications_approval_scope') == 'EXACT_FINISH_ALL_SIX_WORKING_VALUES': accepted = True
            states.append('Owner accepted working proposal; not physically verified' if accepted else
                          str(proposal.get('source_evidence_state') or proposal.get('status') or 'Unapproved proposal / source applicability to check'))
            if accepted and node.get('working_specifications_approval_scope') in ['EXACT_FINISH_ALL_SIX_WORKING_VALUES', 'EXACT_FINISH_PRICE_AVAILABILITY_ONLY'] and proposal.get('status') and cid+'|'+scope not in new_working_projection_nodes:
                states.append(str(proposal['status']))
            if accepted and node.get('working_acceptance_basis') == 'DERIVED_FROM_STANDING_OWNER_POLICY':
                states.append('Card completed under standing owner instruction; no individual reply recorded for this batch. Earlier owner confirmations retained.' if cid == 'BC-MCP-4' and scope == 'MCP4-VERDIGRIS-RUST' else 'Working group accepted under standing instruction; fixing type subsequently owner-stated' if field == 'Fixing' and node.get('owner_fixing_type_decision') else 'Accepted under standing owner instruction; no individual reply recorded')
            any_accepted |= accepted
            evidence = proposal.get('source_evidence', {})
            basis.append(human(proposal.get('basis') or (evidence.get('basis_refs') if isinstance(evidence, dict) else '') or proposal.get('source_ref', '')))
        if cid+'|'+scope in new_working_projection_nodes:
            # Keep every source reference, but flow long citation lists as prose
            # so they fit within Excel's maximum row height.
            basis = [text.replace('\n','; ') if text.count('\n') > 12 else text for text in basis]
        if cid == 'BC-MCP-4' and scope == 'MCP4-VERDIGRIS-RUST' and field in ['Dimensions / depth','Weight','Material / finish','Fixing']:
            basis = ['Earlier field-specific reply context: '+text for text in basis]
            basis.append('Current card: all six working fields accepted under standing instruction. Earlier statements are retained; actual measurements, hardware and stock remain separately qualified.')
        owner_updates = []
        for ledger in partial_ledgers.get(field, []):
            for decision in u.get(ledger, []):
                if field == 'Weight' and ledger == 'size_finish_variant_specification_decisions' and (node.get('working_specifications_approval_scope') == 'EXACT_FINISH_PRICE_AVAILABILITY_ONLY' or node.get('working_acceptance_basis') in ['OWNER_STANDING_INSTRUCTION_APPLIED_TO_CURRENT_CARD', 'OWNER_DIRECT_EXPLICIT_KEEP', 'DERIVED_FROM_STANDING_OWNER_POLICY']):
                    continue  # Whole-card acceptance and commercial replies do not state a measured weight.
                if same_scope(decision, cid, scope) and statement(decision): owner_updates.append('Owner: ' + statement(decision))
        if owner_updates:
            values.extend(dict.fromkeys(owner_updates))
            if node.get('working_specifications_approval_scope') != 'EXACT_FINISH_ALL_SIX_WORKING_VALUES':
                states.append('Scoped owner statement; full-group approval is separate')
        if not values:
            source_key = {'Dimensions / depth': 'dimensions_available', 'Weight': 'weight_available',
                          'Material / finish': 'material_available', 'Fixing': 'fixing_available',
                          'Individual price': 'current_individual_prices'}.get(field)
            available = node.get('available', {})
            local_key = {'Dimensions / depth': 'dimensions', 'Weight': 'weight', 'Material / finish': 'material',
                         'Fixing': 'fixing_source_claim', 'Individual price': 'individual_price', 'Availability': 'availability'}[field]
            value = available.get(local_key) if isinstance(available, dict) else None
            if not value and scope == 'BASE': value = source.get(source_key, '') if source_key else ''
            values = [human(value) if value else 'Not established for this exact review scope']
            states = ['Source-register claim / applicability unconfirmed' if value else 'Missing / unconfirmed']
        if deferred: states = ['Deferred by owner for this collection']
        if field == 'Weight' and p.get('global_approximate_weight_policy'):
            output = p['weight_review_output_overlays']
            key = cid + '|' + scope
            before_weight = {'key': [cid, scope], 'before_detail': '\n'.join(dict.fromkeys(v for v in values if v)),
                             'before_state': '\n'.join(dict.fromkeys(states)), 'before_basis': '\n'.join(dict.fromkeys(v for v in basis if v))}
            override = output['scoped_overrides'].get(key)
            disposition = output['reference_dispositions'].get(key)
            if override:
                later_weight = node.get('accepted_working_specifications', {}).get('weight') if node.get('all_six_working_specification_fields_accepted') else None
                values = [later_weight['display'] if later_weight else override['display']]
                if not later_weight:
                    states = [override['status']]
                    basis = [override.get('basis', '')]
                else:
                    basis.append('Earlier policy90 weight projection retained as history; the later exact-scope accepted working value is displayed.')
                estimate = next((x for x in u.get('conditional_weight_estimate_decisions', []) if x['component_id'] == cid and x['scope'] == scope), None)
                if estimate: basis.append('Assumptions: ' + ' '.join(estimate['assumptions']))
                before_weight['disposition'] = override['disposition']
            elif disposition:
                basis.append('Weight scope: ' + disposition['scope_note'])
                before_weight['disposition'] = disposition['disposition']
            else:
                assert key in output['existing_numeric_scopes'], key
                states.append('Applicable approximate working weight accepted under global owner instruction; source conflicts and conditions retained.')
                before_weight['disposition'] = 'EXISTING_SCOPED_APPROXIMATION_ACCEPTED'
            if not disposition:
                basis.append('Owner weight instruction, 20 October 2026: accept applicable approximations and estimate missing individual weights. Actual mass, packaging, water/system weight and support loads are unverified; other fields retain their own review states.')
            if key == 'BC-CHELSEA|BASE' and output.get('current_native_metadata_exceptions'):
                basis.append('Image reference: existing 17 October replacement receipt and fresh native metadata identify current file id:cnqzTNngPVsAAAAAAA53Gw. Previous id:cnqzTNngPVsAAAAAAAyj2w remains historical. Current file revision/size agree; cached replacement original rehashed and inspected. No new original download or physical-cast certification.')
            before_weight.update(after_detail='\n'.join(dict.fromkeys(v for v in values if v)), after_state='\n'.join(dict.fromkeys(states)), after_basis='\n'.join(dict.fromkeys(v for v in basis if v)))
            weight_policy_overlays.append(before_weight)
        if field == 'Fixing' and p.get('global_fixing_choice_policy'):
            fixing_choice_overlays.append({'key': [cid, scope], 'before_detail': '\n'.join(dict.fromkeys(v for v in values if v)), 'before_state': '\n'.join(dict.fromkeys(states)), 'before_basis': '\n'.join(dict.fromkeys(v for v in basis if v))})
            values.append(p['global_fixing_choice_policy']['catalogue_display'])
            states.append('Owner instructed catalogue fixing choice; existing or historical fitted hardware remains separate')
            basis.append('Owner instruction, 20 October 2026: choose either keyhole fixing or French cleat. This does not confirm installed hardware, number, material, attachment or load rating.')
        spec_rows.append([cid, scope, name, field, '\n'.join(dict.fromkeys(v for v in values if v)),
                          '\n'.join(dict.fromkeys(states)), '\n'.join(dict.fromkeys(v for v in basis if v)),
                          ref['image'], ref['folder'], ref['file_id'], ref['folder_id'], '\n'.join(pids), ''])
    platform = 'Confirmed for this exact scope' if node.get('existing_platform_match_confirmed') is True else 'Exact platform / finish match unconfirmed'
    if scope == 'BASE' and source.get('standalone_offer_refs'): platform = 'Source offer reference(s): ' + ', '.join(source['standalone_offer_refs']) + '; applicability to check'
    spec_status = node.get('specification_status_display') or ('Some working proposals accepted; actual details still need checking' if any_accepted else 'Six specification groups need confirmation')
    if deferred: spec_status = 'Specifications deferred by owner'
    note = node.get('scope') or node.get('gaps') or node.get('photo_reference_scope') or ''
    if reference_disposition:
        identity = 'Existing design/reference identity retained; no additional sale unit established'
        spec_status = 'Reference disposition; use scoped component/finish records'
        note = reference_disposition['description']
    if node.get('working_specifications_approval_scope') == 'EXACT_FINISH_ALL_SIX_WORKING_VALUES' and node.get('root_verified_cached_thumbnail') and 'Thumbnail-only' not in human(note):
        note = human(note) + '\nThumbnail-only selected image evidence; original bytes and scene provenance remain unauthenticated.'
    if node.get('photo_coverage_summary'):
        note = human(note) + '\nPhoto coverage: ' + node['photo_coverage_summary'].replace('has31', 'has 31')
    reviews.append([cid, scope, name, kind, identity, spec_status, platform, ref['image'], ref['folder'],
                    ref['file_id'], ref['folder_id'], human(note), '', *context_columns(node)])
    specifications.extend(spec_rows)


for cid, source in components.items():
    if cid in consolidations:
        name_updates[cid] = consolidations[cid]['canonical_name'] + ' (former Concave Moon ID)'
        continue
    review = p['reviews'].get(cid, {})
    own_scope = review.get('size_finish_variant_id') or review.get('build_variant_id')
    base = review.get('canonical_design_record') or ({} if own_scope else review)
    add_review(cid, 'BASE', base, source, 'Source component record')
    if review.get('canonical_design_record'): name_updates[cid] = review['canonical_design_record']['canonical_name']
    if review.get('canonical_name') and not own_scope: name_updates[cid] = review['canonical_name']
    if cid in aliases: name_updates[cid] = aliases[cid] + ' (historical source ' + cid + ')'
for cid, review in p['reviews'].items():
    if cid in consolidations: continue
    own_scope = review.get('size_finish_variant_id') or review.get('build_variant_id')
    if cid not in components and not own_scope: add_review(cid, 'BASE', review)
    if own_scope: add_review(cid, own_scope, review, kind='Depicted finish / build review')
    for child_key, kind in [('size_finish_variants', 'Finish / size review'), ('build_variants', 'Construction review'),
                            ('component_layouts', 'Layout review'), ('source_reference_reviews', 'Source alias review')]:
        for key, child in (review.get(child_key, {}) or {}).items():
            if cid + '|' + key not in seen: add_review(cid, key, child, kind=kind)
for key, alias in p.get('catalogue_alias_reviews', {}).items():
    adapted = copy.deepcopy(alias)
    bindings = alias.get('historical_name_keep_bindings', [])
    if bindings:
        source_path = ROOT / bindings[0]['source_review_snapshot']
        assert sha(source_path) == source_path.stem
        source_files.append({'source': str(source_path), 'sha256': sha(source_path)})
        source_review = read(source_path)
        proposals = copy.deepcopy(source_review.get('specifications', {}))
        for field, item in proposals.items():
            if not isinstance(item, dict): continue
            if field == 'dimensions' and 'bordered_overall_cm' in item and item['bordered_overall_cm'] is None:
                item['display'] = 'Bordered overall dimensions unconfirmed. Historical core reference: ' + str(item.get('core_historical_reference', 'unknown')) + '. Core size is not established for this bordered depiction.'
            if field == 'weight' and 'bordered_kg' in item and item['bordered_kg'] is None:
                item['display'] = 'Bordered weight unconfirmed. Historical core reference: ' + str(item.get('historical_core_reference', 'unknown')) + '. Border mass and construction unconfirmed.'
            if field == 'material_finish' and item.get('substrate', 'not-present') is None:
                item['display'] = str(item.get('observed', 'White appearance')) + '; actual substrate and border construction unconfirmed.'
            if item.get('evidence_state'): item['source_evidence_state'] = item['evidence_state']
        for decision in u.get('size_finish_variant_specification_decisions', []):
            if decision.get('size_finish_variant_id') == key and decision.get('accepted_nominal_estimated_kg') is not None:
                item = proposals.setdefault('weight', {})
                item['display'] = 'Approximately 6 kg; rough working range 4–9 kg — owner accepted this conditional planning estimate. Assumes a 30 × 30 cm core within an approximately 35 × 35 cm bordered panel and AC730 construction. Size/material assumptions and actual mass remain unverified.'
                item['proposal_id'] = decision['approved_proposal_ids'][0]
                item['basis'] = decision['scope']
                item['source_evidence_state'] = 'OWNER_ACCEPTED_CONDITIONAL_PLANNING_ESTIMATE;ACTUAL_WEIGHT_PENDING'
        adapted['specification_proposals'] = proposals
    add_review(alias.get('catalogue_design_key', key), key, adapted, kind='Catalogue alias')
for key, node in p.get('source_design_reviews', {}).items():
    if node.get('record_kind', '').startswith('INDIVIDUAL_WHOLE_SOURCE'):
        adapted = copy.deepcopy(node)
        adapted['specification_proposals'] = adapted['specifications']
        adapted['scope'] = ('Owner kept the whole sculpture name. Face dimensions 80 × 60 cm are owner-stated; all six working fields accepted under standing instruction. Estimated depth, physical construction, stock and image provenance remain unverified.' if node.get('all_six_working_specification_fields_accepted') else 'Owner kept the whole sculpture name. Face dimensions 80 × 60 cm are owner-stated; depth and other specifications remain unapproved estimates. Physical construction, stock and image provenance remain unconfirmed.' if node.get('identity_confirmed') else 'Whole source under review. Owner-stated face size only; name, other specifications, physical construction and provenance remain unconfirmed.')
        add_review('UGR-G310', key, adapted, kind='Owner-named whole source; no BC ID' if node.get('identity_confirmed') else 'Whole-source candidate; no BC ID')

def group_specification_text(node):
    specs = node['specifications']
    dim, weight = specs['dimensions'], specs['weight']
    size = dim.get('proposal_overall_HWD_cm')
    dimension_text = ' × '.join(f'{v:g}' for v in size) + ' cm overall (H × W × depth) — unmeasured proposal' if size else 'Unconfirmed for the pictured group'
    nominal = weight.get('proposal_dry_total_kg', weight.get('proposal_dry_group_kg'))
    bounds = weight.get('conditional_range_kg')
    weight_text = ('Approximately ' + f'{nominal:g}' + ' kg' + ('; conditional range ' + '–'.join(f'{v:g}' for v in bounds) + ' kg' if bounds else '') + ' — group estimate, not weighed') if nominal is not None else 'Unconfirmed'
    material = specs['material_finish'].get('proposal')
    material_text = material + ' — hypothesis; actual material unconfirmed' if material else 'White appearance; actual casting material and finish unconfirmed'
    fixing = specs['fixing'].get('proposal')
    fixing_text = fixing + ' — mounting concept only; rear hardware and load rating unverified' if fixing else 'Unconfirmed; rear hardware not shown'
    price = specs['individual_price']
    total = price.get('proposed_complete_arrangement_gbp', price.get('proposal_complete_pictured_arrangement_gbp'))
    price_text = ('£' + format(total, ',.0f') + ' for the pictured group — unaccepted asking-price proposal') if total is not None else 'No matched individual or group price established'
    if price.get('proposed_separate_section_asking_price_range_gbp'):
        low, high = price['proposed_separate_section_asking_price_range_gbp']
        price_text += f'; £{low:,.0f}–£{high:,.0f} section range is an unallocated proposal; separate sale units are undecided'
    availability = 'Previously made — owner stated. Current stock and production capacity unconfirmed.'
    weeks = specs['availability'].get('proposed_leadtime_weeks')
    if weeks: availability += ' Made to order in ' + '–'.join(str(v) for v in weeks) + ' weeks is an unapproved proposal.'
    return '\n'.join(['Dimensions/depth: ' + dimension_text, 'Weight: ' + weight_text,
                      'Material/finish: ' + material_text, 'Fixing: ' + fixing_text,
                      'Price: ' + price_text, 'Availability: ' + availability])


groups = []
for key, node in p.get('source_design_reviews', {}).items():
    if node.get('record_kind', '').startswith('INDIVIDUAL_WHOLE_SOURCE'):
        continue
    ref = references(node)
    limits = 'No individual sale-unit or stock count established'
    if node.get('source_AI_creation_declaration_preserved'):
        limits += '. Image embeds an AI-creation declaration; signature and photo/installation authenticity are unverified.'
    elif node.get('case_level_partial_AI_resolution_preserved'):
        limits += '. Source-image origin and client-installation authenticity remain unverified.'
    if node.get('original_Fingerprint_model_relationship', '').startswith('UNCONFIRMED'):
        limits += ' Relationship to the original Fingerprint model remains unconfirmed; the original40cm measurement is not inherited.'
    duplicate = node.get('duplicate_source_image_evidence')
    if duplicate:
        limits += ' Same decoded picture pixels as historical owner-kept ' + duplicate['other_owner_kept_name'] + ' (file ' + duplicate['other_file_id'] + '; folder ' + duplicate['other_folder_id'] + '). '
        if duplicate.get('canonical_name_decision_pending'):
            limits += 'Both names retained pending canonical-name review; '
        else:
            limits += 'Owner selected canonical image-reference name: ' + duplicate['canonical_name'] + '; retained alias: ' + '; '.join(duplicate['retained_aliases']) + '. Historical label for this source: ' + node['canonical_source_name'] + '. '
        limits += 'no separate physical sculpture inferred. The differing size/weight/price proposals remain unaccepted.'
    groups.append([key, node.get('canonical_display_name', node['canonical_source_name']), 'Owner kept source name; owner says design was made' if node.get('identity_confirmed') else 'Name proposed / unconfirmed; owner says design was made',
                   'Group reference; individual component identification deferred by owner',
                   group_specification_text(node), 'All complete actual specification groups pending; estimates unaccepted',
                   ref['image'], ref['folder'], ref['file_id'], ref['folder_id'], limits, ''])
for key, node in p.get('arrangement_reviews', {}).items():
    ref = references(node)
    groups.append([key, node['canonical_name'], 'Owner kept arrangement name', 'Group / arrangement reference',
                   human(node.get('specification_proposals', {})), 'Actual arrangement specifications pending',
                   ref['image'], ref['folder'], ref['file_id'], ref['folder_id'], 'Depicted layout does not certify physical stock', ''])
for key, node in p.get('group_photo_review_dispositions', {}).items():
    ref = references({'source_asset_id': first(node.get('file_ids')), 'source_folder_id': node['folder_id']})
    groups.append([key, folders.get(node['folder_id'], {}).get('name', key), 'Group context retained', node['treatment'],
                   'Existing individual approvals retained; remaining background objects not individually identified',
                   'No new individual specification approval', ref['image'], ref['folder'], ref['file_id'], ref['folder_id'],
                   'G072 upper-shelf source-position candidate remains unconfirmed' if node['group_ref'] == 'G072' else 'Sandstone and Pewter approvals keep their exact scopes', ''])
g050 = next(x for x in u['collection_scope_decisions'] if x['group_ref'] == 'G050')
groups.append(['G050', 'Collection of sculptures', 'Owner requested collection-only treatment', 'Individual review and specifications deferred',
               'No individual specification work requested now', 'Deferred by owner', '', g050['folder_link'], '', g050['folder_id'], 'Resume only on owner request', ''])

platform_updates = []
for offer in model['platform_records']:
    item = copy.deepcopy(offer)
    binding = p.get('offer_photo_bindings', {}).get(offer['offer_ref'])
    if binding and binding.get('photo_level_match_confirmed'):
        item['image_file_id'] = binding.get('primary_file_id', item.get('image_file_id'))
        item['image_folder_id'] = binding.get('folder_id', item.get('image_folder_id'))
        item['image_state'] = 'Exact photograph correspondence verified for ' + str(binding.get('size_finish_variant_id', binding.get('component_id', ''))) + '; current account SKU not reverified'
    if item.get('image_file_id') in assets: item['image_path'] = assets[item['image_file_id']]['path']
    if any(item.get(key) != offer.get(key) for key in ['image_file_id', 'image_folder_id', 'image_state', 'image_path']):
        platform_updates.append(item)

output = ROOT / 'outputs/01a144ab-1a7c-7223-a403-73a4d53d70ff/Boldstone_Sculpture_Catalogue_Review_2026-10-20.xlsx'
result = {'as_of_utc': datetime.now(timezone.utc).isoformat(), 'source_files': source_files,
          'previous_workbook': str(previous), 'output': str(output), 'name_updates': name_updates,
          'reviews': reviews, 'specifications': specifications, 'groups': groups,
          'physical_manufacture_review_policy': p.get('physical_manufacture_review_policy'),
          'working_specification_acceptance_policy': p.get('working_specification_acceptance_policy'),
          'global_fixing_choice_policy': p.get('global_fixing_choice_policy'),
          'fixing_choice_overlays': fixing_choice_overlays,
          'global_approximate_weight_policy': p.get('global_approximate_weight_policy'),
          'weight_policy_overlays': weight_policy_overlays,
          'weight_policy_counts': {'existing_numeric': 214, 'new_conditional_estimates': 9, 'source_display_recoveries': 7, 'reference_or_deferred': 48} if p.get('global_approximate_weight_policy') else None,
          'current_reference_resolutions': [resolution] if p.get('global_approximate_weight_policy') else [],
          'platform_updates': platform_updates, 'asset_updates': [a for fid, a in assets.items() if a != source_assets[fid]],
          'identity_confirmation_counts': u['identity_confirmation_counts'],
          'specification_approval_counts': u['specification_approval_counts'],
          'dimension_confirmation_counts': u['dimension_confirmation_counts'],
          'source_dimension_decision_count': len(u.get('source_dimension_decisions', [])),
          'platform_source_counts': dict(Counter(x['platform'] for x in model['platform_records'])),
          'baseline_photo_gaps': docs['workbook_manifest']['sheets']['Photograph Gaps']['count'],
          'scope_note': 'Review rows overlap across base components, finishes, builds and aliases. Final individually buyable design / variant and physical stock counts remain unverified.'}
assert len(reviews) == len(seen) and len(specifications) == len(reviews) * 6
result['photograph_gap_links'] = []
for row in docs['workbook_manifest']['sheets']['Photograph Gaps']['values']:
    ref = references({}, {'example_file_ids': row[10], 'folder_ids': row[9]})
    result['photograph_gap_links'].append(ref)
result['additional_photograph_gaps'] = []
for variant, label in [('AC-ONE-LEFT-SANDSTONE', 'Sandstone'), ('AC-ONE-LEFT-PEWTER', 'Pewter')]:
    if variant in p.get('current_component_photograph_gaps', {}): continue
    node = p['reviews']['BC-AC-ONE']['size_finish_variants'][variant]
    ref = references(node)
    result['additional_photograph_gaps'].append({
        'values': [variant, 'BC-AC-ONE', node['canonical_name'], label,
                   'Neutral complete front view not established', 'Authenticated in situ image not established',
                   'Matching-finish series image not established', 'Workshop detail and overview; installation provenance unverified',
                   'Exact reviewed packet only. Same physical cast across detail and overview unconfirmed.',
                   ref['folder_id'], ref['file_id'], ''], 'reference': ref})
soundwave = p.get('source_design_reviews', {}).get('SOUNDWAVE-WHITE-G310003')
if soundwave and 'SOURCE-G310003' not in p.get('current_component_photograph_gaps', {}):
    ref = references(soundwave)
    result['additional_photograph_gaps'].append({
        'values': ['SOURCE-G310003', 'UGR-G310', 'Soundwave — White' if soundwave.get('identity_confirmed') else 'Soundwave — White (name pending)', 'White',
                   'Complete front depiction linked; image provenance unverified',
                   'Historical context exists; exact source003 cast correspondence unconfirmed',
                   'Optional; no fixed series established', 'Historic brochure provides design context; source003 image authentication pending',
                   'Rear/fixing and side/profile not established in the reviewed packet', ref['folder_id'], ref['file_id'], ''],
        'reference': ref})
for variant, gap in p.get('current_component_photograph_gaps', {}).items():
    if gap.get('model_locator'):
        node = p
        for part in gap['model_locator']: node = node[part]
    else:
        parent = p['reviews'][gap['component_id']]
        category = {'COMPONENT_LAYOUT':'component_layouts','BUILD':'build_variants'}.get(gap.get('review_scope'),'size_finish_variants')
        node = parent if gap.get('review_scope') == 'BASE' else parent[category][gap.get('size_finish_variant_id',variant)]
    ref = references(node)
    finish_labels = {'LEAF-CURVE-WHITE-GOLD': 'White and Gold Leaf', 'LEAF-GROWTH-WHITE': 'White', 'LEAF-GROWTH-WHITE-GOLD': 'White and Gold Leaf', 'LEAF-FORM-LF1-WHITE': 'White', 'LEAF-FORM-LF2-WHITE': 'White', 'LEAF-FORM-GOLD': 'Gold'}
    front_display = gap['front']
    if variant in ['PANEL-CURVES-BEIGE-PROCESS', 'PANEL-CURVES-MULTICOLOUR-PATINA'] and front_display.startswith('PRIMARY.'):
        front_display = 'Complete individual front linked; camera-original or edit lineage unverified.'
    result['additional_photograph_gaps'].append({
        'values': [gap.get('photo_gap_id',variant), gap['component_id'], gap['canonical_name'], finish_labels.get(variant, gap.get('finish', 'Gold Leaf')),
                   front_display, gap['room'], gap['series'], gap['evidence'], gap['missing'],
                   ref['folder_id'], ref['file_id'], ''], 'reference': ref})
for cid, gap in p.get('source_only_gap_reviews', {}).items():
    ref = references({})
    result['additional_photograph_gaps'].append({
        'values': [cid + '-SOURCE-ONLY', cid, gap['canonical_name'], 'Historical white standard; exact pictured Long finish unbound',
                   'Exact Long100×22cm front photograph not identified in this bounded review',
                   'Long size not bound to an individual room or wall photograph',
                   'Frozen Fish family group pictures exist; exact Long size remains unbound',
                   'Bounded seven groups /96asset-metadata records; maker reuses the same solo picture for Short and Long',
                   gap['evidence_needed'] + ' No absence claim; no Short dimensions or stock inherited.', '', '', ''],
        'reference': ref})
result['group_updates'] = []
for group_ref, override in p.get('catalogue_group_overrides', {}).items():
    if group_ref == 'G262':
        result['group_updates'].append({'group_ref': group_ref, 'family': override['current_family'],
            'name': override['current_name'], 'id': override['current_folder_id'], 'role': override['role'],
            'component_ids': [], 'assignment_status': 'Owner corrected family to Lava Moon; exact component and finish remain unassigned',
            'path': override['current_folder_path']})
    elif group_ref == 'G050':
        result['group_updates'].append({'group_ref': group_ref, 'role': 'Collection context',
            'assignment_status': 'Owner requested collection-only treatment; individual review and specifications deferred. Other established associations retained.'})
    elif override.get('canonical_consolidation_record') or override.get('source_identity_consolidation_record') or override.get('catalogue_finish_alias_record'):
        result['group_updates'].append({'group_ref': group_ref, 'family': override['current_family'],
            'name': override['current_name'], 'id': override['current_folder_id'], 'path': override['current_folder_path'],
            'file_count': override['file_count'], 'role': override['role'], 'component_ids': override['component_ids'],
            'assignment_status': override['assignment_status']})
result['asset_scope_overrides'] = []
for fid, override in p.get('asset_assignment_overrides', {}).items():
    if 'component_ids' in override or 'component_bindings' in override:
        ids = override.get('component_ids', [x['component_id'] for x in override.get('component_bindings', [])])
        result['asset_scope_overrides'].append({'file_id': fid, 'component_ids': list(dict.fromkeys(ids))})
result['source_cell_updates'] = []
for cid, gap in p.get('source_only_gap_reviews', {}).items():
    table = docs['workbook_manifest']['sheets']['Individual Sculptures']
    for index, row in enumerate(table['values']):
        if row[0] != cid: continue
        note = str(row[16] or '') + '\nBounded source reconciliation: seven groups /96asset metadata checked; maker reuses picture45 for Short70×15 and Long100×22. Exact Long image, file/folder IDs and platform offer remain unbound; this does not establish absence. ' + gap['evidence_needed']
        for column, value in [(3, 'Source-only100×22cm option; exact Dropbox photograph remains unbound'),
                              (4, 'Locate a labelled/measured Long reference before completing the standalone listing; owner states all sculptures made'),
                              (16, note)]:
            result['source_cell_updates'].append({'sheet': 'Individual Sculptures', 'row': table['first'] + index, 'column': column, 'value': value})
result['canonical_consolidations'] = consolidations
result['catalogue_alias_rows'] = []
for key, alias in p.get('duplicate_source_image_reviews', {}).items():
    if alias.get('canonical_name_decision_pending'): continue
    result['catalogue_alias_rows'].append([key, alias['canonical_name'], '; '.join(alias['retained_aliases']),
        'Owner-selected canonical name for two identical-pixel source images only; not a physical mould or stock merge. Both stable file/folder references remain in Group References.',
        'Both historical name decisions and conflicting unaccepted size/weight/price drafts retained', alias['owner_name_decision']])
result['source_identity_consolidations'] = p.get('source_identity_consolidations', {})
for alias in result['source_identity_consolidations'].values():
    result['catalogue_alias_rows'].append([alias['canonical_component_id'], 'G233 source002', alias['retain_as_legacy_source_alias'],
        'Owner confirmed same design and catalogue name: Chelsea Moonwave. One canonical design; no separate Moon Ripple listing. Exact source002 only; physical cast, mould, stock and250×100 size applicability unconfirmed. Source file ' + alias['primary_file_id'] + '; comparison file ' + alias['comparison_file_id'],
        'Both image/folder references retained; six source-specific specification groups pending', alias['approval_record']])
if 'BC-CONCAVE' in consolidations:
    consolidation = consolidations['BC-CONCAVE']
    result['catalogue_alias_rows'].insert(0, ['BC-MCP-4', 'MCP4', 'Concave Moon / BC-CONCAVE',
        'Former catalogue name and source ID; use Moon Crater Phase 4. This is a design alias, not a physical mould or stock merge.',
        'Finish-specific specifications retained', consolidation['approval_record']])
    def edit_source(sheet, index, column, value):
        table = docs['workbook_manifest']['sheets'][sheet]
        if table['values'][index][column] != value:
            result['source_cell_updates'].append({'sheet': sheet, 'row': table['first'] + index, 'column': column, 'value': value})
    def append_note(value, note):
        return (str(value or '') + '\n' + note).strip()
    canonical_note = 'Concave Moon is a former name/source ID for Moon Crater Phase 4 (BC-MCP-4). No separate Concave Moon listing. Finish-specific claims and offer conflicts remain scoped.'
    for sheet in ['Individual Sculptures', 'Listing Actions']:
        for i, row in enumerate(docs['workbook_manifest']['sheets'][sheet]['values']):
            if row[0] == 'BC-CONCAVE':
                edit_source(sheet, i, 2, 'Moon Crater Phase')
                edit_source(sheet, i, 3, 'Historical alias; use BC-MCP-4')
                edit_source(sheet, i, 4, 'Use canonical BC-MCP-4 finish records. Historical source ID only; do not create a separate Concave Moon listing.')
                edit_source(sheet, i, 16 if sheet == 'Individual Sculptures' else 9,
                            append_note(row[16 if sheet == 'Individual Sculptures' else 9], canonical_note))
    for sheet, cid_column, name_column in [('Component BOM', 1, 2), ('Proposed Specifications', 0, 1), ('Photograph Gaps', 1, 2)]:
        for i, row in enumerate(docs['workbook_manifest']['sheets'][sheet]['values']):
            if row[cid_column] == 'BC-CONCAVE':
                edit_source(sheet, i, cid_column, 'BC-MCP-4')
                edit_source(sheet, i, name_column, 'Moon Crater Phase 4')
                if sheet == 'Component BOM': edit_source(sheet, i, 20, append_note(row[20], canonical_note))
                if sheet == 'Photograph Gaps': edit_source(sheet, i, 8, append_note(row[8], canonical_note))
    moved_files = p['live_dropbox_metadata_overlays']['MCP4_CONSOLIDATION']['files']
    for i, row in enumerate(docs['workbook_manifest']['sheets']['Mixed Image Links']['values']):
        if row[0] == 'BC-CONCAVE': edit_source('Mixed Image Links', i, 0, 'BC-MCP-4')
        if row[1] in moved_files:
            ref = references({'source_asset_id': row[1]})
            edit_source('Mixed Image Links', i, 2, ref['folder_id'])
            edit_source('Mixed Image Links', i, 5, moved_files[row[1]]['path_display'])
    for i, row in enumerate(docs['workbook_manifest']['sheets']['Photograph Gaps']['values']):
        fid = first(row[10])
        if fid in moved_files:
            ref = references({'source_asset_id': fid})
            replacements = {'id:cnqzTNngPVsAAAAAAAyiJQ': 'id:cnqzTNngPVsAAAAAAAyiqw',
                            'id:cnqzTNngPVsAAAAAAAyiKA': 'id:cnqzTNngPVsAAAAAAAyjLg'}
            current_ids = list(dict.fromkeys(replacements.get(x, x) for x in str(row[9]).split('\n') if x))
            if ref['folder_id'] not in current_ids: current_ids.insert(0, ref['folder_id'])
            ref['current_folder_ids_label'] = '\n'.join(current_ids)
            # Current links and displayed parent agree; the original parent IDs remain in the source workbook and relocation receipt.
            result['photograph_gap_links'][i] = ref
    for i, row in enumerate(docs['workbook_manifest']['sheets']['Unresolved Media']['values']):
        if row[2] in p['catalogue_group_overrides'] and p['catalogue_group_overrides'][row[2]].get('canonical_consolidation_record'):
            edit_source('Unresolved Media', i, 7, 'Canonical design MCP4. Finish-specific match, specifications and physical origin remain separately reviewed.')
(HERE / 'refresh-data.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'review_scope_rows': len(reviews), 'specification_rows': len(specifications), 'group_references': len(groups),
                  'platform_photo_updates': len(platform_updates), 'asset_path_updates': len(result['asset_updates']),
                  'platform_source_counts': result['platform_source_counts'], 'final_sculpture_count': 'UNVERIFIED'}))
