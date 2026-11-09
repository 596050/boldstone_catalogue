"""Narrow follow-up against the already released 880-column master."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import sys

ROOT = Path('/Users/tprice/Documents/boldstone')
PACKET = Path(__file__).parent
OUT = PACKET / 'catalogue-followup'
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
shutil.copy2(PACKET / 'app-specifications-followup.json', OUT / 'app-specifications.json')
old = Xlsx(OUT / 'previous-catalogue.xlsx')
sheet = 'Wall Sculptures'
headers = {old.value(sheet, column(c) + '7'): c for c in range(1, 881)}
assert len(headers) == 880 and headers['google_manufacturer_checked_utc'] == 880
by_id = {old.value(sheet, 'AA' + str(r)): r for r in range(8, 189)}
assert len(by_id) == 181
new_headers = ['pinterest_primary_original_dimensions_px', 'pinterest_larger_selected_photo_count',
               'pinterest_larger_selected_photo_ids', 'pinterest_larger_selected_photo_urls']
assert not set(new_headers) & set(headers)
first = 881
headers.update({h: first + i for i, h in enumerate(new_headers)})
patches = []
serial = lambda t: (datetime.fromisoformat(t.replace('Z', '+00:00'))
                    - datetime(1899, 12, 30, tzinfo=timezone.utc)).total_seconds() / 86400


def patch(h, row, value, style='text'):
    address = column(headers[h]) + str(row)
    before = old.value(sheet, address)
    if before == value:
        return
    assert old.formula(sheet, address) is None
    assert not isinstance(value, str) or len(value) <= 32767
    patches.append(dict(sheet=sheet, cell=address, before=before,
                        value=value, style=style, field=h))


def date(h, row, time):
    before = old.value(sheet, column(headers[h]) + str(row))
    numeric = isinstance(before, (float, int))
    patch(h, row, serial(time) if numeric else 'Checked UTC: ' + time,
          'utc' if numeric else 'text')


for h in new_headers:
    patch(h, 7, h, 'header')
tasks = load(PACKET / 'platform-task-evidence.json')
review = load(PACKET / 'pinterest-original-resolution-review.json')
bb = load(PACKET / 'brandboom-native-restore-verification.json')
fix = load(PACKET / 'brandboom-duplicate-photo-fix.json')
for pid, row in by_id.items():
    entries = tasks['products'][pid]['platforms']
    patch('platform_tasks_json', row, json.dumps(entries, ensure_ascii=False, separators=(',', ':')))
    patch('platform_tasks_summary', row, '; '.join(code + ': ' + e['state'] for code, e in entries.items()))
    date('platform_tasks_checked_utc', row, tasks['checked_at'])
    if entries['brandboom']['state'] == 'not_targeted':
        continue
    patch('brandboom_restoration_status', row,
          'Native all-product export independently verified: exact 176 existing SKUs and 13 saved fields; '
          '2,288 comparisons, zero differences, zero inactive records. No new product created. '
          'The export contains no image columns and does not establish all galleries or Marketplace publication.')
    date('brandboom_checked_utc', row, fix['checked_at'] if pid == fix['catalogue_id'] else bb['checked_at'])
    if pid == fix['catalogue_id']:
        patch('brandboom_image_verification', row,
              'Corrected one extra byte-identical association: media 34736843 moved to recoverable Media Bin; '
              '34706371 retained. Saved once, reloaded and reopened: all 17 expected selected photo IDs verified; '
              'primary 34706366 unchanged; wholesale £109.25 unchanged. Distinct owner-selected Dropbox '
              'records with identical rendered pixels retained. Other galleries remain separately unverified.')
for p in review['products']:
    pid = p['catalogue_id']
    row = by_id[pid]
    entry = tasks['products'][pid]['platforms']['pinterest']
    action = next(t for t in entry['tasks'] if t['id'] == 'primary_image_size')
    candidates = [a for a in p['higher_resolution_listing_candidates']
                  if a['hosted_check']['meets_documented_dimensions']]
    patch('pinterest_primary_image_size_check', row, action['detail'])
    date('pinterest_audit_checked_utc', row, review['summary']['checked_at'])
    patch('pinterest_primary_original_dimensions_px', row, ' × '.join(map(str, p['primary']['original']['dimensions'])))
    patch('pinterest_larger_selected_photo_count', row, len(candidates), 'integer')
    patch('pinterest_larger_selected_photo_ids', row, '\n'.join(a['id'] for a in candidates))
    patch('pinterest_larger_selected_photo_urls', row, '\n'.join(a['hosted_check']['url'] for a in candidates))

plan = dict(created_utc=datetime.now(timezone.utc).isoformat(), source_sha256=sha(body),
    scope='Original resolution and selected/hosted alternatives for 96 Pinterest tasks; native Brandboom field '
          'readback for 176 existing records; one recoverable duplicate photo association correction; '
          'updated dated app task evidence. No product facts, prices, GTINs, stock or app image choices changed.',
    new_headers=new_headers, first_added_column=first, last_added_column=884, patches=patches,
    counts=dict(instagram_published=0, facebook_published=0, linkedin_published=0,
                primary_original_dimensions_confirmed=96, products_with_selected_qualifying_alternatives=28,
                brandboom_native_records_verified=176, brandboom_native_field_comparisons=2288,
                brandboom_duplicate_photo_associations_corrected=1, gtins_assigned=0),
    previews=[dict(name='photo-options', range=column(first) + '7:' + column(first + 1) + '9')])
(OUT / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
for name in ['build.mjs', 'preserve.py', 'independent_verify.py', 'publish.py']:
    shutil.copy2(PACKET / 'catalogue' / name, OUT / name)
# Preserve the verified base workflow while making the follow-up receipts exact.
p = OUT / 'preserve.py'
s = p.read_text().replace('linkedin_new_publications_recorded=5,instagram_new_publications_recorded=5,facebook_new_publications_recorded=5,',
    'linkedin_new_publications_recorded=0,instagram_new_publications_recorded=0,facebook_new_publications_recorded=0,')
s = s.replace("manufacturer_logo_corrected=True,google_brand_names_aligned=176)",
    "manufacturer_logo_corrected=True,google_brand_names_aligned=176,\n    primary_original_dimensions_confirmed=96,qualifying_selected_photo_alternatives_products=28,\n    brandboom_native_field_comparisons=2288,brandboom_duplicate_photo_associations_corrected=1)")
p.write_text(s)
p = OUT / 'publish.py'
s = p.read_text().replace("updated['social_and_merchant_evidence_20261108']=", "updated['photo_and_brandboom_followup_20261108']=")
s = s.replace("pinterest_profile_shop_url='https://boldstonesculpture.com',pinterest_merchant_approved=False,", "pinterest_profile_shop_url='https://boldstonesculpture.com',pinterest_merchant_approved=False,\n        primary_original_dimensions_confirmed=96,qualifying_selected_photo_alternatives_products=28,brandboom_duplicate_photo_associations_corrected=1,")
p.write_text(s)
dependency = Path('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')
if not (OUT / 'node_modules').exists():
    (OUT / 'node_modules').symlink_to(dependency, target_is_directory=True)
print(json.dumps({'patches': len(patches), 'new_fields': len(new_headers),
                  'source_revision': metadata['rev'], 'source_sha256': sha(body)}))
