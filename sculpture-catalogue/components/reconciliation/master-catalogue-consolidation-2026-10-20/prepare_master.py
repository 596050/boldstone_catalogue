"""Consolidate accepted catalogue data without changing original evidence."""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
FIELDS = ['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability']
digest = lambda raw: hashlib.sha256(raw).hexdigest()
read = lambda p: json.loads(p.read_text())
write = lambda p, obj: p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def unique(items):
    return list(dict.fromkeys(x for x in items if x))

def native_path(value):
    return '/' + str(value).split('//', 1)[-1].strip('/')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--four-packet', required=True)
    parser.add_argument('--four-seal', required=True)
    args = parser.parse_args()
    manifest = read(HERE / 'input-manifest.json')
    for key, source in [('four_record_completion', Path(args.four_packet)), ('four_record_seal', Path(args.four_seal))]:
        raw = source.read_bytes()
        dest = HERE / 'inputs' / (key + '.json')
        if dest.exists():
            assert dest.read_bytes() == raw, key + ' input changed after freeze'
        else:
            dest.write_bytes(raw)
        manifest[key] = {'source': str(source.resolve()), 'snapshot': str(dest), 'sha256': digest(raw)}
    source = lambda key: read(Path(manifest[key]['snapshot']))
    before = source('count_register')
    g = copy.deepcopy(before)
    packet, seal = source('four_record_completion'), source('four_record_seal')
    assert 'PASS' in seal['status']
    assert len(packet['records']) == 4
    products = {x['product_id']: x for x in g['options']}
    applied = []
    for record in packet['records']:
        target = products[record['product_id']]
        assert {k: target.get(k) for k in record['before_target']} == record['before_target'], record['name'] + ' before-target mismatch'
        protected = {k: copy.deepcopy(target.get(k)) for k in ['product_id', 'canonical_key', 'name', 'canonical_component_id', 'option_family_id', 'image_url', 'folder_url', 'file_id', 'folder_id', 'source_scopes']}
        target['specifications'] = copy.deepcopy(record['specifications'])
        target.update(copy.deepcopy(record['after_flags']))
        target['remaining_evidence_gaps'] = copy.deepcopy(record['remaining_evidence_gaps'])
        target['working_completion_source'] = manifest['four_record_completion']
        assert all(target.get(k) == v for k, v in protected.items())
        applied.append(target['product_id'])

    # Recover real proposal text from the saved family records. This changes no
    # owner acceptance or physical-verification state.
    recovered = []
    wc_labels = {'PROPOSAL_UNCONFIRMED': 'Working proposal', 'ESTIMATE_UNCONFIRMED': 'Working estimate',
                 'MATERIAL_GUESS_FINISH_VISUAL': 'Proposed material and visible finish'}
    for x in g['options']:
        if x.get('option_family_id') != 'BC-WALL-CIRCLE':
            continue
        for field, detail in x['specifications'].items():
            raw = detail.get('source_field_record', {})
            if raw.get('proposal') and detail['display'] == raw.get('status'):
                detail['prior_status_only_display'] = detail['display']
                detail['display'] = wc_labels.get(raw['status'], 'Working proposal') + ': ' + raw['proposal']
                detail['display_recovery_basis'] = 'Saved proposal text; existing family working approval and uncertainty retained'
                recovered.append({'product_id': x['product_id'], 'field': field, 'source_status': raw['status']})
    assert len(recovered) == 36

    # Construct a current-path index from verified stable-ID overlays. Original
    # assertions, source offers and historic names stay unchanged.
    model = source('source_component_model')
    assets = {x['id']: x for x in model['assets']}
    paths = {native_path(x['path']): x['id'] for x in model['assets']}
    current_files, current_folders = {}, {}
    for move in g['current_link_overlay']['moved_file_replacements']:
        current_files[move['file_id']] = {'file_id': move['file_id'], 'folder_id': move['current_folder_id'],
                                          'image_url': move['current_image_url'], 'folder_url': move['current_folder_url']}
        paths[native_path(move['historical_file_path'])] = move['file_id']
        paths[native_path(move['current_file_path'])] = move['file_id']
    for folder in g['current_link_overlay']['folder_replacements']:
        current_folders[folder['deleted_folder_id']] = {'folder_id': folder['current_folder_id'], 'folder_url': folder['current_folder_url']}
    rename = read(Path(g['input_manifest']['family_rename_overlay']['snapshot']))
    ammonite = source('ammonite_current_paths')
    assert ammonite['status'] == 'PASS_CURRENT_PATH_OVERLAY'
    assert source('ammonite_verification')['status'] == 'PASS'
    for overlay in [rename, ammonite]:
        folders = {native_path(x['current_display_path']): x for x in overlay['objects'] if x['object_type'] == 'folder'}
        for obj in overlay['objects']:
            if obj['object_type'] == 'folder':
                current_folders[obj['file_id']] = {'folder_id': obj['file_id'], 'folder_url': obj['current_native_url']}
            else:
                parent = folders[native_path(obj['current_display_path']).rsplit('/', 1)[0]]
                current_files[obj['file_id']] = {'file_id': obj['file_id'], 'folder_id': parent['file_id'],
                                                'image_url': obj['current_native_url'], 'folder_url': parent['current_native_url']}
                paths[native_path(obj['old_display_path'])] = obj['file_id']
                paths[native_path(obj['current_display_path'])] = obj['file_id']

    folder_paths = {native_path(x['path']): x['id'] for x in model['groups']}
    for overlay in [rename, ammonite]:
        for obj in overlay['objects']:
            if obj['object_type'] == 'folder':
                folder_paths[native_path(obj['old_display_path'])] = obj['file_id']
                folder_paths[native_path(obj['current_display_path'])] = obj['file_id']
    for folder in g['current_link_overlay']['folder_replacements']:
        folder_paths[native_path(folder['historical_folder_path'])] = folder['deleted_folder_id']
        folder_paths[native_path(folder['current_folder_path'])] = folder['current_folder_id']

    def url_path(url):
        parsed = urlparse(url)
        if not parsed.netloc.endswith('dropbox.com'):
            return ''
        path = unquote(parsed.path)
        for prefix in ['/home', '/preview']:
            if path.startswith(prefix + '/'):
                path = path[len(prefix):]
                break
        preview = parse_qs(parsed.query).get('preview', [])
        return path.rstrip('/') + '/' + preview[0] if preview else path

    def resolve(file_id='', folder_id='', image_url='', folder_url=''):
        file_id = file_id or paths.get(url_path(image_url), '')
        folder_id = folder_id or folder_paths.get(url_path(folder_url), '')
        if file_id in current_files:
            return copy.deepcopy(current_files[file_id])
        if folder_id in current_folders:
            f = current_folders[folder_id]
            name = assets.get(file_id, {}).get('name')
            return {'file_id': file_id, 'folder_id': f['folder_id'], 'folder_url': f['folder_url'],
                    'image_url': f['folder_url'] + '?preview=' + quote(name, safe='') if name else image_url}
        return {'file_id': file_id, 'folder_id': folder_id or assets.get(file_id, {}).get('folder_id', ''),
                'image_url': image_url, 'folder_url': folder_url}

    def update(record, file_id='', folder_id=''):
        old = {k: record.get(k, '') for k in ['file_id', 'folder_id', 'image_url', 'folder_url']}
        cur = resolve(file_id or old['file_id'], folder_id or old['folder_id'], old['image_url'], old['folder_url'])
        if any(cur[k] != old[k] for k in old):
            record['pre_master_display_reference'] = old
            record.update(cur)
        return cur

    prepared = source('prepared_product_source')
    offer_coverage = {x['offer_ref']: x for x in prepared['source_offer_coverage']}
    for x in g['options']:
        update(x)
        if x.get('context_image_url'):
            cur = resolve(image_url=x['context_image_url'], folder_url=x.get('context_folder_url', ''))
            x['context_image_url'], x['context_folder_url'] = cur['image_url'], cur['folder_url']
        x['related_platform_offer_refs'] = [o['offer_ref'] for o in prepared['source_offer_coverage'] if x['product_id'] in o.get('related_product_ids', [])]
        x['source_supported_platform_scope_refs'] = [o['offer_ref'] for o in prepared['source_offer_coverage'] if x['product_id'] in o.get('exact_supported_target_ids', [])]
        if x.get('option_family_id') == 'BC-WALL-CIRCLE':
            x['related_platform_offer_refs'] = unique(x['related_platform_offer_refs'] + ['O001'])
        elif x['product_id'] in applied and x.get('canonical_component_id'):
            related = [o['offer_ref'] for o in g['source_offer_edges'] if any(x['canonical_component_id'] in member['canonical_component_targets'] for member in o['members'])]
            x['related_platform_offer_refs'] = unique(x['related_platform_offer_refs'] + related)
        x['platform_scope_note'] = ('Preserved source-to-review-scope crosswalk; exact current specimen match unverified'
                                    if x['source_supported_platform_scope_refs'] else
                                    'Related source association only; exact individual finish, size and offer match unresolved' if x['related_platform_offer_refs'] else
                                    'No exact current platform offer mapped to this individual option')
        if x.get('option_family_id') == 'BC-WALL-CIRCLE':
            x['platform_scope_note'] = 'Existing Wall Circle parent product; exact native pattern, diameter and lighting aliases to this visual entry remain unresolved'
        elif x['canonical_key'].startswith(('BC-BONE-1|', 'BC-BONE-2|')):
            x['platform_scope_note'] = 'Existing Bone Spiral set associated through its source component list; exact current individual offer remains unresolved'
        x['master_fields'] = {}
        for field in FIELDS:
            f = x['specifications'][field]
            assert f['working_accepted'] and f['display']
            current = f.get('working_completion_overlay', {}).get('prepared_source_field') or f.get('scoped_current_working_overlay') or f.get('source_field_record') or {}
            original = f.get('assertions', [])
            if f.get('working_completion_overlay'):
                state = 'Accepted working description under the owner instruction; actual specification unverified'
            elif f.get('scoped_current_working_overlay'):
                state = 'Accepted scoped working correction; actual specification and current quote unverified'
            elif f.get('source_field_record'):
                source_state = current.get('status') or current.get('evidence_level')
                state = {'PROPOSAL_UNCONFIRMED': 'Kept working proposal; applicability to this pattern remains unconfirmed',
                         'ESTIMATE_UNCONFIRMED': 'Kept approximate working weight; not measured for this pattern',
                         'MATERIAL_GUESS_FINISH_VISUAL': 'Material remains a working guess; finish described from the image'}.get(source_state, str(source_state or 'Kept working family description with existing uncertainty'))
            else:
                state = '\n'.join(unique(y.get('state') for y in original))
            basis = unique([str(current[k]) for k in ['basis', 'limits', 'needs_confirmation', 'estimate_caution'] if current.get(k)])
            basis.extend(unique(y.get('basis') for y in original))
            refs = current.get('basis_refs', [])
            if current.get('basis_refs'):
                ref_labels = [v if isinstance(v, str) else str(v.get('source_ref') or v.get('ref') or v.get('decision_id') or v.get('source_id') or v.get('description') or ('Owner decision ' + v['json_locator'] if v.get('json_locator') else 'Scoped source reference')) for v in refs]
                basis.append('Source references: ' + ', '.join(ref_labels))
            display = f['display']
            if field == 'Fixing' and not all(word in display.lower() for word in ['keyhole', 'french cleat']):
                display = 'Offered fixing choice: ' + ' or '.join(x['offered_fixing_choices']) + '.\nSource / installed detail: ' + display
            x['master_fields'][field] = {'display': display, 'state': state, 'basis': '\n'.join(unique(basis)),
                                         'working_recorded': 1, 'physical_verification': 0,
                                         'source_scopes': unique(y.get('source_scope') for y in original) or x['source_scopes'],
                                         'proposal_ids': unique(y.get('proposal_id') for y in original) + ([current['proposal_id']] if current.get('proposal_id') else []),
                                         'source_references': copy.deepcopy(refs),
                                         'prior_display': f.get('prior_working_display') or f.get('prior_status_only_display') or ''}
        x['six_working_fields_recorded'] = all(f['working_recorded'] for f in x['master_fields'].values())
        x['working_specification_status'] = 'COMPLETE_SIX_WORKING_FIELDS'

    product_index = {x['product_id']: x for x in g['options']}
    association_overlays = {}
    for ref in ['O001', 'O034']:
        ids = [x['product_id'] for x in g['options'] if ref in x['related_platform_offer_refs']]
        association_overlays[ref] = {'related_option_ids': ids,
                                     'mapping_state': ('Wall Circle parent family and seven kept visual entries; exact native aliases unresolved' if ref == 'O001' else
                                                       'Source set associated with two identified Bone Spiral panels; exact individual offers unresolved'),
                                     'scope_note': ('Seven approved visual entries and 144 native combinations are preserved as overlapping source layers.' if ref == 'O001' else
                                                    'Both panels are individual catalogue records. The set SKU and set totals are retained at set scope.'),
                                     'exact_individual_match_upgraded': False,
                                     'basis': 'Existing parent/source-BOM association and the accepted current identity register'}
    assert len(association_overlays['O001']['related_option_ids']) == 7
    assert len(association_overlays['O034']['related_option_ids']) == 2
    for component in g['components']:
        first = product_index[component['option_ids'][0]]
        for key in ['image_url', 'folder_url', 'file_id', 'folder_id']:
            component[key] = first[key]
    for x in g['arrangement_context_references'] + g['aliases'] + g['exceptions'] + g['source_review_reconciliation']:
        update(x)
    for offer in g['source_offer_edges']:
        if offer.get('current_primary_reference'):
            update(offer['current_primary_reference'])
    # source_sets and source_offer_edges were serialized copies; update both.
    for offer in g['source_sets']:
        if offer.get('current_primary_reference'):
            update(offer['current_primary_reference'])
    for row in g['exceptions']:
        if row['candidate_id'] in ['GAP-BC-CR-RING', 'GAP-BC-FFL-1']:
            cid = row['candidate_id'].removeprefix('GAP-')
            x = next(x for x in g['options'] if x['canonical_key'] == cid + '|BASE')
            row['required_information'] = x['readiness_note'] + ' Photo/identity gaps: ' + '; '.join(str(v) for v in x.get('remaining_evidence_gaps', []))
            row['working_specifications_status'] = 'Six working fields recorded; photo and actual-specification gaps retained'

    original_refs = []
    for row in g['original_review_specification_assertions']:
        original_refs.append(resolve(row[9], row[10], row[7], row[8]))
    summary = copy.deepcopy(g['summary'])
    summary.update(current_option_records=len(g['options']), current_field_groups=len(g['options']) * 6,
                   options_with_six_working_fields=sum(x['six_working_fields_recorded'] for x in g['options']),
                   four_record_working_completions=len(applied), saved_wall_circle_proposal_displays_restored=len(recovered),
                   current_ammonite_path_objects=len(ammonite['objects']))
    assert len(g['components']) == 111 and len(g['options']) == 184
    assert summary['options_with_six_working_fields'] == 184
    assert len({x['product_id'] for x in g['options']}) == 184
    assert sum(bool(x.get('file_id')) for x in g['options']) == 183
    assert g['original_review_specification_assertions'] == before['original_review_specification_assertions']
    assert all(x['physical_specifications_verified'] is False for x in g['options'])
    assert not next(x for x in g['options'] if x['canonical_key'] == 'BC-FFL-1|BASE')['file_id']
    g.update(schema='boldstone.consolidated-master-catalogue.v1', created_utc=datetime.now(timezone.utc).isoformat(),
             summary=summary, master_input_manifest=manifest, source_platform_offer_coverage=prepared['source_offer_coverage'],
             original_specification_current_references=original_refs,
             master_working_completion={'packet': manifest['four_record_completion'], 'seal': manifest['four_record_seal'], 'option_ids': applied},
             wall_circle_display_recoveries=recovered,
             master_platform_association_overlays=association_overlays,
             latest_ammonite_current_paths={'source': manifest['ammonite_current_paths'], 'summary': ammonite['summary']})
    write(HERE / 'input-manifest.json', manifest)
    write(HERE / 'canonical-master-register.json', g)
    write(HERE / 'data-reconciliation.json', {'status': 'PASS', 'summary': summary,
                                             'all_original184_option_ids_and_names_preserved': [(x['product_id'], x['name']) for x in g['options']] == [(x['product_id'], x['name']) for x in before['options']],
                                             'all1668_original_specification_rows_unchanged': True,
                                             'no_new_identity_or_physical_verification_events': True})
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
