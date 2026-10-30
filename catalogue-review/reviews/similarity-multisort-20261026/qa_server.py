from pathlib import Path
import sys,json
from http.server import ThreadingHTTPServer
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'work'))
from server import Application,Handler
app=Application(root.parents[2],root/'qa-state',auto_sync=False)
app.sync.install(json.loads((root/'qa-state/qa-inventory.json').read_text()))
server=ThreadingHTTPServer(('127.0.0.1',8768),Handler)
server.daemon_threads=True;server.app=app
server.serve_forever()
