"""Prepare the owner's three-finish catalogue decision without publishing it."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import sqlite3
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
BASE = PROJECT / 'sculpture-catalogue'
OUT = BASE / 'components/reconciliation/frozen-fish-three-finishes-2026-10-29'
RUNTIME = Path('/Users/tprice/Library/Application Support/BoldstoneReview')
WHITE = 'BSI-FE10273D3655'
NAMES = {WHITE: 'Frozen Fish - White', 'BSI-8DE87C63B013': 'Frozen Fish - Terracotta',
         'BSI-0D80125C0E35': 'Frozen Fish - Verdigris'}
OLD = ['BSI-04D6E8690F30', 'BSI-86E6AEA0EB98', 'BSI-60CAC1435616']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
def write(p, data):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

assert not OUT.exists(), 'Retain the existing preparation; do not overwrite it.'
OUT.mkdir(parents=True)
stamp = datetime.now(timezone.utc).isoformat()
decision = {'recorded_utc': stamp, 'decision_id': 'FROZEN-FISH-THREE-FINISHES-20261029',
    'owner_quote': 'Yes - consolidate into three finish listings: Should Frozen Fish now have just three component listings - White, Terracotta and Verdigris',
    'question_scope': 'Three component listings; One, Two, Three and Long retained only as old names.',
    'active_names': NAMES, 'retired_option_ids': OLD, 'replacement_option_id': WHITE,
    'scope': 'Current purchasable catalogue grouping. Preserve original source records, specifications and qualified platform claims; no native file changes or automatic image-use approval.'}
write(OUT / 'owner-decision.json', decision)
controls = ['current-master.json', 'components/reviews/specification_review_progress.json',
            'components/checkpoint.json', 'checkpoint.json']
manifest = {'created_utc': stamp, 'controls': {}, 'input_register': {}, 'input_gallery': {}}
for name in controls:
    path = BASE / name
    dest = OUT / 'inputs' / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    manifest['controls'][name] = {'sha256': sha(path), 'snapshot': str(dest)}
pointer = read(BASE / 'current-master.json')
source_register = BASE / pointer['register']
source_gallery = (BASE / pointer['current_published_gallery_projection']['path']).parent / 'complete-image-platform-register.sqlite'
for key, path in [('input_register', source_register), ('input_gallery', source_gallery)]:
    dest = OUT / 'inputs' / path.name
    shutil.copy2(path, dest)
    manifest[key] = {'path': str(path), 'sha256': sha(path), 'snapshot': str(dest)}
assert sha(source_register) == pointer['register_sha256']
original = read(source_register)
register = deepcopy(original)
options = {r['product_id']: r for r in register['options']}
before = {r['product_id']: r for r in original['options']}
assert set(OLD + list(NAMES)) <= set(original['active_option_ids'])

with closing(sqlite3.connect('file:' + str(RUNTIME / 'reviews.sqlite3') + '?mode=ro', uri=True)) as db:
    db.row_factory = sqlite3.Row
    reviews = [dict(r) for r in db.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id')
               if r['product_id'] in OLD + list(NAMES)]
assert all(r['kind'] == 'field' for r in reviews), 'Saved photo/product choices need a separate merge before publication.'
write(OUT / 'inputs/frozen-fish-saved-reviews.json', reviews)
for pid in OLD + list(NAMES):
    with urllib.request.urlopen('http://127.0.0.1:8767/api/products/' + pid, timeout=30) as response:
        write(OUT / ('inputs/' + pid + '.json'), json.load(response))

keeper = options[WHITE]
for pid, name in NAMES.items():
    row = options[pid]
    row['retained_names'] = list(dict.fromkeys(row.get('retained_names', []) + [row['name'], before[pid]['name'].replace('—', '-')]))
    row['name'] = name
    row['current_finish_listing_decision'] = decision
for pid in OLD:
    old = options[pid]
    keeper['retained_names'] = list(dict.fromkeys(keeper['retained_names'] + old.get('retained_names', []) + [old['name'], old['name'].replace('—', '-')]))
    for field in ['source_scopes', 'related_platform_offer_refs', 'source_supported_platform_scope_refs', 'confirmed_arrangement_ids']:
        keeper[field] = list(dict.fromkeys(keeper.get(field, []) + old.get(field, [])))
    retirement = {**decision, 'option_id': pid, 'status': 'RETIRED_ALIAS_RETAINED_IN_HISTORY'}
    old.update(counted_as_individual_option=False, count_class='Retired alias - historical identity retained', catalogue_retirement=retirement)
    register['catalogue_retirements'].append(retirement)
    register['aliases'].append({'alias_id': decision['decision_id'] + ':' + pid, 'source': old['name'],
        'source_option_id': pid, 'targets': [WHITE], 'target_option_ids': [WHITE],
        'relationship': 'Owner-consolidated finish listing', 'reason': decision['owner_quote'],
        'evidence': str(OUT / 'owner-decision.json'), 'individual_count_increment': 0})
keeper['merged_option_source_records'] = OLD
register['active_option_ids'] = [pid for pid in original['active_option_ids'] if pid not in OLD]
register['retired_option_ids'] = list(dict.fromkeys(original['retired_option_ids'] + OLD))
register['current_product_option_aliases'] = {**register.get('current_product_option_aliases', {}), **{pid: WHITE for pid in OLD}}
register['latest_frozen_fish_finish_consolidation'] = decision
active = set(register['active_option_ids'])
summary = register['summary']
for field in ['individual_options_on_identified_components', 'individual_named_working_options', 'current_option_records', 'options_with_six_working_fields']:
    summary[field] = original['summary'][field] - 3
summary['current_field_groups'] -= 18
summary['retired_option_records'] = len(register['retired_option_ids'])
summary['individual_options_with_dropbox_reference'] = sum(bool(options[pid].get('file_id')) for pid in active)
summary['active_component_ids_including_provisional'] = len({options[pid]['canonical_component_id'] for pid in active if options[pid].get('canonical_component_id')})
groups = register['current_working_design_group_projection']
for group in groups['groups']:
    group['active_option_ids'] = [pid for pid in group.get('active_option_ids', []) if pid in active]
groups['active_individual_finish_option_count'] = len(active)
groups['retained_option_record_count'] = len(register['options'])
groups['latest_finish_listing_consolidation'] = decision
for pid, row in options.items():
    assert row['specifications'] == before[pid]['specifications']
    assert row.get('master_fields') == before[pid].get('master_fields')
    assert row.get('selling_details') == before[pid].get('selling_details')
    if pid not in NAMES and pid not in OLD:
        assert row == before[pid], pid
assert len(active) == 184 and len(register['options']) == 191
write(OUT / 'canonical-master-register.json', register)

gallery_dir = OUT / 'gallery-projection'; gallery_dir.mkdir()
gallery = gallery_dir / 'complete-image-platform-register.sqlite'
shutil.copy2(source_gallery, gallery)
additions = []
with closing(sqlite3.connect(gallery)) as db:
    db.execute('CREATE TABLE products_before_frozen_fish_finish_merge AS SELECT * FROM products')
    for pid in OLD + list(NAMES):
        row = options[pid]
        db.execute('UPDATE products SET name=?,record_json=? WHERE product_id=?', (row['name'], json.dumps(row, ensure_ascii=False), pid))
    known = set(db.execute('SELECT file_id,intended_use,status FROM associations WHERE product_id=?', (WHITE,)))
    for pid in OLD:
        for aid, _, fid, use, status, raw in db.execute('SELECT * FROM associations WHERE product_id=?', (pid,)).fetchall():
            if (fid, use, status) in known:
                continue
            record = json.loads(raw)
            new_id = hashlib.sha256((decision['decision_id'] + ':' + aid).encode()).hexdigest()[:24]
            record.update(association_id=new_id, product_id=WHITE,
                          retained_source_association_id=aid, retained_source_option_id=pid,
                          current_listing_grouping_decision=decision['decision_id'])
            db.execute('INSERT INTO associations VALUES(?,?,?,?,?,?)', (new_id, WHITE, fid, use, status, json.dumps(record, ensure_ascii=False)))
            known.add((fid, use, status)); additions.append({'id': new_id, 'source': aid, 'old_product_id': pid, 'file_id': fid, 'use': use})
    offers = set(db.execute('SELECT offer_ref,relationship FROM source_product_links WHERE product_id=?', (WHITE,)))
    for pid in OLD:
        for offer, _, relationship, raw in db.execute('SELECT * FROM source_product_links WHERE product_id=?', (pid,)).fetchall():
            if (offer, relationship) in offers:
                continue
            record = json.loads(raw)
            record.update(product_id=WHITE, retained_source_option_id=pid,
                          current_listing_grouping_decision=decision['decision_id'], new_exact_individual_variant_assignment=False)
            db.execute('INSERT INTO source_product_links VALUES(?,?,?,?)', (offer, WHITE, relationship, json.dumps(record, ensure_ascii=False)))
            offers.add((offer, relationship))
    db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)', ('frozen_fish_finish_consolidation', json.dumps(decision)))
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
write(OUT / 'association-additions.json', additions)
seal = {'status': 'PREPARED_THREE_FROZEN_FISH_FINISH_LISTINGS', 'decision': decision,
        'register_sha256': sha(OUT / 'canonical-master-register.json'), 'database_sha256': sha(gallery),
        'source_register': manifest['input_register'], 'source_gallery': manifest['input_gallery'],
        'active_options': 184, 'retained_options': 191, 'retired_options': 7,
        'association_additions': len(additions), 'physical_specifications_changed': 0, 'native_writes': 0}
write(gallery_dir / 'sealed-handoff.json', seal)
next_pointer = deepcopy(pointer)
next_pointer.update(recorded_utc=stamp, status='CURRENT184_FROZEN_FISH_THREE_FINISHES_APP_SOURCE',
    register=str((OUT / 'canonical-master-register.json').relative_to(BASE)), register_sha256=seal['register_sha256'],
    summary=summary, publication_receipt=str((OUT / 'publication-receipt.json').relative_to(BASE)),
    latest_frozen_fish_finish_consolidation=decision,
    workbook_status='Historical 187-option snapshot; the app and next review export use the current 184-option register.',
    historical_gallery_before_frozen_fish_finish_consolidation=pointer['current_published_gallery_projection'])
next_pointer['latest_corrections'] += ' Owner consolidated Frozen Fish into White, Terracotta and Verdigris finish listings; three old White options retained as aliases. Existing working specifications and source claims preserved.'
next_pointer['current_published_gallery_projection'] = {'status': seal['status'],
    'path': str((gallery_dir / 'sealed-handoff.json').relative_to(BASE)), 'sha256': sha(gallery_dir / 'sealed-handoff.json'),
    'register_sha256': seal['register_sha256'], 'database_sha256': seal['database_sha256'],
    'active_options': 184, 'retained_options': 191, 'source_platform_associations_preserved': True,
    'association_additions': str((OUT / 'association-additions.json').relative_to(BASE))}
write(OUT / 'next-current-master.json', next_pointer)
write(OUT / 'input-manifest.json', manifest)
stage = OUT / 'staging-project/sculpture-catalogue'
staged_pointer = deepcopy(next_pointer)
staged_pointer['register'] = str(OUT / 'canonical-master-register.json')
staged_pointer['current_published_gallery_projection']['path'] = str(gallery_dir / 'sealed-handoff.json')
write(stage / 'current-master.json', staged_pointer)
print(json.dumps({'directory': str(OUT), 'active_options': 184, 'retained_options': 191, 'new_associations': len(additions), 'published': False}))
