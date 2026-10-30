"""Verify a bounded family's exact current reference IDs and write its link report."""
import argparse
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

parser = argparse.ArgumentParser()
parser.add_argument('lane', type=Path)
args = parser.parse_args()
H = args.lane.resolve()
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda x: html.escape(str(x), quote=True)
write = lambda p, x: Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
assert not (H / 'sealed-handoff.json').exists(), 'Do not overwrite a sealed audit'
scope = read(H / 'scope.json')
receipts = read(H / 'metadata-receipts.json')
assert receipts['scope_sha256'] == sha(H / 'scope.json')
account = receipts['account']['structuredContent']
assert account['root_namespace_id'] == account['home_namespace_id'] == '202238505'
assert sha(scope['source_register']) == scope['source_register_sha256']
observed = {x['requested_id']: x for x in receipts['observations']}
assert len(observed) == len(receipts['observations']) and set(observed) == set(scope['query_ids'])
rows = []
root = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/'
for option in scope['options']:
    file_response = observed[option['file_id']]['response']
    folder_response = observed[option['folder_id']]['response']
    file_data = file_response.get('structuredContent', {})
    folder_data = folder_response.get('structuredContent', {})
    file = file_data.get('file')
    folder = folder_data.get('folder')
    issues = []
    if file_response.get('isError') or file_data.get('metadata_type') != 'file':
        issues.append('Selected file metadata unavailable; no absence or deletion inferred')
    if folder_response.get('isError') or folder_data.get('metadata_type') != 'folder':
        issues.append('Containing folder metadata unavailable')
    if file and folder:
        assert file['id'] == option['file_id'] and folder['id'] == option['folder_id']
        assert file['path_display'].startswith(root) and folder['path_display'].startswith(root)
        if str(Path(file['path_display']).parent) != folder['path_display']:
            issues.append('Selected file has a different current parent')
        if unquote(urlsplit(option['folder_url']).path.removeprefix('/home')) != folder['path_display']:
            issues.append('Saved folder link differs from current folder path')
        image = urlsplit(option['image_url'])
        if image.path.startswith('/preview/'):
            expected_file = unquote(image.path.removeprefix('/preview'))
        elif image.path.startswith('/home/') and parse_qs(image.query).get('preview'):
            expected_file = unquote(image.path.removeprefix('/home')) + '/' + parse_qs(image.query)['preview'][0]
        else:
            expected_file = None
            issues.append('Image URL form needs explicit review')
        if expected_file and expected_file != file['path_display']:
            issues.append('Saved image link differs from the exact current file path')
    fields = option['master_fields']
    assert len(fields) == 6
    rows.append({'option_id': option['product_id'], 'name': option['name'], 'file_id': option['file_id'],
                 'folder_id': option['folder_id'], 'image_url': option['image_url'], 'folder_url': option['folder_url'],
                 'status': 'SELECTED_FILE_AND_CONTAINING_FOLDER_METADATA_VERIFIED' if not issues else 'REFERENCE_NEEDS_REVIEW',
                 'issues': issues, 'native_file_metadata': file, 'native_folder_metadata': folder,
                 'working_fields': fields, 'new_image_selection': False, 'source_option_object': option})
summary = {'current_options_checked': len(rows), 'selected_files_verified': sum(not r['issues'] for r in rows),
           'containing_folders_verified': sum(bool(r['native_folder_metadata']) for r in rows),
           'new_metadata_conflicts': sum(bool(r['issues']) for r in rows), 'working_field_objects_retained': len(rows) * 6,
           'new_physical_verifications': 0, 'new_native_or_platform_writes': 0, 'live_binary_downloads': 0,
           'live_sandbox_integration_tested': False}
result = {'schema': 'boldstone.family-primary-reference-observations.v1', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'family': scope['family'], 'scope': 'Only the selected file and containing folder for each current catalogue option. This does not certify all family assets, image origin, physical specifications or manufacturing counts.',
          'source_register': scope['source_register'], 'source_register_sha256': scope['source_register_sha256'],
          'source_scope_sha256': sha(H / 'scope.json'), 'summary': summary, 'rows': rows,
          'source_photo_roles_and_owner_holds_unchanged': True}
write(H / 'navigation-findings.json', result)
cards = []
for index, row in enumerate(rows, 1):
    print(f"ITEM {index}: {row['name']}\nStatus: {row['status']}\nImage: {row['image_url']}\nFolder: {row['folder_url']}")
    table = []
    for key, field in row['working_fields'].items():
        value = field['display'].split('\n')[0]
        table.append('<tr><th>' + esc(key) + '</th><td>' + esc(value) + '<details><summary>Existing qualification and source</summary><pre>' + esc(json.dumps(field, ensure_ascii=False, indent=2)) + '</pre></details></td></tr>')
    cards.append('<article id="' + esc(row['option_id']) + '"><h2>' + str(index) + '. ' + esc(row['name']) + '</h2><p>' + ('Selected file and containing folder metadata verified.' if not row['issues'] else esc('; '.join(row['issues']))) + '</p><p><a href="' + esc(row['image_url']) + '">Selected image</a> · <a href="' + esc(row['folder_url']) + '">Containing folder</a></p><table>' + ''.join(table) + '</table><p><small>File ID: ' + esc(row['file_id']) + '<br>Folder ID: ' + esc(row['folder_id']) + '<br>File revision: ' + esc((row['native_file_metadata'] or {}).get('rev', 'Unavailable')) + '</small></p></article>')
title = scope['family'] + ' selected images and working specifications'
text = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>' + esc(title) + '</title><style>body{font:17px/1.5 Arial,sans-serif;max-width:1050px;margin:40px auto;padding:0 24px;color:#222}h1{font-size:30px}h2{font-size:23px}article{border-top:1px solid #ccc;margin-top:30px;padding-top:15px}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #ddd;padding:10px}th{width:25%}a{color:#15549b}details{font-size:14px;margin:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}small{overflow-wrap:anywhere}</style></head><body><h1>' + esc(title) + '</h1><p>' + str(summary['current_options_checked']) + ' current catalogue options. ' + str(summary['selected_files_verified']) + ' selected files and ' + str(summary['containing_folders_verified']) + ' containing folders verified through fresh stable-ID metadata reads. Existing image selections, six working fields and owner holds remain.</p><p>This is a navigation check. Image contents and origin, actual dimensions, weight, fitted hardware and physical stock were not newly verified. Historical naming holds remain. No image bytes were downloaded or changed.</p>' + ''.join(cards) + '</body></html>'
(H / 'review.html').write_text(text)
write(H / 'sealed-handoff.json', {'schema': 'boldstone.family-reference-handoff-seal.v1',
      'status': 'SEALED_SCOPED_READ_ONLY_METADATA_FINDINGS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
      'family': scope['family'], 'summary': summary,
      'files': [{'path': str(H / name), 'sha256': sha(H / name)} for name in ['scope.json', 'metadata-receipts.json', 'navigation-findings.json', 'review.html']],
      'reviewer_script': {'path': str(Path(__file__).resolve()), 'sha256': sha(__file__)},
      'canonical_publication_requested': False})
print(json.dumps({'status': 'SEALED', **summary, 'seal_sha256': sha(H / 'sealed-handoff.json'), 'review': str(H / 'review.html')}))
