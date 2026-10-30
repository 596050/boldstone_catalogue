"""Report fresh and explicitly reused reference observations without changing state."""
import argparse
import hashlib
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

parser = argparse.ArgumentParser()
parser.add_argument('lane', type=Path)
parser.add_argument('--seal', action='store_true')
args = parser.parse_args()
H = args.lane.resolve()
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda x: html.escape(str(x), quote=True)
write = lambda p, x: Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
assert not (H / 'sealed-handoff.json').exists(), 'The completed audit is immutable'
plan = read(H / 'plan.json')
assert sha(plan['source_register']) == plan['source_register_sha256']
observed = dict(plan['reused_observations'])
input_files = {str(H / 'plan.json'): sha(H / 'plan.json')}
guard_events = []
for path in sorted((H / 'receipts').glob('*.json')):
    batch = read(path)
    assert batch['plan_sha256'] == input_files[str(H / 'plan.json')]
    input_files[str(path)] = sha(path)
    if batch.get('stop'):
        guard_events.append({'path': str(path), 'status': batch['stop']})
    for entry in batch['entries']:
        identifier = entry['requested_id']
        assert identifier in plan['new_query_ids'] and identifier not in observed, identifier
        observed[identifier] = entry
amend_path = H / 'scope-amendment-001.json'
amendment = read(amend_path) if amend_path.exists() else None
archive_allowed = amendment['exact_predeclared_archive_id_paths'] if amendment else {}
if amendment:
    input_files[str(amend_path)] = sha(amend_path)
    assert amendment['new_query_ids_added'] == 0 and amendment['owner_policy']['permitted_root'] == '/BOLDSTONE MASTER'
    event = amendment['original_halt_receipt']
    assert sha(event['path']) == event['sha256']

def expected_image_path(url):
    parsed = urlsplit(url)
    if parsed.path.startswith('/preview/'):
        return unquote(parsed.path.removeprefix('/preview'))
    if parsed.path.startswith('/home/') and parse_qs(parsed.query).get('preview'):
        return unquote(parsed.path.removeprefix('/home')) + '/' + parse_qs(parsed.query)['preview'][0]
    return None

rows = []
for option in plan['eligible_options']:
    identifiers = [option['file_id'], option['folder_id']]
    evidence = [observed.get(identifier) for identifier in identifiers]
    issues, missing, native = [], [], []
    for identifier, item, kind in zip(identifiers, evidence, ['file', 'folder']):
        if item is None:
            missing.append(identifier)
            native.append(None)
            continue
        response = item['response']
        data = response.get('structuredContent', {})
        obj = data.get(kind)
        if response.get('isError') or data.get('metadata_type') != kind or obj is None:
            issues.append(kind.upper() + '_METADATA_UNAVAILABLE_NO_ABSENCE_INFERRED')
            native.append(None)
            continue
        assert obj['id'] == identifier
        path = obj['path_display']
        if not path.startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/') and archive_allowed.get(identifier) != path:
            issues.append('RETURNED_PATH_OUTSIDE_DECLARED_REFERENCE_SCOPE')
        native.append(obj)
    file, folder = native
    differences = []
    case_only = False
    verified_current_image_url = None
    verified_current_folder_url = None
    if file and folder:
        if str(Path(file['path_display']).parent) != folder['path_display']:
            differences.append('Current file parent differs from the saved containing folder')
        if expected_image_path(option['image_url']) != file['path_display']:
            differences.append('Saved image URL path differs from the current exact-ID path')
        if unquote(urlsplit(option['folder_url']).path.removeprefix('/home')) != folder['path_display']:
            differences.append('Saved folder URL path differs from the current exact-ID folder path')
        same_parent = str(Path(file['path_display']).parent) == folder['path_display']
        case_only = bool(differences) and same_parent and expected_image_path(option['image_url']).casefold() == file['path_display'].casefold() and unquote(urlsplit(option['folder_url']).path.removeprefix('/home')).casefold() == folder['path_display'].casefold()
        if same_parent:
            verified_current_folder_url = 'https://www.dropbox.com/home' + quote(folder['path_display'], safe='/')
            verified_current_image_url = verified_current_folder_url + '?preview=' + quote(file['name'], safe='')
    if missing:
        status = 'PENDING_METADATA_READ'
    elif issues:
        status = 'NATIVE_METADATA_UNAVAILABLE_OR_OUTSIDE_DECLARED_SCOPE'
    elif case_only:
        status = 'SELECTED_IDS_AND_PARENT_VERIFIED_CASE_ONLY_URL_DIFFERENCE'
    elif differences:
        status = 'FILE_AND_FOLDER_RESOLVED_WITH_NAVIGATION_DIFFERENCE'
    else:
        status = 'SELECTED_FILE_AND_CONTAINING_FOLDER_VERIFIED'
    source_kind = 'HISTORICAL_DOCUMENT_REFERENCE_INSIDE_OWNER_MASTER_ROOT' if option['file_id'] in archive_allowed else 'WALL_SCULPTURE_SELECTED_REFERENCE'
    rows.append({'option_id': option['product_id'], 'name': option['name'], 'family': option['family'],
                 'file_id': option['file_id'], 'folder_id': option['folder_id'], 'image_url': option['image_url'],
                 'folder_url': option['folder_url'], 'status': status, 'issues': issues, 'navigation_differences': differences,
                 'case_only_url_difference': case_only, 'verified_current_image_url': verified_current_image_url,
                 'verified_current_folder_url': verified_current_folder_url,
                 'pending_ids': missing, 'native_file_metadata': file, 'native_folder_metadata': folder,
                 'evidence': [{'requested_id': identifier, 'kind': item.get('evidence_kind', 'NEW_NATIVE_METADATA_READ'),
                              'recorded_utc': item.get('completed_utc'), 'source': item.get('source')} for identifier, item in zip(identifiers, evidence) if item],
                 'reference_source_class': source_kind, 'working_fields': option['master_fields'],
                 'new_photo_selection_or_physical_verification': False})
new_ids = set(observed) & set(plan['new_query_ids'])
pending_ids = set(plan['all_query_ids']) - set(observed)
statuses = Counter(row['status'] for row in rows)
summary = {'active_catalogue_options': plan['active_options'], 'in_scope_options': len(rows),
           'excluded_options': len(plan['excluded_options']), 'family_scopes': len(plan['families']),
           'unique_metadata_ids': len(plan['all_query_ids']), 'reused_metadata_observations': len(plan['reused_observations']),
           'new_metadata_reads_attempted': len(new_ids), 'new_metadata_reads_returned': sum(not observed[i]['response'].get('isError') and bool(observed[i]['response'].get('structuredContent', {}).get('metadata_type')) for i in new_ids),
           'pending_unique_metadata_reads': len(pending_ids), 'option_statuses': dict(statuses),
           'new_image_selections': 0, 'binary_downloads': 0, 'native_or_platform_writes': 0,
           'new_physical_verifications': 0, 'live_sandbox_tested': False}
current = read(B / 'current-master.json')
current_register = read(B / current['register'])
current_options = {o['product_id']: o for o in current_register['options']}
drift = []
for option in plan['eligible_options']:
    live_option = current_options.get(option['product_id'], {})
    if any(live_option.get(k) != option.get(k) for k in ['file_id', 'folder_id', 'image_url', 'folder_url', 'master_fields']):
        drift.append(option['product_id'])
summary['current_catalogue_selection_or_field_changes_since_freeze'] = drift
result = {'schema': 'boldstone.library-current-selected-reference-audit.v1', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'status': 'ALL_PLANNED_READS_ATTEMPTED' if not pending_ids else 'IN_PROGRESS', 'summary': summary,
          'source_register': plan['source_register'], 'source_register_sha256': plan['source_register_sha256'],
          'current_register_sha256': current['register_sha256'], 'guard_events_preserved': guard_events,
          'scope_amendment': {'path': str(amend_path), 'sha256': sha(amend_path)} if amendment else None,
          'rows': rows, 'excluded_options': plan['excluded_options'],
          'scope': 'Selected-reference navigation only. Prior verified reads retain their original clocks. The current observations span a review interval and are not a transaction-wide inventory, visual review or physical verification.'}
write(H / 'findings.json', result)
(H / 'families').mkdir(exist_ok=True)
style = 'body{font:17px/1.5 Arial,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px;color:#222}h1{font-size:30px}h2{font-size:22px}article{border-top:1px solid #ccc;padding:18px 0;margin-top:20px}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #ddd;padding:9px}th{width:25%}a{color:#15549b}pre{white-space:pre-wrap;overflow-wrap:anywhere}small{overflow-wrap:anywhere}details{font-size:14px;margin-top:8px}'
family_links = []
for index, (family, options) in enumerate(plan['families'].items(), 1):
    filename = str(index).zfill(3) + '-' + ''.join(c.lower() if c.isalnum() else '-' for c in family).strip('-') + '.html'
    family_rows = [r for r in rows if r['family'] == family]
    cards = []
    for row in family_rows:
        clocks = '; '.join(item['kind'] + ' at ' + str(item['recorded_utc']) for item in row['evidence'])
        fields = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v['display'].split('\n')[0]) + '<details><summary>Existing source and qualification</summary><pre>' + esc(json.dumps(v, ensure_ascii=False, indent=2)) + '</pre></details></td></tr>' for k, v in row['working_fields'].items())
        notes = row['issues'] + row['navigation_differences']
        current_links = '<p><a href="' + esc(row['verified_current_image_url']) + '">Same selected image at the observed path</a> · <a href="' + esc(row['verified_current_folder_url']) + '">Verified current folder</a></p>' if row['case_only_url_difference'] else ''
        cards.append('<article id="' + esc(row['option_id']) + '"><h2>' + esc(row['name']) + '</h2><p>' + esc(row['status']) + '</p><p><a href="' + esc(row['image_url']) + '">Saved selected image reference</a> · <a href="' + esc(row['folder_url']) + '">Saved containing folder</a></p>' + current_links + '<p>' + esc('; '.join(notes)) + '</p><p><small>' + esc(clocks) + '<br>' + esc(row['reference_source_class']) + '</small></p><table>' + fields + '</table></article>')
    page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>' + esc(family) + ' reference review</title><style>' + style + '</style></head><body><h1>' + esc(family) + ' selected references</h1><p>Current catalogue references and existing qualified working fields. Metadata observations are labelled with their actual source clocks. No new image, provenance, manufacture, measurement or stock claim was made.</p><p><a href="../index.html">Full reference review</a></p>' + ''.join(cards) + '</body></html>'
    (H / 'families' / filename).write_text(page)
    family_status = dict(Counter(r['status'] for r in family_rows))
    family_links.append('<tr><td><a href="families/' + filename + '">' + esc(family) + '</a></td><td>' + str(len(family_rows)) + '</td><td>' + esc(json.dumps(family_status)) + '</td></tr>')
exclusions = ''.join('<li>' + esc(o['name']) + ': ' + esc(o['reason']) + '</li>' for o in plan['excluded_options'])
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Current selected image and folder references</title><style>' + style + '</style></head><body><h1>Current selected image and folder references</h1><p>' + str(len(rows)) + ' in-scope catalogue options across ' + str(len(plan['families'])) + ' families. ' + str(len(plan['excluded_options'])) + ' options excluded under existing holds, another session’s work, or a missing selected identity.</p><p>New metadata reads attempted: ' + str(len(new_ids)) + '. Prior verified metadata observations reused: ' + str(len(plan['reused_observations'])) + '. Remaining metadata IDs: ' + str(len(pending_ids)) + '.</p><p>These are references for current sale options, not a physical stock count or a review of every family photograph. Existing image roles, source qualifications, estimates and owner holds remain. No image bytes were downloaded and no native or platform writes were made.</p><p>The Cup Ring archive reference is limited to its exact predeclared file and folder inside BOLDSTONE MASTER. The original over-narrow guard halt and its documented policy correction are retained in the evidence.</p><table><tr><th>Family</th><th>Options</th><th>Reference status</th></tr>' + ''.join(family_links) + '</table><h2>Excluded options</h2><ul>' + exclusions + '</ul></body></html>'
(H / 'index.html').write_text(page)
if args.seal:
    assert not pending_ids and not drift, 'Finish reads and resolve frozen/current selection drift before sealing'
    for path, digest in input_files.items():
        assert sha(path) == digest
    artifacts = [H / 'plan.json', H / 'findings.json', H / 'index.html', *sorted((H / 'families').glob('*.html')), *sorted((H / 'receipts').glob('*.json'))]
    if amendment:
        artifacts.append(amend_path)
    write(H / 'sealed-handoff.json', {'schema': 'boldstone.current-selected-reference-audit-seal.v1',
          'status': 'SEALED_ALL_PLANNED_METADATA_READS_ATTEMPTED', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'summary': summary, 'files': [{'path': str(path), 'sha256': sha(path)} for path in artifacts],
          'source_register_sha256': plan['source_register_sha256'], 'canonical_publication_requested': False,
          'scope': result['scope'], 'guard_event_and_correction_retained': bool(guard_events)})
print(json.dumps({'status': result['status'], **summary, 'report': str(H / 'index.html'), 'sealed': args.seal}))
