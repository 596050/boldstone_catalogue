"""Read and retain the current Dropbox master without modifying it."""
from pathlib import Path
import sys, json, hashlib, sqlite3
from datetime import datetime, timezone

ROOT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection

pointer=json.loads((OUT/'source-pointer-before.json').read_text())['current_app_review_workbook']
with connection(ROOT) as (client,_):
    m=client.files_get_metadata(pointer['dropbox']['id'])
    assert m.rev==pointer['dropbox']['rev'] and m.path_display==pointer['dropbox']['path_display']
    dm,response=client.files_download('rev:'+m.rev)
    try: body=response.content
    finally: response.close()
    assert dm.id==m.id and hashlib.sha256(body).hexdigest()==pointer['sha256']
    (OUT/'previous-catalogue.xlsx').write_bytes(body)
    meta={k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in
          ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
    (OUT/'previous-dropbox-metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
dbpath=Path.home()/'Library/Application Support/BoldstoneReview/reviews.sqlite3'
db=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True)
snapshot={'database':str(dbpath),'last_event':db.execute('SELECT MAX(id), MAX(at) FROM events').fetchone(),
          'checked_utc':datetime.now(timezone.utc).isoformat()}
db.close()
(OUT/'app-source-guard.json').write_text(json.dumps(snapshot,indent=2)+'\n')
print(json.dumps({'status':'SOURCE_BYTES_VERIFIED','rev':m.rev,'size':len(body),'last_app_event':snapshot['last_event']}))
