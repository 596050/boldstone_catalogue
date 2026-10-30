"""Refresh the user-facing record and gap list only after verified publication."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import html
import json
import re

ROOT = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
JOB = Path(__file__).resolve().parent
OUT = ROOT / 'outputs/fingerprint-product-finalization-2026-10-22'
packet = json.loads((JOB / 'product-update-packet.json').read_text())
pointer = json.loads((ROOT / 'current-master.json').read_text())
register_path = ROOT / pointer['register']
assert hashlib.sha256(register_path.read_bytes()).hexdigest() == pointer['register_sha256']
register = json.loads(register_path.read_text())
expected = {x['product_id'] for x in packet['options']}
assert {x['product_id'] for x in register['options'] if x['family'] == 'Fingerprint'} == expected
verification = json.loads((JOB / 'published-integration-verification.json').read_text())
assert verification['status'] == 'PASS' and verification['register_sha256'] == pointer['register_sha256']
assert verification['workbook_counts']['master_records'] == len(register['options'])
assert verification['workbook_sha256'] == pointer['workbook_sha256']
assert hashlib.sha256((ROOT / pointer['workbook']).read_bytes()).hexdigest() == pointer['workbook_sha256']
audit_path = Path(verification['audit'])
audit = json.loads(audit_path.read_text())
gaps = []
for x in audit['coverage']:
    role = x['individual']
    if role['status'] != 'Available':
        ref = role.get('reference') or {}
        gaps.append({'option_id': x['option_id'], 'name': x['name'],
                     'status': role['status'], 'qualification': role.get('basis', ''),
                     'image_url': ref.get('image_url'), 'folder_url': ref.get('folder_url')})
status = {'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'status': 'PUBLISHED_AND_INDEPENDENTLY_VERIFIED',
          'master_pointer': str(ROOT / 'current-master.json'),
          'register': str(register_path), 'register_sha256': pointer['register_sha256'],
          'workbook': str(ROOT / pointer['workbook']), 'workbook_sha256': pointer['workbook_sha256'],
          'current_component_identities': len(register['components']),
          'current_individual_options': len(register['options']),
          'current_fingerprint_components': 3, 'current_fingerprint_options': 6,
          'current_fingerprint_individual_image_gaps': 0,
          'catalogue_individual_image_gaps': len(gaps),
          'required_picture_actions': audit['counts']['required_picture_actions'],
          'working_specifications_not_physical_certification': True,
          'legacy_record_disposition': packet['legacy_disposition']['disposition']}
(OUT / 'publication-state.json').write_text(json.dumps(status, indent=2) + '\n')
(OUT / 'individual-image-gaps.json').write_text(json.dumps({'publication': status, 'gaps': gaps}, ensure_ascii=False, indent=2) + '\n')
esc = html.escape
message = (f'Published and independently verified: 3 Fingerprint Concentric designs × 2 finishes = 6 current product options. '
           f'Catalogue total: {len(register["components"])} identified component identities and {len(register["options"])} working individual options. '
           f'Fingerprint individual-image gaps: 0. Catalogue individual-image gaps: {len(gaps)}. '
           f'Required picture actions across all roles: {audit["counts"]["required_picture_actions"]}.')
page_path = OUT / 'index.html'
page = page_path.read_text()
page = re.sub(r'(<p class="status" id="publication-status">).*?(</p>)', lambda m: m.group(1) + esc(message) + m.group(2), page, flags=re.S)
rows = []
for x in gaps:
    links = []
    if x['image_url']:
        links.append(f'<a href="{esc(x["image_url"], quote=True)}">Existing reference</a>')
    if x['folder_url']:
        links.append(f'<a href="{esc(x["folder_url"], quote=True)}">Folder</a>')
    rows.append(f'<tr><th>{esc(x["name"])}</th><td>{esc(x["status"])}</td><td>{" · ".join(links)}</td></tr>')
gap_section = ('<section id="current-image-gaps"><h2>Remaining individual-image gaps</h2>'
               '<p>These are current catalogue options without a qualified complete individual photograph. Group and detail references remain linked. '
               'The old Left/Right Fingerprint image tasks are archived with their superseded records; they are not marked as newly photographed historical casts.</p>'
               '<table><thead><tr><th>Current option</th><th>Coverage</th><th>Existing links</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
               '<p><a href="../01a144ab-1a7c-7223-a403-73a4d53d70ff/Boldstone_Sculpture_Master_Catalogue_2026-10-20.xlsx">Open the updated master workbook</a>. '
               'Counts describe working catalogue identities and options, not physical stock or mould inventory.</p></section>')
if '<section id="current-image-gaps">' in page:
    page = re.sub(r'<section id="current-image-gaps">.*?</section>', lambda _: gap_section, page, flags=re.S)
else:
    page = page.replace('</html>', gap_section + '</html>')
page_path.write_text(page)
print(json.dumps(status, indent=2))
