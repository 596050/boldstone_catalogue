"""Record the owner instruction and current component-first organisation audit."""
import collections
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
pointer = json.loads((BASE / 'sculpture-catalogue/current-master.json').read_text())
register_path = BASE / 'sculpture-catalogue' / pointer['register']
register_bytes = register_path.read_bytes()
assert hashlib.sha256(register_bytes).hexdigest() == pointer['register_sha256']
register = json.loads(register_bytes)
families = collections.defaultdict(list)
for component in register['components']:
    families[component['family']].append({k: component.get(k) for k in (
        'component_id', 'name', 'family', 'option_ids', 'option_names',
        'file_id', 'folder_id', 'scope_note')})
multi = {family: components for family, components in families.items() if len(components) > 1}
group_only = [{k: option.get(k) for k in (
    'product_id', 'name', 'family', 'canonical_component_id',
    'file_id', 'folder_id', 'photo_coverage')}
    for option in register['options']
    if option.get('photo_coverage', {}).get('individual') == 'Group only']
audit = {
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'OWNER_COMPONENT_FIRST_RULE_RECORDED; NO_DROPBOX_MUTATIONS',
    'owner_instruction': 'When there are multiple component sculptures for a particular sculpture family, the sculpture pairs/groups should be split into individual component sculptures',
    'rule': [
        'Organise each separately identified component as its own sculpture, with its own catalogue identity and component folder.',
        'Retain approved component numbers; distinguish a source whole-composition number from component numbers.',
        'Keep finishes and size options associated with their individual component.',
        'Retain whole-pair and group photographs as arrangement or context references linked to the identified components.',
        'Move existing individual photographs only when an evidence-backed file-to-component mapping is available.',
        'Do not duplicate group photographs as purported individual photographs, alter original images, invent member identities, or infer mould or stock counts.',
        'Preserve existing catalogue IDs and specifications; the master writer alone applies shared-register changes.',
    ],
    'register_source': {
        'pointer_recorded_utc': pointer['recorded_utc'],
        'path': str(register_path),
        'sha256': pointer['register_sha256'],
        'identified_catalogue_components': len(register['components']),
        'working_options': len(register['options']),
        'families_with_multiple_identified_components': len(multi),
        'group_only_options_in_this_snapshot': len(group_only),
        'limit': 'This is a named register snapshot. Concurrent image-coverage updates may supersede its gap counts; counts are not physical mould or stock counts.',
    },
    'families_with_multiple_identified_components': multi,
    'snapshot_group_only_options': group_only,
    'first_priority': {
        'family': 'Fingerprint',
        'existing_component_ids': ['BC-FP-LEFT', 'BC-FP-RIGHT'],
        'existing_option_ids': ['BSI-6D48F324B10C', 'BSI-5A81C695D1AB', 'BSI-59CBB4D2FA9E', 'BSI-51CF74303593'],
        'finding': 'The approved catalogue already separates two concentric components in White and Verdigris. The current three numbered Dropbox folders contain pair or context photographs, not isolated member photographs.',
        'source_number_scope': 'Fingerprint source proposal 2 describes the whole concentric pair. It does not establish per-member numbers 1 and 2.',
        'next_action': 'Prepare a component-to-folder and individual-file crosswalk while retaining pair references. Any genuinely new numeric member convention remains explicit and separate from recovering source numbering.',
        'supersedes': 'A pair-only rename is insufficient to satisfy the component-first organisation instruction.',
        'native_readback': 'fingerprint-native-readback.json',
        'visual_review': 'sculpture-catalogue/components/reviews/fingerprint-01.jpg (historical board; current parent identities crosschecked by native readback)',
    },
    'remote_files_or_folders_created_moved_deleted': 0,
    'shared_master_writes_by_this_lane': 0,
}
target = OUT / 'component-organisation-audit.json'
if target.exists():
    raise SystemExit('Refusing to overwrite the sealed audit')
target.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'multi_component_families': len(multi), 'group_only_snapshot_options': len(group_only)}))
