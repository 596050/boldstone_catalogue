"""Independent exact-answer, field-preservation and workbook delta audit."""
from pathlib import Path
import collections, copy, datetime, decimal, hashlib, json, posixpath, re, zipfile
from xml.etree import ElementTree as E

Q = Path(__file__).resolve().parent
F = Q / 'frozen-inputs'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks = collections.Counter(); failures = []

def check(ok, category, context=''):
    checks[category] += 1
    if not ok: failures.append({'category': category, 'context': str(context)[:1200]})

manifest = read(Q / 'frozen-input-manifest.json')
for p, h in manifest['protected_published_files'].items():
    check(sha(p) == h, 'published_baseline_unchanged_start', p)
for p, item in manifest['inputs'].items():
    check(sha(item['frozen_copy']) == item['sha256'], 'frozen_candidate_input_hash', p)

old = read(F / 'baseline-master_register'); new = read(F / 'canonical-master-register.json')
old_options = {x['product_id']: x for x in old['options']}
options = {x['product_id']: x for x in new['options']}
FF = 'BSI-04D6E8690F30'; FFS = 'BSI-FE10273D3655'
wall_ids = ['BSI-CCB6CA396E9C', 'BSI-22DA74B2107E', 'BSI-1B20DCA291BB']
allowed = {FF, FFS, *wall_ids}
actual_changed = {k for k in options if options[k] != old_options[k]}
check(set(options) == set(old_options) and len(options) == 189, '189_retained_option_records')
check({k for k,v in options.items() if v['counted_as_individual_option']} == {k for k,v in old_options.items() if v['counted_as_individual_option']} and sum(x['counted_as_individual_option'] for x in options.values()) == 188, '188_active_option_set_unchanged')
check(actual_changed == allowed, 'only_five_exact_option_records_changed', actual_changed)
for k in options:
    if k not in allowed: check(options[k] == old_options[k], 'other_full_option_records_unchanged', k)

packets = read(F / 'approved-packets.json')
raw = {x['turn_id']: x for x in read(Q / 'raw-owner-message-records.json')['records']}
decisions = {}
for packet in packets:
    check(sha(packet['seal']) == packet['seal_sha256'], 'owner_answer_seal_hash', packet['decision_id'])
    seal = read(packet['seal'])
    members = seal.get('files', {})
    members = [{'path': p, 'sha256': h} for p,h in members.items()] if isinstance(members,dict) else members
    for item in members:
        p = Path(item['path']); p = p if p.is_absolute() else Path(packet['seal']).parent / p
        check(sha(p) == item['sha256'], 'owner_seal_member_hash', p)
    check(sha(packet['answer_path']) == packet['answer_sha256'], 'exact_answer_file_hash', packet['decision_id'])
    answer = read(packet['answer_path']); decisions[packet['decision_id']] = answer
    source = raw.get(answer['owner_message_provenance']['turn_id'], {})
    check(source.get('role') == 'user' and source.get('text') == packet['owner_answer_verbatim'] == answer['owner_answer_verbatim'], 'exact_user_turn_and_verbatim_reply', packet['decision_id'])
    check(packet['accepted_relationship'] == answer['accepted_relationship'], 'accepted_relationship_exact_packet_copy', packet['decision_id'])
check(set(decisions) == {'LEGACY-FFL1-FFS2-RELIEF','WC-03-PATTERN','WC-06-PATTERN','WC-07-PATTERN'}, 'four_exact_answer_decisions')
for packet in packets:
    answer = decisions[packet['decision_id']]
    pid = FF if packet['decision_id'].startswith('LEGACY') else answer['accepted_relationship']['product_id']
    resolution = options[pid]['current_owner_identity_resolution' if pid == FF else 'current_owner_pattern_resolution']
    for k in ['decision_id','owner_answer_verbatim','owner_message_provenance']:
        check(resolution[k] == answer[k], 'candidate_exact_answer_provenance', (pid,k))
    check(resolution['seal_sha256'] == packet['seal_sha256'] and resolution['answer_sha256'] == packet['answer_sha256'], 'candidate_answer_hash_binding', pid)
    if pid != FF:
        check(options[pid]['owner_confirmed_pattern_name'] == answer['accepted_relationship']['pattern_name'], 'exact_owner_pattern_name', pid)
        check(resolution['native_pattern_or_variant_id_assigned'] is None and options[pid]['canonical_component_id'] == old_options[pid]['canonical_component_id'], 'pattern_name_without_native_variant_or_new_component', pid)
        for key in ['exact_current_configuration_certified','exact_current_option_configuration_match_verified']:
            check(options[pid]['current_listing_reconciliation'][key] == old_options[pid]['current_listing_reconciliation'][key], 'native_configuration_flags_not_promoted', (pid,key))
        check(options[pid]['current_listing_resolution']['exact_current_physical_or_all_six_field_configuration_certified'] is False, 'pattern_not_physical_certification', pid)
check(options[wall_ids[0]]['name'] == old_options[wall_ids[0]]['name'], 'Pale_Blue_name_unchanged')
check(options[wall_ids[1]]['name'] == 'Wall Circle — Azure Blue and White Marbled' and options[wall_ids[2]]['name'] == 'Wall Circle — Brass with World Colours', 'two_exact_display_renames')
check(options[FF]['canonical_component_id'] == options[FFS]['canonical_component_id'] == 'BC-FFS-2', 'FFL1_exact_existing_FFS2_design')
check(options[FF]['owner_confirmed_design_reference']['product_id'] == FFS and options[FF]['owner_confirmed_design_reference']['file_id'] == old_options[FFS]['file_id'], 'FFL1_shared_design_reference_scope')
for pid, item in options.items():
    for key in ['file_id','folder_id','image_url','folder_url','context_file_id','context_folder_id','context_image_url','context_folder_url']:
        check(item.get(key) == old_options[pid].get(key), 'all_selected_image_and_folder_fields_unchanged', (pid,key))
    for key in ['in_situ','series']:
        check(item['photo_coverage'].get(key) == old_options[pid]['photo_coverage'].get(key), 'all_context_and_series_photo_policies_unchanged', (pid,key))
check(options[FF]['file_id'] == options[FF]['image_url'] == '' and options[FF]['photo_coverage']['individual'] == 'Shared design reference', 'FFL1_no_selected_primary_promotion')

wording = read(F / 'identity-wording-field-changes.json')
word_map = {(x['option_id'],x['field']): x for x in wording}
unchanged_fields = 0
for pid, item in options.items():
    for label, field in item['master_fields'].items():
        before = old_options[pid]['master_fields'][label]
        if (pid,label) in word_map:
            expected = word_map[(pid,label)]
            check(before == expected['before'] and field == expected['after'], 'three_exact_wording_field_objects', label)
            delta = {k for k in set(before)|set(field) if before.get(k) != field.get(k)}
            check(pid == FF and delta <= {'display','basis'}, 'wording_changes_only_display_or_basis', (pid,label,delta))
            check(re.findall(r'\d+(?:\.\d+)?',before['display']) == re.findall(r'\d+(?:\.\d+)?',field['display']), 'wording_display_numeric_tokens_unchanged', label)
            check(field['state'] == before['state'] and field['physical_verification'] == before['physical_verification'], 'wording_states_and_physical_flags_unchanged', label)
        else:
            check(field == before, 'all_other_full_working_field_objects_unchanged', (pid,label)); unchanged_fields += 1
check(len(word_map) == 3 and unchanged_fields == 1131, '3_wording_plus_1131_identical_fields')
check({x['component_id'] for x in old['components']} == {x['component_id'] for x in new['components']} and len(new['components']) == 112, '112_retained_component_IDs')
projection = read(F / 'working-design-group-projection.json')
check(projection['grouped_working_design_identity_count'] == 110 and projection['retained_component_identity_record_count'] == 112 and projection['active_individual_finish_option_count'] == 188, '188_112_110_projection_counts')
check(projection['component_id_to_working_group'] == read(F / 'baseline-group_projection')['component_id_to_working_group'], 'existing_component_working_groups_unchanged')
coverage = read(F / 'image-coverage-current.json')
check(coverage['counts']['in_situ_statuses']['No verified image'] == 22 and coverage['counts']['series_statuses']['No verified image'] == 1, '22_plus_1_photography_gaps_unchanged')
summary = read(F / 'import-summary.json')
check(summary['remaining_owner_decision_ids'] == [] and summary['new_selected_primary_images'] == summary['new_exact_platform_matches'] == summary['new_physical_measurements'] == 0, 'four_decisions_complete_without_scope_promotion')

legacy = options[FF].get('current_legacy_identity_disposition', {})
check(legacy.get('same_as_FFS2_not_assumed') is not True and 'Identify whether historical FFL1' not in legacy.get('next_action',''), 'current_FFL1_disposition_not_stale', legacy)
check(options[FF].get('unbound_identity') is not True or options[FF].get('unbound_identity_scope') in {'PHOTO_ONLY','SELECTED_PHOTO_ONLY'}, 'current_FFL1_unbound_flag_explicitly_photo_only', options[FF].get('unbound_identity'))

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PR = '{http://schemas.openxmlformats.org/package/2006/relationships}'
def canon(e, relationships=None, ignore_link_display=False):
    attrs = dict(e.attrib)
    if relationships is not None and REL+'id' in attrs:
        attrs[REL+'id'] = repr(relationships.get(attrs[REL+'id'], ('UNRESOLVED',attrs[REL+'id'])))
    if ignore_link_display and e.tag == NS+'hyperlink': attrs.pop('display',None)
    return (e.tag,tuple(sorted(attrs.items())),e.text.strip() if e.text and e.text.strip() else '',tuple(canon(x,relationships,ignore_link_display) for x in e))
def relationship_semantics(z, part):
    if part not in z.namelist(): return {}
    return {x.get('Id'):tuple(sorted((k,v) for k,v in x.attrib.items() if k != 'Id')) for x in E.fromstring(z.read(part))}
def value(c, strings):
    t = c.get('t'); v = c.find(NS+'v')
    if t == 'inlineStr': return ''.join(x.text or '' for x in c.iter(NS+'t'))
    if t == 's': return strings[int(v.text)] if v is not None else None
    if v is None or v.text is None: return None
    if t == 'b': return v.text == '1'
    if t in {'str','e','d'}: return v.text
    return decimal.Decimal(v.text)
def workbook(p):
    z = zipfile.ZipFile(p); strings=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        strings=[''.join(t.text or '' for t in x.iter(NS+'t')) for x in E.fromstring(z.read('xl/sharedStrings.xml'))]
    w = E.fromstring(z.read('xl/workbook.xml'))
    rels = {x.get('Id'):x.get('Target') for x in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheets={}; vals={}; formulas={}; styles={}; layout={}; hyperlinks={}; displays={}
    for sheet in w.find(NS+'sheets'):
        target=rels[sheet.get(REL+'id')]
        target=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl',target))
        name=sheet.get('name'); root=E.fromstring(z.read(target)); sheets[name]=target
        rp=posixpath.join(posixpath.dirname(target),'_rels',posixpath.basename(target)+'.rels')
        links=relationship_semantics(z,rp)
        for c in root.findall('.//'+NS+'sheetData/'+NS+'row/'+NS+'c'):
            k=(name,c.get('r')); vals[k]=value(c,strings); styles[k]=c.get('s')
            f=c.find(NS+'f')
            if f is not None: formulas[k]=canon(f)
        hyperlinks[name]=collections.Counter((tuple(sorted((k,v) for k,v in x.attrib.items() if k not in {REL+'id','display'})),links.get(x.get(REL+'id'))) for x in root.findall('.//'+NS+'hyperlink'))
        displays.update({(name,x.get('ref')):x.get('display') for x in root.findall('.//'+NS+'hyperlink')})
        skeleton=copy.deepcopy(root)
        for c in skeleton.findall('.//'+NS+'sheetData/'+NS+'row/'+NS+'c'):
            c.attrib.pop('t',None)
            for child in list(c):
                if child.tag in {NS+'v',NS+'is',NS+'f'}: c.remove(child)
        layout[name]=canon(skeleton,links,True)
    return z,w,sheets,vals,formulas,styles,layout,hyperlinks,displays

a=workbook(F/'baseline-master_workbook'); b=workbook(F/'master-workbook.pending')
check(list(a[2]) == list(b[2]) and len(b[2]) == 28, '28_sheet_names_and_order_unchanged')
check(a[4] == b[4] and len(b[4]) == 3407, 'all_formula_text_and_attributes_unchanged')
check(a[5] == b[5], 'all_cell_style_indices_unchanged')
check(a[6] == b[6], 'all_sheet_layouts_and_native_structures_unchanged')
check(a[7] == b[7] and sum(sum(v.values()) for v in b[7].values()) == 12206, '12206_native_hyperlink_targets_and_positions_unchanged')
check(set(a[0].namelist()) == set(b[0].namelist()), 'native_package_part_set_unchanged')
plan=read(F/'workbook-edit-plan.json')
planned={(x['sheet'],x['cell']):x for x in plan['cell_changes']+plan['calculated_value_changes']}
changed={k for k in set(a[3])|set(b[3]) if a[3].get(k)!=b[3].get(k)}
check(len(plan['cell_changes']) == 95 and len(plan['calculated_value_changes']) == 8 and len(planned) == 103 and changed == set(planned), 'only_95_authored_and_8_calculated_value_changes', sorted(changed-set(planned)))
display_changes={k for k in set(a[8])|set(b[8]) if a[8].get(k)!=b[8].get(k)}
check(len(display_changes)==3 and display_changes <= set(planned), 'three_hyperlink_labels_synchronize_planned_cells', sorted(display_changes))
for k in display_changes:
    check(a[8][k]==a[3][k] and b[8][k]==b[3][k], 'hyperlink_display_matches_planned_old_and_new_cell_value', k)
for k,x in planned.items():
    check(a[3].get(k) == x['before'] and b[3].get(k) == x['value'], 'exact_old_and_new_planned_cell_values', k)
    check((k in b[4]) == (x in plan['calculated_value_changes']), 'authored_vs_calculated_cell_scope', k)
for part in a[0].namelist():
    if a[0].read(part) == b[0].read(part): continue
    if part in a[2].values(): continue
    if part.endswith('.rels'):
        check(collections.Counter(relationship_semantics(a[0],part).values()) == collections.Counter(relationship_semantics(b[0],part).values()), 'regenerated_relationship_IDs_resolve_to_same_targets', part)
    elif part == 'xl/workbook.xml':
        check(canon(E.fromstring(a[0].read(part)),relationship_semantics(a[0],'xl/_rels/workbook.xml.rels')) == canon(E.fromstring(b[0].read(part)),relationship_semantics(b[0],'xl/_rels/workbook.xml.rels')), 'workbook_relationships_resolve_to_same_sheet_structure', part)
    elif part.endswith('.xml'):
        check(canon(E.fromstring(a[0].read(part))) == canon(E.fromstring(b[0].read(part))), 'other_changed_XML_is_serialization_only', part)
    else: check(False,'unexpected_non_XML_package_change',part)
artifact=read(Q/'artifact-value-readback.json')
check(artifact['status'] == 'PASS' and artifact['authored_value_reads'] == 95 and artifact['calculated_value_reads'] == 8 and artifact['original_candidate_bytes_unchanged'] is True, 'independent_artifact_tool_103_value_reads')
check(len(artifact['previews']) == 5, 'five_scoped_preview_ranges_rendered')
for x in artifact['previews']:check(sha(x['path']) == x['sha256'],'preview_hash',x['path'])
for p,h in manifest['protected_published_files'].items():check(sha(p)==h,'published_baseline_unchanged_end',p)

result={'status':'PASS' if not failures else 'FAIL','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'candidate_workbook_sha256':sha(F/'master-workbook.pending'),'candidate_register_sha256':sha(F/'canonical-master-register.json'),
        'frozen_edit_plan_sha256':sha(F/'workbook-edit-plan.json'),'checks_total':sum(checks.values()),'checks_passed':sum(checks.values())-len(failures),'check_categories':dict(checks),'failures':failures,
        'actual_changed_option_IDs':sorted(actual_changed),'workbook_authored_changes':95,'calculated_cache_changes':8,'artifact_tool_value_reads':103,'scoped_previews_reviewed':5,
        'all_other_working_field_objects_unchanged':unchanged_fields,'unchanged_published_files':10,'scope':'Exact four owner answers, final candidate identity/wording and workbook delta only; no full gallery rerun. Native Excel runtime not evaluated.',
        'live_calls':0,'native_writes':0,'canonical_writes':0,'owner_questions_issued':0}
(Q/'candidate-independent-readback.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','checks_total','checks_passed','failures','candidate_workbook_sha256','candidate_register_sha256']}))
