"""Read the current catalogue workbook by stable Dropbox ID."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection

pointer = json.loads((OUT / 'source-pointer-before.json').read_text())['current_app_review_workbook']
with connection(ROOT) as (client, root):
    m = client.files_get_metadata(pointer['dropbox']['id'])
    assert m.path_display == '/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
    meta, response = client.files_download('rev:' + m.rev)
    try:
        body = response.content
    finally:
        response.close()
    assert meta.id == m.id and meta.rev == m.rev
    assert hashlib.sha256(body).hexdigest() == pointer['sha256'], 'The Dropbox workbook changed; compare it before editing.'
    (OUT / 'previous-catalogue.xlsx').write_bytes(body)
    receipt = {k: str(getattr(m, k)) if k in ('server_modified', 'client_modified') else getattr(m, k)
               for k in ('id', 'path_display', 'rev', 'size', 'content_hash', 'server_modified', 'client_modified')}
    (OUT / 'previous-dropbox-metadata.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps({'status': 'VERIFIED_CURRENT_TEMPLATE', 'bytes': len(body), 'revision': m.rev}))
