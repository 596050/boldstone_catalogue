from pathlib import Path
import sys,json
from http.server import ThreadingHTTPServer
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'work'))
from server import Application,Handler
from projection import Projection
app=Application(root.parents[2],root/'qa-state',auto_sync=False)
app.sync.install(json.loads((root/'qa-state/qa-inventory.json').read_text()))
view=app.projection()
folders={}
for aid,pids in view.group_defaults.items():
 a=view.cat.assets[aid]
 folders.setdefault(a.get('folder_url'),{'label':a.get('folder_label'),'family':a.get('family'),'products':[view.cat.products[p]['name'] for p in pids],'files':0})['files']+=1
(root/'group-defaults-audit.json').write_text(json.dumps(list(folders.values()),indent=2))
server=ThreadingHTTPServer(('127.0.0.1',8768),Handler);server.daemon_threads=True;server.app=app
server.serve_forever()
