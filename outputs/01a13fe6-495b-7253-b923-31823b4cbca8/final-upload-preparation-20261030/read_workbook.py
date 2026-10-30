from pathlib import Path
import json,sys,hashlib
OUT=Path(__file__).resolve().parent
sys.path.insert(0,'/Users/tprice/Documents/boldstone/catalogue-review')
from delete_dropbox import connection
with connection(Path('/Users/tprice/Documents/boldstone')) as (client,root):
    metadata,response=client.files_download('id:cnqzTNngPVsAAAAAAA7JEQ')
    try: body=response.content
    finally: response.close()
    assert metadata.path_display=='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
    assert len(body)==metadata.size
    (OUT/'previous-catalogue.xlsx').write_bytes(body)
    (OUT/'previous-dropbox-metadata.json').write_text(json.dumps({'id':metadata.id,'rev':metadata.rev,
        'path':metadata.path_display,'size':metadata.size,'content_hash':metadata.content_hash,
        'sha256':hashlib.sha256(body).hexdigest()},indent=2))
    print(json.dumps({'bytes':len(body),'rev':metadata.rev}))
