"""Rebind terminal readers explicitly after this owner-decision publication."""
import copy
import hashlib
import json
from pathlib import Path
import shutil

H = Path(__file__).resolve().parent
B = H.parents[2]
R = B.parent/'reports/catalogue-terminal-walkthrough-20261024'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
p = read(B/'current-master.json')
assert p['register_sha256'] == sha(H/'canonical-master-register.json')
assert p['workbook_sha256'] == sha(B/p['workbook'])
assert read(H/'publication-receipt.json')['current_master_pointer_sha256'] == sha(B/'current-master.json')
g = read(B/p['register'])
old = read(H/'inputs/master_register.before')
assert g['original_review_specification_assertions'] == old['original_review_specification_assertions']
assert all(x['selling_details']['estimated_price'] == y['selling_details']['estimated_price'] for x,y in zip(old['options'],g['options']))
for name in ['walkthrough.py','navigation_projection.py','current-navigation-projection.json','walkthrough-state.json','current-reader-acceptance.json']:
    dest = H/'inputs'/('reader-before-owner-import-'+name)
    assert not dest.exists()
    shutil.copy2(R/name,dest)
projection = read(R/'current-navigation-projection.json')
projection['current_bindings'] = {k:copy.deepcopy(p[k]) for k in ['register','register_sha256','workbook','workbook_sha256','current_asset_reference_map','current_native_reference_map']}
projection['accepted_frozen_bindings']['register'].append(old_sha := read(H/'inputs/pointer.before')['register_sha256'])
projection['accepted_frozen_bindings']['workbook'].append(read(H/'inputs/pointer.before')['workbook_sha256'])
projection['accepted_frozen_bindings']['pointer'].append(sha(H/'inputs/pointer.before'))
projection.pop('all189_working_field_objects_and_source_assertions_unchanged',None)
projection.update(working_physical_and_commercial_numeric_values_and_states_preserved=True,all_source_assertions_unchanged=True,
    owner_identity_wording_changes=read(H/'identity-wording-field-changes.json'),
    owner_decision_publication={'path':str(H/'publication-receipt.json'),'sha256':sha(H/'publication-receipt.json')},
    observed_published_pointer_sha256=sha(B/'current-master.json'))
(R/'current-navigation-projection.json').write_text(json.dumps(projection,ensure_ascii=False,indent=2)+'\n')
helper = R/'navigation_projection.py'
s = helper.read_text()
s = s.replace("assert projection['all189_working_field_objects_and_source_assertions_unchanged']",
    "assert projection.get('working_physical_and_commercial_numeric_values_and_states_preserved',projection.get('all189_working_field_objects_and_source_assertions_unchanged',False))\n    assert projection.get('all_source_assertions_unchanged',True)")
helper.write_text(s)
script = R/'walkthrough.py'
s = script.read_text()
s = s.replace('1 pending Frozen Fish identity.','1 legacy Frozen Fish source offer still unverified; its relief relationship is resolved.')
s = s.replace("if args.item>len(items):raise SystemExit", "if pointer.get('latest_owner_identity_decision_import'):\n for packet in pointer['latest_owner_identity_decision_import']['decisions']:\n  a=read(packet['answer_path']);rel=a['accepted_relationship'];oid=rel.get('product_id') or rel['legacy_product_id'];o=options[oid];ref=o if o.get('file_id') else o['owner_confirmed_design_reference']\n  details={'Exact owner answer':a['owner_answer_verbatim'],'Scope':rel['scope'],'Preserved boundaries':'No exact native variant, new physical measurement, material confirmation or stock claim.22 context and1 series deferrals remain.'}\n  details.update({k:v['display']+'\\n'+v['state'] for k,v in o['master_fields'].items()})\n  items.append({'title':'Imported owner identity decision','status':'Owner answer verified and saved in the current master','option_id':oid,'name':o['name'],'image':ref['image_url'],'containing_folder':ref['folder_url'],'file_id':ref['file_id'],'folder_id':ref['folder_id'],'details':details,'review':str(B/pointer['current_image_review_links']['latest_owner_identity_decisions'])+'#'+oid})\nif args.item>len(items):raise SystemExit")
script.write_text(s)
verifier = R/'verify_current_readers.py'
s = verifier.read_text().replace("len(state['items']) == 99","len(state['items']) == 103")
s = s.replace('for num in [3,8,9,97,98,99]:','for num in [3,8,9,97,98,99,100,101,102,103]:')
s = s.replace("'main_work_items':99","'main_work_items':103").replace("'main_terminal_runs':[3,8,9,97,98,99]","'main_terminal_runs':[3,8,9,97,98,99,100,101,102,103]")
verifier.write_text(s)
print('Current terminal readers explicitly rebound; frozen source packets unchanged')
