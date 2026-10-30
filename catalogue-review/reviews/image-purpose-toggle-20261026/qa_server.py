from pathlib import Path
import sys
from http.server import ThreadingHTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from server import Application, Handler
from dropbox_sync import read_inventory
root=Path(__file__).resolve().parent
app=Application(root.parents[2], root/'qa-state', auto_sync=False)
inventory=read_inventory(Path.home()/'Library/Application Support/BoldstoneReview/dropbox-sync/inventory.json')
# Test against the current native records, using only the QA/local catalogue
# preview cache; production runtime media paths stay outside this sandbox.
inventory['media']={}
app.sync.install(inventory)
server=ThreadingHTTPServer(('127.0.0.1',8768), Handler)
server.daemon_threads=True
server.app=app
server.serve_forever()
