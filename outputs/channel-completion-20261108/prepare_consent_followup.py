"""Prepare a narrow 884-column master follow-up for verified consent and photo review."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import sys
import urllib.request

ROOT = Path('/Users/tprice/Documents/boldstone')
PACKET = Path(__file__).parent
OUT = PACKET / 'catalogue-consent-followup'
OUT.mkdir(exist_ok=True)
sys.path[:0] = [str(ROOT / 'catalogue-review'), str(ROOT / 'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx, column
from delete_dropbox import connection

load = lambda p: json.loads(Path(p).read_text())
sha = lambda b: hashlib.sha256(b).hexdigest()
pointer = load(ROOT / 'sculpture-catalogue/current-master.json')
source = pointer['current_app_review_workbook']
body = Path(source['path']).read_bytes()
assert sha(body) == source['sha256']
assert source['dropbox']['rev'] == '65fca85cd86a70c0dea29'
(OUT / 'source-pointer-before.json').write_text(json.dumps(pointer, indent=2) + '\n')
(OUT / 'previous-catalogue.xlsx').write_bytes(body)
with connection(ROOT) as (db, _):
    m = db.files_get_metadata(source['dropbox']['id'])
    assert m.rev == source['dropbox']['rev'] and m.path_display == source['dropbox']['path_display']
    dm, response = db.files_download('rev:' + m.rev)
    try:
        assert dm.id == m.id and response.content == body
    finally:
        response.close()
    metadata = {k: str(getattr(m, k)) if k.endswith('modified') else getattr(m, k)
                for k in ['id', 'path_display', 'rev', 'size', 'content_hash', 'server_modified', 'client_modified']}
(OUT / 'previous-dropbox-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as r:
    app = json.load(r)
(OUT / 'app-specifications.json').write_text(json.dumps(app) + '\n')
old = Xlsx(OUT / 'previous-catalogue.xlsx')
sheet = 'Wall Sculptures'
headers = {old.value(sheet, column(c) + '7'): c for c in range(1, 885)}
assert len(headers) == 884 and headers['pinterest_larger_selected_photo_urls'] == 884
by_id = {old.value(sheet, 'AA' + str(r)): r for r in range(8, 189)}
assert len(by_id) == 181
new_headers = ['pinterest_larger_unselected_photo_count', 'pinterest_larger_unselected_photo_ids',
               'pinterest_larger_unselected_photo_urls', 'pinterest_unselected_photo_review_notes']
assert not set(new_headers) & set(headers)
first = 885
headers.update({h: first + i for i, h in enumerate(new_headers)})
patches = []


def patch(h, row, value, style='text'):
    address = column(headers[h]) + str(row)
    before = old.value(sheet, address)
    if before == value:
        return
    assert old.formula(sheet, address) is None
    assert not isinstance(value, str) or len(value) <= 32767
    patches.append(dict(sheet=sheet, cell=address, before=before, value=value, style=style, field=h))


def date(h, row, time):
    before = old.value(sheet, column(headers[h]) + str(row))
    numeric = isinstance(before, (float, int))
    value = ((datetime.fromisoformat(time.replace('Z', '+00:00'))
              - datetime(1899, 12, 30, tzinfo=timezone.utc)).total_seconds() / 86400
             if numeric else 'Checked UTC: ' + time)
    patch(h, row, value, 'utc' if numeric else 'text')


tasks = load(PACKET / 'platform-task-evidence.json')
photos = load(PACKET / 'pinterest-unselected-photo-options.json')
photo_by_id = {p['catalogue_id']: p for p in photos['products']}
assert len(photo_by_id) == 4
for h in new_headers:
    patch(h, 7, h, 'header')
for pid, row in by_id.items():
    entries = tasks['products'][pid]['platforms']
    patch('platform_tasks_json', row, json.dumps(entries, ensure_ascii=False, separators=(',', ':')))
    patch('platform_tasks_summary', row, '; '.join(code + ': ' + e['state'] for code, e in entries.items()))
    date('platform_tasks_checked_utc', row, tasks['checked_at'])
    p = entries['pinterest']
    if p['state'] == 'not_targeted':
        continue
    tracking = next(t for t in p['tasks'] if t['id'] == 'pinterest_tracking')
    assert tracking['state'] == 'verified'
    patch('pinterest_tag_verification', row, tracking['detail'])
    if any(t['id'] == 'primary_image_size' for t in p['tasks']):
        q = photo_by_id.get(pid)
        candidates = q['qualifying_candidates'] if q else []
        patch('pinterest_larger_unselected_photo_count', row, len(candidates), 'integer')
        if q:
            patch('pinterest_larger_unselected_photo_ids', row, '\n'.join(c['id'] for c in candidates))
            patch('pinterest_larger_unselected_photo_urls', row, '\n'.join(c['url'] for c in candidates))
            details = '; '.join(c['name'] + ': ' + ' × '.join(map(str, c['header_check']['dimensions'])) + ' px' for c in candidates)
            patch('pinterest_unselected_photo_review_notes', row, q['visual_review_note'] + ' ' + details
                  + '. Current Dropbox revision metadata and bounded original headers checked; full original hash not recomputed. '
                  'Small previews visually reviewed. Existing purpose and primary choices unchanged. These are proposals, not published primary replacements.')
plan = dict(created_utc=datetime.now(timezone.utc).isoformat(), source_sha256=sha(body),
    scope='Verified live Pinterest matched browser events and repaired separate-category consent ordering; four additional unselected high-resolution photo review opportunities. '
          'No product facts, prices, labour, GTINs, stock, website images or app primary/purpose choices changed.',
    new_headers=new_headers, first_added_column=first, last_added_column=888, patches=patches,
    counts=dict(instagram_published=0, facebook_published=0, linkedin_published=0, pinterest_live_event_types_verified=3,
                consent_regression_checks=17, qualifying_unselected_originals=21,
                products_with_unselected_photo_options=4, gtins_assigned=0, pinterest_appeals_used=0),
    previews=[dict(name='unselected-photo-review', range=column(first) + '7:' + column(first + 1) + '10')])
(OUT / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
for name in ['build.mjs', 'preserve.py', 'independent_verify.py', 'publish.py']:
    shutil.copy2(PACKET / 'catalogue-followup' / name, OUT / name)
p = OUT / 'preserve.py'
s = p.read_text().replace('brandboom_duplicate_photo_associations_corrected=1)',
    'brandboom_duplicate_photo_associations_corrected=1,pinterest_live_browser_event_types=3,\n'
    '    pinterest_consent_regression_checks=17,qualifying_unselected_photo_alternatives_products=4)')
p.write_text(s)
p = OUT / 'publish.py'
s = p.read_text().replace("updated['photo_and_brandboom_followup_20261108']=", "updated['consent_and_photo_review_followup_20261108']=")
s = s.replace('brandboom_duplicate_photo_associations_corrected=1,',
    'brandboom_duplicate_photo_associations_corrected=1,pinterest_live_browser_event_types=3,\n'
    '        pinterest_consent_regression_checks=17,qualifying_unselected_photo_alternatives_products=4,')
p.write_text(s)
dependency = Path('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')
if not (OUT / 'node_modules').exists():
    (OUT / 'node_modules').symlink_to(dependency, target_is_directory=True)
print(json.dumps(dict(patches=len(patches), new_fields=4, source_revision=metadata['rev'], source_sha256=sha(body))))
