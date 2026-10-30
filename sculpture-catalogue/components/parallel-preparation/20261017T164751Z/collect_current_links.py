"""Read existing links for reviewed examples; never create or change sharing."""
from pathlib import Path
import argparse, hashlib, json, sys
from urllib.parse import quote

R = Path(__file__).parent
P = Path(json.loads((R / 'Live_Metadata_Location.json').read_text())['private_metadata_directory'])
sys.path.insert(0, '/Users/tprice/Library/Application Support/BoldstoneImageConsistency/identity-resolution-20261016T120156Z')
import classification_executor as e

def save(path, obj):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)

def examples(obj):
    if isinstance(obj, dict):
        if obj.get('file_id'):
            yield obj
        for value in obj.values():
            yield from examples(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from examples(value)

def main():
    assert json.loads((R / 'Fake_Adapter_Gate.json').read_text())['passed'] == 74
    census = json.loads((P / 'Native_Census.json').read_text())
    heads = {x['id']: x for x in census['entries']}
    targets = set()
    for worker in sorted(R.glob('worker-*')):
        packet = worker / 'packets.json'
        if not packet.exists():
            packet = worker / 'packets.partial.json'
        if packet.exists():
            # Other examples get current account-path deep links in the merger.
            # Query existing sharing only for primaries to keep this lane fast.
            primaries = [x.get('primary_example') for x in json.loads(packet.read_text())['entries']]
            for item in examples(primaries):
                for key in ['file_id', 'folder_id']:
                    if item.get(key):
                        targets.add(item[key])
    output = R / 'Current_Example_Links.json'
    existing = json.loads(output.read_text()) if output.exists() else {'entries': {}}
    rows = existing['entries']
    pending = sorted(targets - set(rows))
    rawdir = P / 'existing-links'
    rawdir.mkdir(exist_ok=True)
    api = None
    try:
        if pending:
            api = e.f.n.AuditAPI()
        for i, item_id in enumerate(pending, 1):
            head = heads.get(item_id)
            if not head:
                rows[item_id] = {'id': item_id, 'status': 'ABSENT_FROM_CURRENT_CENSUS', 'checked_utc': e.f.n.now()}
                continue
            rawpages = []
            links = []
            cursor = None
            try:
                while True:
                    result = api.read('sharing_list_shared_links', cursor=cursor) if cursor else api.read('sharing_list_shared_links', path=item_id, direct_only=True)
                    raw = e.f.n.sdk_json(result)
                    rawpages.append(raw)
                    for link in raw.get('links', []):
                        matches = link.get('id') == item_id or (not link.get('id') and link.get('path_lower') == head.get('path_lower'))
                        if matches and link.get('url'):
                            links.append({'url': link['url'], 'id': link.get('id'), 'path_lower': link.get('path_lower')})
                    if not result.has_more:
                        break
                    cursor = result.cursor
                    if not cursor:
                        raise RuntimeError('SHARED_LINK_CURSOR_MISSING')
                key = hashlib.sha256(item_id.encode()).hexdigest()
                save(rawdir / (key + '.json'), {'id': item_id, 'checked_utc': e.f.n.now(), 'pages': rawpages})
                rows[item_id] = {
                    **head, 'checked_utc': e.f.n.now(),
                    'status': 'CURRENT_ID_WITH_EXISTING_LINKS' if links else 'CURRENT_ID_ACCOUNT_LINK_ONLY',
                    'existing_shared_links': links, 'pagination_exhausted': True,
                    'account_preview_url': 'https://www.dropbox.com/preview' + quote(head['path'], safe='/'),
                    'account_preview_url_basis': 'Constructed account deep link from current native path; authenticated browser opening not tested',
                    'remote_mutations': 0,
                }
            except Exception as exc:
                rows[item_id] = {**head, 'checked_utc': e.f.n.now(), 'status': 'EXISTING_LINK_LOOKUP_FAILED', 'error_type': type(exc).__name__, 'account_preview_url': 'https://www.dropbox.com/preview' + quote(head['path'], safe='/'), 'remote_mutations': 0}
            save(output, {'recorded_utc': e.f.n.now(), 'native_census_utc': census['recorded_utc'], 'scope': 'Prepared worker examples only; pre-existing sharing links read without creation', 'entries': rows, 'remote_mutations': 0})
            if i % 10 == 0 or i == len(pending):
                print(json.dumps({'resolved_this_pass': i, 'pending_this_pass': len(pending), 'total_cached': len(rows)}), flush=True)
    finally:
        if api:
            api.close()
    print(json.dumps({'status': 'READ_ONLY_LINK_PASS_COMPLETE', 'target_ids': len(targets), 'cached_ids': len(rows), 'remote_mutations': 0}), flush=True)

if __name__ == '__main__':
    main()
