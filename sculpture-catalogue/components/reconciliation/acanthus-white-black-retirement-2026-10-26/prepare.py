"""Stage the exact owner retirement, preserving all other option/source evidence."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import copy
import hashlib
import json
import sqlite3

H = Path(__file__).resolve().parent
B = H.parents[2]
OID = 'BSI-B0D0CCA7E318'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
manifest = read(H / 'input-manifest.json')
for r in manifest.values():
    assert sha(r['path']) == sha(r['snapshot']) == r['sha256']
p = read(manifest['pointer']['snapshot'])
old = read(manifest['register']['snapshot'])
g = copy.deepcopy(old)
options = {o['product_id']: o for o in g['options']}
o = options[OID]
assert OID in g['active_option_ids'] and OID not in g['retired_option_ids']
native = read(H / 'native-readback.json')
assert len(native['rows']) == 4 and all(r['not_found'] for r in native['rows'])
now = datetime.now(timezone.utc).isoformat()
decision = {'decision_id': 'ACANTHUS-TWO-LEAVES-WHITE-BLACK:OWNER-RETIRED:2026-10-26',
    'recorded_utc': now, 'option_id': OID, 'name': o['name'],
    'owner_text': 'Delete Acanthus Two Leaves - White and Black everywhere',
    'instruction_path': str(H / 'owner-instruction.json'), 'instruction_sha256': sha(H / 'owner-instruction.json'),
    'status': 'RETIRED_FROM_CURRENT_CATALOGUE', 'current_offer_active': False,
    'physical_or_commercial_verification_inferred': False,
    'scope': 'Exact White and Black option only. Preserve all other finishes, shared images and family/Bronze platform records.'}
o.update(catalogue_status='Retired', active_catalogue_option=False, counted_as_individual_option=False,
    count_class='Retired option - historical identity retained', catalogue_retirement=decision,
    current_offer_active=False, historical_selling_details_only=True,
    current_availability='Retired - removed at owner request', current_measurement_required=False)
o['photo_coverage'].update(individual='Retired / not applicable', in_situ='Retired / not applicable', series='Retired / not applicable')
o.setdefault('current_photo_task_review', {}).update(state='OWNER_RETIRED_OPTION',
    next_action='No active photograph, specification, offer or draft-creation task.', retirement=decision)
o['current_listing_resolution'] = {**o.get('current_listing_resolution', {}), 'catalogue_active': False,
    'status': 'RETIRED_NO_CURRENT_OFFER_OR_DRAFT_CREATION', 'next_action': 'None - owner-retired option; history retained.'}
g['catalogue_retirements'].append(decision)
g['retired_option_ids'].append(OID)
g['active_option_ids'] = [pid for pid in old['active_option_ids'] if pid != OID]
g['latest_catalogue_retirement'] = decision
g['count_definition'] = '187 active individually offered finish/size/build options; 189 retained history records including two owner-retired options. Component/design groups are not physical casts, moulds or stock.'
component = next(c for c in g['components'] if c['component_id'] == 'BC-AC-TWO')
component['historical_option_members_before_retirement'] = {k: copy.deepcopy(component[k]) for k in ['option_ids', 'option_count', 'option_names']}
component['option_ids'].remove(OID)
component['option_names'].remove(o['name'])
component['option_count'] = len(component['option_ids'])
component.setdefault('retired_option_ids', []).append(OID)
summary = g['summary']
summary.update(individual_options_on_identified_components=180, individual_named_working_options=187,
    individual_options_with_dropbox_reference=186, current_option_records=187, current_field_groups=1122,
    options_with_six_working_fields=187, retained_option_records=189, retired_option_records=2,
    retained_working_field_groups=1134)
projection = g['current_working_design_group_projection']
projection['active_individual_finish_option_count'] = 187
for group in projection['groups']:
    if OID in group.get('active_option_ids', []):
        group['active_option_ids'].remove(OID)
treatment_path = Path(g['current_listing_treatment_plan']['register'])
treatment = read(treatment_path)
archived = next(r for r in treatment['options'] if r['product_id'] == OID)
treatment['options'] = [r for r in treatment['options'] if r['product_id'] != OID]
treatment.setdefault('retired_option_history', []).append({'retirement': decision, 'historical_treatment': archived})
treatment['active_option_count'] = 187
treatment['retirement_scope'] = decision
dump(H / 'listing-treatment-register.json', treatment)
dump(H / 'retired-listing-treatment.json', archived)
g['current_listing_treatment_plan']['register'] = str(H / 'listing-treatment-register.json')
g['current_listing_treatment_plan']['register_sha256'] = sha(H / 'listing-treatment-register.json')
g['current_listing_treatment_plan']['status'] = 'LOCAL_WORKING_TREATMENT_FOR_ALL187_ACTIVE_OPTIONS_WITH_RETIRED_HISTORY'
ts = g['current_listing_treatment_plan']['summary']
ts['active_option_count'] = 187
ts['working_specification_fields'] = 1122
ts['listing_treatments'] = dict(Counter(r['listing_treatment'] for r in treatment['options']))
ts['retired_local_treatments'] = 2
g['current_listing_treatment_plan']['historical_package_before_retirement'] = copy.deepcopy(old['current_listing_treatment_plan']['package'])
dump(H / 'canonical-master-register.json', g)
before_options = {r['product_id']: r for r in old['options']}
after_options = {r['product_id']: r for r in g['options']}
assert len(g['active_option_ids']) == 187 and len(g['options']) == 189 and len(g['retired_option_ids']) == 2
assert set(before_options) == set(after_options)
assert all(before_options[pid] == after_options[pid] for pid in before_options if pid != OID)
assert g['original_review_specification_assertions'] == old['original_review_specification_assertions']
assert len(g['original_review_specification_assertions']) == 1668
for k in ['specifications', 'master_fields', 'source_product_sha256', 'canonical_component_id']:
    assert before_options[OID][k] == after_options[OID][k]
unchanged = {pid: hashlib.sha256(json.dumps(before_options[pid], sort_keys=True).encode()).hexdigest() for pid in g['active_option_ids']}
delta = {'status': 'PREPARED_EXACT_OPTION_RETIREMENT_NOT_PUBLISHED', 'option_id': OID,
    'old_register_path': manifest['register']['path'], 'old_register_sha256': manifest['register']['sha256'],
    'new_register_path': str(H / 'canonical-master-register.json'), 'new_register_sha256': sha(H / 'canonical-master-register.json'),
    'baseline_pointer_sha256': manifest['pointer']['sha256'], 'before_active_options': 188, 'after_active_options': 187,
    'retained_history_records': 189, 'retired_history_records': 2,
    'unchanged_active_option_ids': g['active_option_ids'], 'unchanged_active_option_object_sha256': unchanged,
    'other_option_objects_unchanged': 188, 'unchanged_raw_specification_assertions': 1668,
    'unchanged_gallery_database': str((B / p['current_published_gallery_projection']['path']).parent / 'complete-image-platform-register.sqlite'),
    'unchanged_gallery_sha256': '26a09ffd64380e7c87dde27882b503d022bf8275510909f965718ee36aa9b591',
    'native_owned_folder_and_files_not_found': native,
    'retired_option_review_rows_must_remain_historical': True,
    'app_source_rebase_owner': '01a13fe6-495b-7253-b923-31823b4cbca8',
    'platform_or_native_mutations_by_root': 0}
assert sha(delta['unchanged_gallery_database']) == delta['unchanged_gallery_sha256']
dump(H / 'SOURCE_READY_FOR_APP_REBASE.json', delta)
print(json.dumps({k: v for k, v in delta.items() if k not in ['unchanged_active_option_ids', 'unchanged_active_option_object_sha256', 'native_owned_folder_and_files_not_found']}, indent=2))
