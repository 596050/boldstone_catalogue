import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,quote,unquote,parse_qs
H=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def display(p):return '/'+p.split('//',1)[1].lstrip('/')if p.startswith('ns:')else p
def namespace(p):return 'ns:202238505/'+display(p)
@lru_cache(maxsize=1)
def path_map():
 result={x[k]['path_display'].casefold():x[k]['path_display']for x in read(H/'verified-six-cases.json')['rows']for k in ['file_metadata','folder_metadata']}
 if(H/'moonwave-native-overlay.json').exists():
  for x in read(H/'moonwave-native-overlay.json')['specific_file_maps']:result[x['old_path'].casefold()]=x['new_path'];result[x['new_path'].casefold()]=x['new_path']
 return result
def refresh(value):
 if not isinstance(value,str):return value
 paths=path_map()
 if value.startswith('ns:'):
  p=display(value);return namespace(paths[p.casefold()])if p.casefold()in paths else value
 if value.startswith('/BOLDSTONE MASTER/')and value.casefold()in paths:return paths[value.casefold()]
 if not value.startswith('https://www.dropbox.com/'):return value
 z=urlsplit(value);p=unquote(z.path);route=next((r for r in ['/home','/preview']if p.startswith(r+'/')),None)
 if not route:return value
 p=p[len(route):];name=parse_qs(z.query).get('preview',[''])[0];full=p+'/'+name if name else p
 if full.casefold()not in paths:return value
 current=paths[full.casefold()];target=current.rsplit('/',1)[0]if name else current
 return urlunsplit((z.scheme,z.netloc,route+quote(target,safe='/'),z.query,z.fragment))
