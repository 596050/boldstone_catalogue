"""Isolated UI test: all native responses are simulated, never Dropbox calls."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
import sys, json

root = Path(__file__).resolve().parent
sys.path[:0] = [str(root/'work'), str(root/'work/tests')]
from server import Application, Handler, ThreadingHTTPServer
from delete_dropbox import inspect_file, execute, verify_absent, CATALOGUE_ROOT
from deletions import NativeRejected
from fetch_original import OriginalError
from test_deletions import FakeDropbox

app = Application('/Users/tprice/Documents/boldstone', root/'qa-state', auto_sync=False)
client = FakeDropbox()
client.files = {}
for aid, asset in app.catalogue.assets.items():
    if asset['source'] != 'Dropbox':continue
    original = asset.get('original', {})
    path = (asset.get('provenance', {}).get('path') or '').removeprefix('ns:202238505/')
    client.files[aid] = SimpleNamespace(id=aid, name=asset['name'], rev='qa-revision',
        content_hash=original.get('dropbox_content_hash'), size=original.get('bytes'),
        path_display=path, path_lower=path.lower(), server_modified=datetime.now(timezone.utc),
        has_explicit_shared_members=False)
missing_id = 'id:cnqzTNngPVsAAAAAAAufIg'
client.gone.add(missing_id)
client.gone.add('id:cnqzTNngPVsAAAAAAAuQcA')
app.catalogue.assets[missing_id]['local_preview'] = False
app.catalogue.paths.pop(missing_id, None)
app.catalogue.preview_paths.pop(missing_id, None)
def runner(request):
    try:
        if request['action'] == 'inspect':
            result = {'file': inspect_file(client, request['binding'], CATALOGUE_ROOT, allow_missing=True)}
            if request.get('keeper_binding'):
                result['keeper'] = inspect_file(client, request['keeper_binding'], CATALOGUE_ROOT)
        elif request['action'] == 'execute':
            result = execute(client, request['reviewed'], request['binding'], CATALOGUE_ROOT, request.get('keeper'))
        else:result = verify_absent(client, request['file_id'])
        (root/'qa-native-simulation.json').write_text(json.dumps({'simulated': True, 'real_dropbox_mutations': 0,
            'simulated_delete_calls': client.calls, 'last_result': result}, indent=2))
        return result
    except OriginalError as error:raise NativeRejected(str(error)) from error
app.deletions.runner = runner
server = ThreadingHTTPServer(('127.0.0.1', 8768), Handler)
server.daemon_threads = True
server.app = app
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close()
