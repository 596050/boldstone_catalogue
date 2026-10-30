"""Prepare the owner-approved three White products, preserving all history."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, shutil, sqlite3, sys, urllib.request

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
BASE = PROJECT / 'sculpture-catalogue'
OUT = BASE / 'components/reconciliation/lava-moon-three-white-products-2026-10-29'
RUNTIME = Path('/Users/tprice/Library/Application Support/BoldstoneReview')
WHITE = ['BSI-7357A558C9E8', 'BSI-791ADD96D660', 'BSI-2246CBC9C94E']
OLD = ['BSI-725A77437026', 'BSI-D7C2FC84A86B', 'BSI-63B177B06578']
FOLDER = 'id:cnqzTNngPVsAAAAAAAyihw'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
def write(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

assert not OUT.exists(), 'Do not overwrite an existing prepared publication.'
OUT.mkdir(parents=True)
stamp = datetime.now(timezone.utc).isoformat()
decision = {'recorded_utc': stamp, 'decision_id': 'LAVA-MOON-THREE-WHITE-PRODUCTS-20261029',
    'owner_quote': 'Yes - only the three White products',
    'approved_question': "Should the app show only Lava Moon 1-3 White as products, keeping the Sandstone pictures only in the family image library?",
    'active_option_ids': WHITE, 'retired_option_ids': OLD,
    'family_library_only_folder_id': FOLDER,
    'scope': 'Retire Sandstone product options without merging their specifications or images into White. Keep all native photographs, saved choices and source history. No Dropbox changes.'}
write(OUT / 'owner-decision.json', decision)
manifest = {'created_utc': stamp, 'controls': {}}
for name in ['current-master.json', 'components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']:
    src = BASE / name; dest = OUT / 'inputs' / name
    dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dest)
    manifest['controls'][name] = {'sha256': sha(src), 'snapshot': str(dest)}
pointer = read(BASE / 'current-master.json')
source_register = BASE / pointer['register']
source_gallery = (BASE / pointer['current_published_gallery_projection']['path']).parent / 'complete-image-platform-register.sqlite'
for key, path in [('input_register', source_register), ('input_gallery', source_gallery)]:
    dest = OUT / 'inputs' / path.name; shutil.copy2(path, dest)
    manifest[key] = {'path': str(path), 'sha256': sha(path), 'snapshot': str(dest)}
assert sha(source_register) == pointer['register_sha256']
original = read(source_register); register = deepcopy(original)
options = {r['product_id']: r for r in register['options']}
before = {r['product_id']: r for r in original['options']}
assert set(WHITE + OLD) <= set(original['active_option_ids'])
with closing(sqlite3.connect('file:' + str(RUNTIME / 'reviews.sqlite3') + '?mode=ro', uri=True)) as db:
    db.row_factory = sqlite3.Row
    reviews = [dict(r) for r in db.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id')]
write(OUT / 'inputs/saved-reviews.json', reviews)
for pid in OLD:
    row = options[pid]
    retirement = {**decision, 'option_id': pid, 'status': 'RETIRED_OPTION_CONTEXT_IMAGES_RETAINED'}
    row.update(counted_as_individual_option=False,
        count_class='Retired Sandstone option - photographs retained as family context', catalogue_retirement=retirement)
    register['catalogue_retirements'].append(retirement)
register['active_option_ids'] = [pid for pid in original['active_option_ids'] if pid not in OLD]
register['retired_option_ids'] = list(dict.fromkeys(original['retired_option_ids'] + OLD))
register['family_library_only_folder_ids'] = list(dict.fromkeys(register.get('family_library_only_folder_ids', []) + [FOLDER]))
register['latest_lava_moon_product_decision'] = decision
active = set(register['active_option_ids']); summary = register['summary']
for field in ['individual_options_on_identified_components', 'individual_named_working_options', 'current_option_records', 'options_with_six_working_fields']:
    summary[field] -= len(OLD)
summary['current_field_groups'] -= 6 * len(OLD)
summary['retired_option_records'] = len(register['retired_option_ids'])
summary['individual_options_with_dropbox_reference'] = sum(bool(options[pid].get('file_id')) for pid in active)
summary['active_component_ids_including_provisional'] = len({options[pid]['canonical_component_id'] for pid in active if options[pid].get('canonical_component_id')})
groups = register['current_working_design_group_projection']
for group in groups['groups']:
    group['active_option_ids'] = [pid for pid in group.get('active_option_ids', []) if pid in active]
groups['active_individual_finish_option_count'] = len(active)
groups['retained_option_record_count'] = len(register['options'])
groups['latest_lava_moon_product_decision'] = decision
for pid, row in options.items():
    for field in ('specifications', 'master_fields', 'selling_details'):
        assert row.get(field) == before[pid].get(field)
    if pid not in OLD: assert row == before[pid], pid
assert len(active) == 181 and len(register['options']) == 191
write(OUT / 'canonical-master-register.json', register)
gallery_dir = OUT / 'gallery-projection'; gallery_dir.mkdir()
gallery = gallery_dir / 'complete-image-platform-register.sqlite'
shutil.copy2(source_gallery, gallery)
with closing(sqlite3.connect(gallery)) as db:
    db.execute('CREATE TABLE products_before_lava_moon_white_only AS SELECT * FROM products')
    for pid in OLD:
        db.execute('UPDATE products SET record_json=? WHERE product_id=?', (json.dumps(options[pid], ensure_ascii=False), pid))
    db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)', ('lava_moon_three_white_products', json.dumps(decision)))
    db.commit(); assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
seal = {'status': 'PREPARED_LAVA_MOON_THREE_WHITE_PRODUCTS', 'decision': decision,
    'register_sha256': sha(OUT / 'canonical-master-register.json'), 'database_sha256': sha(gallery),
    'source_register': manifest['input_register'], 'source_gallery': manifest['input_gallery'],
    'active_options': 181, 'retained_options': 191, 'retired_options': 10,
    'physical_specifications_changed': 0, 'native_writes': 0, 'source_image_associations_preserved': True}
write(gallery_dir / 'sealed-handoff.json', seal)
new = deepcopy(pointer)
new.update(recorded_utc=stamp, status='CURRENT181_LAVA_MOON_THREE_WHITE_PRODUCTS_APP_SOURCE',
    register=str((OUT / 'canonical-master-register.json').relative_to(BASE)), register_sha256=seal['register_sha256'],
    summary=summary, publication_receipt=str((OUT / 'publication-receipt.json').relative_to(BASE)),
    latest_lava_moon_product_decision=decision,
    workbook_status='Workbook refresh pending for the current 181-option register and live app choices.',
    historical_gallery_before_lava_moon_white_only=pointer['current_published_gallery_projection'])
new['latest_corrections'] += ' Owner retained only Lava Moon 1-3 White as products; Sandstone photographs remain family-library context. All specifications and historical associations preserved.'
new['current_published_gallery_projection'] = {'status': seal['status'],
    'path': str((gallery_dir / 'sealed-handoff.json').relative_to(BASE)), 'sha256': sha(gallery_dir / 'sealed-handoff.json'),
    'register_sha256': seal['register_sha256'], 'database_sha256': seal['database_sha256'],
    'active_options': 181, 'retained_options': 191, 'source_platform_associations_preserved': True}
write(OUT / 'next-current-master.json', new); write(OUT / 'input-manifest.json', manifest)
stage = deepcopy(new)
stage['register'] = str(OUT / 'canonical-master-register.json')
stage['current_published_gallery_projection']['path'] = str(gallery_dir / 'sealed-handoff.json')
write(OUT / 'staging-project/sculpture-catalogue/current-master.json', stage)
print(json.dumps({'prepared': str(OUT), 'active': len(active), 'retained': len(register['options']), 'native_writes': 0}))
