"""Prepare one scoped identity review without changing catalogue or app choices."""
from pathlib import Path
import hashlib
import html
import json
import os
import sqlite3
from datetime import datetime, timezone
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'sculpture-catalogue'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p, x: Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
now = datetime.now(timezone.utc).isoformat()
pointer_path = BASE / 'current-master.json'
p = read(pointer_path)
assert sha(pointer_path) == '9083266b288bfef81f806c3975a18a8dc1bb5268a984152de64852bbd5bf3c1c'
register = BASE / p['register']
assert sha(register) == p['register_sha256']
g = read(register)
option = next(x for x in g['options'] if x['product_id'] == 'BSI-EBD43DF0704F')
old_review_path = BASE / 'components/parallel-reviews/o006-o007-source-photo-review-20261024-B/review.json'
case = next(x for x in read(old_review_path)['cases'] if x['offer_ref'] == 'O007')
database = BASE / 'components/parallel-reviews/all-record-image-matching-20261024-B/published-projections/20261025T121532991771Z/complete-image-platform-register.sqlite'
assert sha(database) == '26a09ffd64380e7c87dde27882b503d022bf8275510909f965718ee36aa9b591'
controls = [BASE / f for f in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']]
for f in controls:
    assert read(f)['current_master_catalogue'] == p
protected = [pointer_path, register, BASE / p['workbook'], BASE / p['preferred_review_workbook'], database, *controls]
before = {str(f): sha(f) for f in protected}
c = sqlite3.connect('file:' + quote(str(database)) + '?mode=ro', uri=True)
source = []
roles = {1: 'Complete panel, front view', 2: 'Detail', 3: 'Detail', 4: 'Detail', 5: 'Detail', 6: 'Detail', 7: 'Complete panel, left angle', 8: 'Complete panel, right angle'}
for raw, in c.execute('select record_json from source_gallery where offer_ref=?', ('O007',)):
    r = json.loads(raw)
    a = next(x for x in r['cached_renditions'] if Path(x['path']).is_file())
    actual_sha = sha(a['path'])
    if a.get('recorded_sha256'):
        assert actual_sha == a['recorded_sha256']
    source.append({k: r[k] for k in ['gallery_entry_id', 'native_product_id', 'native_media_id', 'gallery_order', 'source_url', 'captured_utc'] } | {
        'local_path': a['path'], 'sha256': actual_sha,
        'viewed_in_this_review': True, 'role': roles[r['gallery_order']],
        'representation': 'Retained website rendition; original-sized Dropbox bytes not asserted',
        'prior_review_status': r['visual_review_status'],
        'exact_original_file_binding': None,
    })
c.close()
source.sort(key=lambda x: x['gallery_order'])
assert [r['gallery_order'] for r in source] == list(range(1, 9))
viewed_native_ids = ['id:cnqzTNngPVsAAAAAAAygZw', 'id:cnqzTNngPVsAAAAAAAygaA', 'id:cnqzTNngPVsAAAAAAAygfw', 'id:cnqzTNngPVsAAAAAAAygcw']
assets = read(BASE / p['current_asset_reference_map']['path'])
native = []
for fid in viewed_native_ids:
    prev = next(x for x in case['images'] if x.get('file_id') == fid)
    current = assets[fid]
    assert sha(prev['path']) == prev['sha256']
    native.append({k: current[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url', 'name']} | {
        'local_path': prev['path'], 'sha256': prev['sha256'], 'role': prev['role'],
        'viewed_in_this_review': True, 'representation': prev['cached_representation'],
        'comparison_scope': 'Current selected MCP1 reference' if fid == option['file_id'] else 'Contrast photograph only; no identity assignment',
    })
question = {
    'status': 'PREPARED_ONE_NARROW_OWNER_DESIGN_QUESTION',
    'owner_lane': '01a144ab-1a7c-7223-a403-73a4d53d70ff',
    'question': 'Does Squarespace O007 show the same MCP1 relief design as the linked Dropbox panel, with a different finish/example, or does it belong to another Moon Crater phase?',
    'scope': 'Design identity only. No exact photograph, physical cast, size, material, fitted fixing, price, availability, SKU or Shopify binding is inferred from an answer.',
    'source_image_url': source[0]['source_url'],
    'dropbox_image_url': option['image_url'], 'dropbox_folder_url': option['folder_url'],
    'new_sku_or_product_creation_on_hold': True,
}
review = {
    'status': 'LOCAL_VISUAL_RECHECK_COMPLETE_EXACT_BINDING_UNRESOLVED',
    'recorded_utc': now, 'source_offer_ref': 'O007', 'option_id': option['product_id'],
    'name': option['name'], 'source_native_tuple': case['native_tuple'],
    'source_url': case['source_url'],
    'source_scope': 'Retained local website/export observations; no current live Squarespace or Shopify inventory claim.',
    'baseline_pointer_sha256': before[str(pointer_path)],
    'register_sha256': p['register_sha256'], 'database_sha256': sha(database),
    'source_frames_rechecked': 8, 'Dropbox_references_rechecked': 4,
    'newly_discovered_source_frames_claimed': False,
    'findings': [
        'All eight retained website frames are visually consistent with the same photographed circular relief, including its distinct central rust patch, outer rim and turquoise background.',
        'The selected MCP1 Dropbox reference has a different rust distribution, with a much broader lower-centre rust field. These are not established as the same photograph or finished specimen.',
        'The website angle frames make the outer rim clear, but images do not independently establish its numbered design. MCP2 and MCP3 comparisons are contrast references only.',
        'Current individual listing specifications remain working proposals. No website dimensions, price, material or hardware are transferred to the Dropbox option.',
    ],
    'website_images': source, 'dropbox_references': native,
    'working_fields_retained': {k: {'display': v['display'], 'state': v['state']} for k, v in option['master_fields'].items()},
    'owner_question': question,
    'canonical_changes': 0, 'app_review_writes': 0, 'native_writes': 0, 'platform_writes': 0,
    'exact_source_photo_bindings_added': 0, 'new_individual_options': 0,
    'photo_holds_reopened': 0, 'physical_verifications_added': 0,
}
dump(OUT / 'mcp1-review.json', review)
dump(OUT / 'owner-question.json', question)
esc = lambda s: html.escape(str(s), quote=True)
def image_card(r, native=False):
    image_link = r['image_url'] if native else r['source_url']
    title = r['name'] if native else f"{r['gallery_order']}. {r['source_url'].rsplit('/', 1)[-1]}"
    links = f'<a href="{esc(image_link)}">Open image</a>'
    if native:
        links += f' · <a href="{esc(r["folder_url"])}">Containing Dropbox folder</a>'
    ident = f"{r['file_id']} / {r['folder_id']}" if native else f"Squarespace media {r['native_media_id']}"
    return f'<figure><a href="{esc(image_link)}"><img src="{esc(Path(r["local_path"]).as_uri())}" alt="{esc(title)}"></a><figcaption><strong>{esc(title)}</strong><p>{esc(r["role"])}</p><p>{links}</p><small>{esc(ident)}<br>{esc(r["representation"])}</small></figcaption></figure>'
table = ''.join(f'<tr><th>{esc(k)}</th><td>{esc(v["display"])}<br><small>{esc(v["state"])}</small></td></tr>' for k,v in review['working_fields_retained'].items())
doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MCP1: one design identity check</title><style>body{{font:17px/1.5 Arial,sans-serif;color:#222;max-width:1120px;margin:32px auto;padding:0 20px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}}figure{{margin:0;padding:15px;border:1px solid #ccc}}img{{width:100%;height:430px;object-fit:contain;background:#f4f4f1}}small{{overflow-wrap:anywhere}}td,th{{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd}}th{{width:22%}}.notice{{padding:15px;background:#fff6df}}a{{color:#075993}}</style></head><body><h1>Moon Crater: one design identity check</h1><p>{esc(now)} · 188 active options retained.</p><p class="notice"><strong>{esc(question['question'])}</strong><br>{esc(question['scope'])}</p><div class="grid">{image_card(source[0])}{image_card(native[0],True)}</div><h2>What the comparison establishes</h2><ul>{''.join('<li>'+esc(s)+'</li>' for s in review['findings'])}</ul><p>Source product <code>{esc(case['native_tuple']['product_id'])}</code>, variant <code>{esc(case['native_tuple']['variant_id'])}</code>, raw SKU <code>{esc(case['native_tuple']['sku_raw'])}</code> remain a retained candidate. No new SKU is proposed while its binding is unresolved.</p><h2>All eight retained Squarespace photographs rechecked</h2><div class="grid">{''.join(image_card(x) for x in source)}</div><h2>Current Dropbox comparison references</h2><div class="grid">{''.join(image_card(x,True) for x in native)}</div><h2>Existing working details retained</h2><table>{table}</table><p>Images are unaltered cached representations. No catalogue, local app choices, Dropbox files or online records changed. Existing photograph holds remain.</p></body></html>'''
(OUT / 'index.html').write_text(doc)

# This is an active root queue note, not an immutable evidence packet.
queue = ROOT / 'reports/catalogue-terminal-walkthrough-20261024/pending-owner-design-question.json'
q = read(queue)
assert q['status'] == 'PENDING_OWNER_DESIGN_QUESTION_NO_MASTER_CHANGE'
edge = next(e for e in g['current_owner_design_equivalence_edges'] if e['edge_id'] == 'OWNER-20261024:DECOWAVES1-WHITE-VERDIGRIS-SAME-DESIGN')
assert sorted(q['option_ids']) == sorted(edge['owner_confirmed_option_ids'])
assert sha(edge['source_evidence']['path']) == edge['source_evidence']['sha256']
(OUT / 'obsolete-deco-question.before.json').write_bytes(queue.read_bytes())
q.update(status='COMPLETED_OWNER_PAIR_DESIGN_RELATIONSHIP_ALREADY_PUBLISHED', question_pending=False,
    superseded_utc=now, superseding_register_sha256=p['register_sha256'],
    superseding_edge_id=edge['edge_id'], owner_answer=edge['owner_answer_verbatim'],
    source_evidence=edge['source_evidence'], no_physical_or_commercial_fields_transferred=True,
    supersession_scope='Exact Decowaves 1 Verdigris / Frozen Decowaves 1 White pair only. Preserve previous question and evidence as history; do not re-prompt.')
tmp = queue.with_name(queue.name + '.tmp-root')
dump(tmp, q); os.replace(tmp, queue)
assert read(queue) == q
after = {str(f): sha(f) for f in protected}
assert before == after
assert len(source) == 8 and len(native) == 4
assert all(Path(x['local_path']).is_file() and sha(x['local_path']) == x['sha256'] for x in source + native)
verification = {'status': 'PASS_SAVED_REVIEW_AND_QUEUE_READBACK', 'recorded_utc': now,
    'source_frames_viewed': 8, 'Dropbox_references_viewed': 4, 'image_checksums_verified': 12,
    'protected_files_unchanged': before, 'all_three_controls_match_pointer': True,
    'obsolete_root_question_closed_by_existing_owner_evidence': True,
    'new_exact_platform_matches': 0, 'new_physical_verifications': 0, 'canonical_or_app_changes': 0,
    'native_or_platform_writes': 0,
    'outputs': {str(OUT / n): sha(OUT / n) for n in ['mcp1-review.json','owner-question.json','index.html']},
    'updated_root_queue': {'path': str(queue), 'sha256': sha(queue)}}
dump(OUT / 'verification.json', verification)
print(json.dumps({k:v for k,v in verification.items() if k not in {'protected_files_unchanged','outputs'}},ensure_ascii=False,indent=2))
print('Review: ' + str(OUT / 'index.html'))
