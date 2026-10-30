import ast, copy, csv, hashlib, json, posixpath, sys, zipfile
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

BASE = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
C = BASE / 'components/reconciliation/moonspirals-three-pair-navigation-master-2026-10-24'
OUT = BASE / 'outputs/moonspirals-three-pair-navigation-master-2026-10-24'
OWN = Path(__file__).parent
MOVED = {'id:cnqzTNngPVsAAAAAAAucCw', 'id:cnqzTNngPVsAAAAAAAuR4Q', 'id:cnqzTNngPVsAAAAAAAuigw'}
WALL = {'BSI-65520F070145', 'BSI-D5A939264C82'}
EXPECTED_REG, EXPECTED_BOOK, EXPECTED_AUDIT = sys.argv[1:4]
def load(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name, obj): (OWN / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
checks = []
def check(name, ok, detail=None): checks.append({'name': name, 'passed': bool(ok), 'details': detail})
manifest = load(C / 'input-manifest.json')
freeze = load(C / 'candidate-freeze.json')
frozen = dict(freeze['frozen_artifacts'])
frozen[str(C / 'candidate-freeze.json')] = sha(C / 'candidate-freeze.json')
for name in ['moonspirals-pair-folder-changes.html', 'all-current-moonspirals-images.html', 'current-primary-navigation-health.html', 'Current_Primary_Navigation_48.csv']:
    frozen[str(OUT / name)] = sha(OUT / name)
old = load(manifest['master_register']['snapshot']); new = load(C / 'canonical-master-register.json')
audit0 = load(manifest['audit']['snapshot']); audit1 = load(C / 'image-coverage-current.json')
health0 = load(manifest['primary_health']['snapshot']); health1 = load(C / 'current-primary-navigation-health.json')
oldops = {r['product_id']: r for r in old['options']}; newops = {r['product_id']: r for r in new['options']}
assets0 = load(manifest['report_assets']['snapshot']); assets1 = load(C / 'current-assets.json')
map0 = load(manifest['native_map']['snapshot']); map1 = load(C / 'current-native-reference-map.json')
overlay = load(manifest['moonspirals_overlay']['snapshot'])
moves = {r['file_id']: r for r in overlay['specific_file_maps']}
objects = {r['file_id']: r for r in overlay['objects']}
wall_source = load(manifest['wall_circle_receipt_1']['snapshot'])
wall_rows = {r['option_id']: r for r in wall_source['rows']}
wall_receipts = load(manifest['wall_circle_receipt_0']['snapshot'])
wall_annotations = load(C / 'wall-circle-history-observations.json')
plan = load(C / 'workbook-edit-plan.json')

check('exact_flat_candidate_hashes', sha(C / 'canonical-master-register.json') == EXPECTED_REG == freeze['candidate_register_sha256'] and
      sha(C / 'master-workbook.pending') == EXPECTED_BOOK == freeze['candidate_workbook_sha256'] and
      sha(C / 'image-coverage-current.json') == EXPECTED_AUDIT == freeze['candidate_audit_sha256'])
check('exact_v2_freeze_file_hash', sha(C / 'candidate-freeze.json') == '54feb92bb768185641c9273f4e123d99bee7d056576bb8808bd7e4820fc1eca1')
check('all_frozen_artifacts_match', all(sha(p) == h for p, h in frozen.items()))
check('exact_published_baseline_and_all_frozen_inputs',
      manifest['pointer']['sha256'] == '1b1025e30e4e22ed362e48fec48e2266c895a086758bb5f6edcdb5d85ec82c1e' and
      manifest['master_register']['sha256'] == '8826312ebe27d675e7477925d849be3a3bc14d71cfdaa2f6b310c594b2a64ccf' and
      manifest['master_workbook']['sha256'] == 'ee78acab9c7f07cfab9cb5292c27e3eec70762127d1e9bd495310aed16e06316' and
      all(sha(v['snapshot']) == v['sha256'] for v in manifest.values() if isinstance(v, dict) and 'snapshot' in v))
native_qa = load(OWN / 'native-readback.json')
check('completed_independent_native14_checks_retained_without_repeat',
      sha(OWN / 'native-readback.json') == '0ce44b066dd6903c888388ca1e83df86b9bdb9585642bcc63369a8a73cbfacfe' and
      native_qa['status'] == 'PASS' and native_qa['checks_passed'] == native_qa['checks_total'] == 14 and
      sha(manifest['moonspirals_seal']['snapshot']) == native_qa['native_seal']['sha256'])
stripped_ops = copy.deepcopy(newops)
for oid in WALL: stripped_ops[oid]['current_primary_navigation'] = oldops[oid]['current_primary_navigation']
check('all189_full_option_objects_preserved_except_two_navigation_annotations',
      len(newops) == 189 and stripped_ops == oldops and
      [r['product_id'] for r in new['options']] == [r['product_id'] for r in old['options']])
stripped_reg = copy.deepcopy(new)
for key in ['latest_image_coverage_audit', 'current_primary_navigation_health', 'latest_moonspirals_pair_native_navigation_import',
            'latest_active_photo_source_review', 'latest_wall_circle_exact_history_observation']:
    if key in old: stripped_reg[key] = old[key]
    else: stripped_reg.pop(key, None)
stripped_reg['options'] = old['options']
check('all_other_register_data_design_groups_sources_and_counts_unchanged', stripped_reg == old)
check('188_active_options112_component_ids110_working_groups_retained',
      new['summary']['current_option_records'] == 188 and len(new['components']) == 112 and
      new['summary']['grouped_working_design_identity_count'] == 110 and
      new['current_working_design_group_projection'] == old['current_working_design_group_projection'])
unchanged = [('physical-source-audit.json', 'physical_audit'), ('photo-review-queue.json', 'report_reviews'),
             ('guided-owner-review-state.json', 'review_state'), ('pending-followups.json', 'pending'),
             ('photo-source-review.json', 'photo_source'), ('working-design-group-projection.json', 'working_groups')]
check('physical_fields_photo_roles_holds_and_design_projection_byte_identical',
      all(sha(C / filename) == sha(manifest[key]['snapshot']) for filename, key in unchanged))
stripped_audit = copy.deepcopy(audit1)
for i, row in enumerate(stripped_audit['coverage']):
    if row['option_id'] in WALL:
        row['individual']['current_native_navigation'] = audit0['coverage'][i]['individual']['current_native_navigation']
stripped_audit['current_primary_navigation_health'] = audit0['current_primary_navigation_health']
check('image_audit_only_two_navigation_notes_and_current_health_pointer_change', stripped_audit == audit0)
check('corrected_current_health_pointer_and_hash_agree_in_audit_and_register',
      all(obj['path'] == str(C / 'current-primary-navigation-health.json') and obj['sha256'] == sha(C / 'current-primary-navigation-health.json')
          for obj in [new['current_primary_navigation_health'], audit1['current_primary_navigation_health']]))

history_reads = []
local_original_checks = []
for oid, record in wall_rows.items():
    key = 'history-yellow-grey' if oid == 'BSI-65520F070145' else 'history-terracotta'
    response = wall_receipts['observations'][key]['response']
    hist = response.get('structuredContent') or json.loads(response['content'][0]['text'])
    nav = newops[oid]['current_primary_navigation']
    history_reads.append(hist['is_deleted'] is True and hist['server_deleted'] == record['server_deleted_utc'] == nav['server_deleted_utc'] and
                         hist['has_more'] is False and len(hist['entries']) == record['available_revision_count'] == nav['available_revision_count'] and
                         hist['entries'][0] == record['latest_available_revision'] == nav['latest_available_revision'] and
                         hist['entries'][0]['file_id'] == newops[oid]['file_id'])
    original = record['existing_local_original']; raw = Path(original['path']).read_bytes()
    whole = hashlib.sha256(raw).hexdigest()
    content = hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0, len(raw), 4194304))).hexdigest()
    local_original_checks.append(whole == original['sha256'] and len(raw) == original['size'] == hist['entries'][0]['size'] and
                                 content == original['dropbox_content_hash'] == hist['entries'][0]['content_hash'])
check('two_deleted_flags_clocks_and_latest_revisions_match_sealed_live_responses', set(wall_rows) == WALL and all(history_reads))
check('two_existing_historical_original_bytes_match_remote_revision_hashes', all(local_original_checks))
check('wall_circle_annotations_retain_history_hold_and_no_restoration_or_selection',
      set(wall_annotations['rows']) == WALL and wall_annotations['restorations'] == wall_annotations['replacement_selections'] == 0 and
      all(newops[oid]['current_primary_navigation'] == wall_annotations['rows'][oid] and
          newops[oid]['current_primary_navigation']['previous_navigation_observation'] == oldops[oid]['current_primary_navigation'] and
          newops[oid]['current_primary_navigation']['existing_local_historical_original'] == wall_rows[oid]['existing_local_original'] and
          newops[oid]['current_primary_navigation']['owner_hold_preserved'] is True and
          all(newops[oid]['current_primary_navigation'][k] is False for k in ['current_primary_verified', 'replacement_selected', 'restored_to_dropbox']) and
          newops[oid]['current_primary_navigation']['deletion_actor'] is None and newops[oid]['current_primary_navigation']['deletion_reason'] is None
          for oid in WALL))
check('audit_navigation_annotations_equal_option_annotations',
      all(row['individual']['current_native_navigation'] == newops[row['option_id']]['current_primary_navigation']
          for row in audit1['coverage'] if row['option_id'] in WALL))
h0 = {r['product_id']: r for r in health0['rows']}; h1 = {r['product_id']: r for r in health1['rows']}
check('48_health_rows_preserved_except_exact_two_saved_primary_histories', set(h0) == set(h1) and len(h1) == 48 and
      all(h1[oid] == row for oid, row in h0.items() if oid not in WALL) and
      all(h1[oid]['previous_navigation_observation'] == h0[oid] and
          h1[oid]['server_deleted_utc'] == wall_rows[oid]['server_deleted_utc'] and
          h1[oid]['restored_to_dropbox'] is False and
          all(h1[oid][k] == h0[oid][k] for k in h0[oid] if k not in ['navigation_status', 'qualification']) for oid in WALL))
hc = dict(health1['counts'])
hc.pop('saved_primary_ids_marked_deleted_in_available_history', None); hc.pop('matching_local_historical_originals', None)
check('original_health_counts_unchanged_two_specific_observation_counts_added', hc == health0['counts'] and
      health1['counts']['saved_primary_ids_marked_deleted_in_available_history'] == health1['counts']['matching_local_historical_originals'] == 2)

check('only_three_existing_asset_objects_changed', set(assets0) == set(assets1) and {i for i in assets0 if assets0[i] != assets1[i]} == MOVED)
asset_ok = []
for fid in MOVED:
    before, after, move, obj = assets0[fid], assets1[fid], moves[fid], objects[fid]
    expected = copy.deepcopy(before)
    expected.update(path=obj['current_ns_path'], display_path=move['new_path'], folder_path=obj['current_ns_path'].rsplit('/', 1)[0],
                    folder_id=move['new_parent_id'], image_url=obj['current_native_url'], folder_url=obj['current_native_url'].split('?', 1)[0],
                    modified_time=obj['current_server_modified'])
    expected['historical_same_id_navigation'] = before.get('historical_same_id_navigation', []) + [{k: before.get(k) for k in ['path', 'display_path', 'folder_path', 'folder_id', 'image_url', 'folder_url']}]
    asset_ok.append(after == expected)
check('all_three_asset_changes_equal_sealed_paths_parents_times_and_saved_previous_links', all(asset_ok))
expected_map = copy.deepcopy(map0)
for fid in MOVED:
    obj = objects[fid]
    expected_map['current_objects'][fid].update(path=obj['current_ns_path'], display_path=obj['current_path'], parent_id=obj['current_parent_id'], current_navigation_source=manifest['moonspirals_overlay']['path'])
    expected_map['old_path_to_id'][obj['current_path'].lower()] = fid
history = load(C / 'path-change-history.json')
history_entry = map1['verified_path_change_history'][-1]
expected_map['verified_path_change_history'].append(history_entry)
expected_map['status'] = 'CURRENT_MAP_WITH_THREE_APPROVED_MOONSPIRALS_PAIR_PATHS'
check('entire_native_map_only_three_current_objects_three_path_keys_and_history_entry', expected_map == map1)
check('three_navigation_history_records_equal_before_and_after_objects',
      len(history) == 3 and {x['file_id'] for x in history} == MOVED and history_entry['objects'] == history and
      history_entry['sha256'] == manifest['moonspirals_overlay']['sha256'] and
      all(x['before'] == map0['current_objects'][x['file_id']] and x['current'] == map1['current_objects'][x['file_id']] for x in history))

class HTML(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.text=[]
    def handle_starttag(self, tag, attrs):
        if tag == 'a': self.links.append(dict(attrs).get('href'))
    def handle_data(self, data): self.text.append(data)
def readhtml(name):
    h=HTML(); h.feed((OUT/name).read_text()); return h
mh = readhtml('moonspirals-pair-folder-changes.html'); ah = readhtml('all-current-moonspirals-images.html'); wh = readhtml('current-primary-navigation-health.html')
check('moonspiral_change_and_inventory_reports_include_three_new_images_and_parent_links',
      all(assets1[fid][k] in h.links for fid in MOVED for k in ['image_url','folder_url'] for h in [mh,ah]))
with (OUT/'Current_Primary_Navigation_48.csv').open(encoding='utf-8-sig', newline='') as f: rows=list(csv.DictReader(f))
check('navigation_csv_retains48_rows_exact_saved_links_and_two_deleted_statuses', len(rows) == 48 and
      all(r['file_id'] == newops[r['option_id']]['file_id'] and r['folder_id'] == newops[r['option_id']]['folder_id'] for r in rows) and
      all(r['navigation_status'] == 'SAVED_PRIMARY_ID_MARKED_DELETED_IN_AVAILABLE_DROPBOX_HISTORY' for r in rows if r['option_id'] in WALL))
wt=' '.join(wh.text)
check('navigation_html_qualifies_historical_originals_no_restore_and_held_reviews',
      all(r['server_deleted_utc'] in wt and r['folder_url'] in wh.links for r in wall_rows.values()) and
      'historical' in wt.lower() and 'hold' in wt.lower() and 'restor' in wt.lower())

helper=BASE/'components/parallel-reviews/decowaves1-candidate-qa-20261024T040807Z/verify_decowaves1.py'
function=next(x for x in ast.parse(helper.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='read_xlsx')
N={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
exec(compile(ast.Module(body=[function],type_ignores=[]),str(helper),'exec'))
w0,rh0=read_xlsx(manifest['master_workbook']['snapshot']);w1,rh1=read_xlsx(C/'master-workbook.pending')
check('28_sheets_and_order_retained',list(w0)==list(w1) and len(w1)==28)
expected_w=copy.deepcopy(w0);value_errors=[]
allowed={('Master Catalogue',x) for x in ['A3','N188','N190','V188','V190']}|{('Photo Coverage',x) for x in ['D188','D190','L188','L190']}
for r in plan['cell_changes']:
    cell=expected_w[r['sheet']][r['cell']]
    if cell['value']!=str(r['before']) or cell['formula'] is not None:value_errors.append((r['sheet'],r['cell']))
    cell['value']=str(r['value'])
check('exact_nine_planned_values_only_in_two_status_rows_and_summary',len(plan['cell_changes'])==9 and {(r['sheet'],r['cell']) for r in plan['cell_changes']}==allowed and not value_errors,value_errors)
oldprefix=str(BASE/'outputs/decowaves2-owner-design-group-master-2026-10-24')+'/'
newprefix=str(OUT)+'/'
planned={(r['sheet'],r['cell']):r['target'] for r in plan['hyperlinks']}
linkchanges=[];badlinks=[]
for sheet,cells in w0.items():
    for addr,cell in cells.items():
        before=cell.get('hyperlink');after=w1[sheet].get(addr,{}).get('hyperlink')
        if before==after:continue
        rebase=isinstance(before,str) and before.startswith(oldprefix) and after==newprefix+before[len(oldprefix):]
        newreview=(sheet,addr)==('Master Catalogue','A3') and before==oldprefix+'decowaves2-owner-design-equivalence.html' and after==newprefix+'moonspirals-pair-folder-changes.html'
        valid=(rebase or newreview) and planned.get((sheet,addr))==after and Path(after.split('#',1)[0]).is_file()
        record={'sheet':sheet,'cell':addr,'before':before,'after':after,'valid':valid};linkchanges.append(record)
        if valid:expected_w[sheet][addr]['hyperlink']=after
        else:badlinks.append(record)
check('all_link_changes_are_declared_local_report_rebases_or_new_summary_review',bool(linkchanges) and not badlinks,{'count':len(linkchanges),'errors':badlinks})
check('entire_workbook_values_formulas_and_links_equal_narrow_allowed_projection',expected_w==w1,{'unexpected_sheets':[s for s in w1 if expected_w[s]!=w1[s]]})
expected_rh=copy.deepcopy(rh0)
for r in plan['row_heights']:expected_rh[r['sheet']][r['row']]=float(r['height'])
check('exact_four_declared_row_height_changes',len(plan['row_heights'])==4 and expected_rh==rh1)
f0={(s,a):c['formula'] for s,cs in w0.items() for a,c in cs.items() if c['formula'] is not None}
f1={(s,a):c['formula'] for s,cs in w1.items() for a,c in cs.items() if c['formula'] is not None}
l0={(s,a):c['hyperlink'] for s,cs in w0.items() for a,c in cs.items() if c.get('hyperlink')}
l1={(s,a):c['hyperlink'] for s,cs in w1.items() for a,c in cs.items() if c.get('hyperlink')}
check('all3407_formulas_and12206_hyperlinks_retained_external_destinations_unchanged',f0==f1 and len(f1)==3407 and len(l0)==len(l1)==12206 and
      {k:v for k,v in l0.items() if v.startswith(('https://','http://'))}=={k:v for k,v in l1.items() if v.startswith(('https://','http://'))})
check('no_native_workbook_link_edits_or_new_sheets',not plan['native_link_changes'] and not plan['new_sheets'])
check('candidate_and_report_bytes_stable_through_readback',all(sha(p)==h for p,h in frozen.items()))
result={'status':'PASS' if all(c['passed'] for c in checks) else 'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),
        'candidate_register_sha256':EXPECTED_REG,'candidate_workbook_sha256':EXPECTED_BOOK,'candidate_audit_sha256':EXPECTED_AUDIT,
        'checks_passed':sum(c['passed'] for c in checks),'checks_total':len(checks),'checks':checks,'frozen_artifacts':frozen,
        'prior_native14_readback':{'path':str(OWN/'native-readback.json'),'sha256':sha(OWN/'native-readback.json')},
        'scope':'Independent candidate JSON, provider receipt projection, two historical local-byte comparisons, CSV/HTML and XLSX semantic readback. No shared/native writes; prior native14 checks retained without repeat.'}
assert not (OWN/'candidate-readback.json').exists(),'Preserve previous candidate check before rerun'
save('local-report-link-changes.json',linkchanges);save('candidate-readback.json',result)
seal={'status':result['status'],'recorded_utc':result['recorded_utc'],'candidate_register_sha256':EXPECTED_REG,'candidate_workbook_sha256':EXPECTED_BOOK,
      'candidate_audit_sha256':EXPECTED_AUDIT,'files':[{'path':str(OWN/n),'sha256':sha(OWN/n)} for n in ['verify_candidate.py','candidate-readback.json','local-report-link-changes.json','native-readback.json']],
      'shared_or_native_writes':0}
save('sealed-handoff.json',seal)
print(json.dumps({'status':result['status'],'checks_passed':result['checks_passed'],'checks_total':result['checks_total'],'failed':[c for c in checks if not c['passed']],
                  'path':str(OWN/'candidate-readback.json'),'sha256':sha(OWN/'candidate-readback.json'),'seal_sha256':sha(OWN/'sealed-handoff.json')}))
