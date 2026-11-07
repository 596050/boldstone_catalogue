"""Read image metadata inside named sculpture archives, including generic camera names."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import FileMetadata

folders = json.loads((OUT/'archival-family-folder-targets.json').read_text())
excluded = ['greetings card','marbled moon print','marbling and painting prints','proposals/tiles','variant generation']
folders = [f for f in folders if not any(term in f['path'].casefold() for term in excluded)]
assert 0 < len(folders) <= 100
suffixes = {'.jpg','.jpeg','.png','.tif','.tiff','.webp','.heic','.mpo'}
results = []
with connection(ROOT) as (db,_):
    def scan(folder):
        rows, pages = [], 0
        try:
            response = db.files_list_folder(folder['id'],recursive=True,include_media_info=True,limit=2000)
            while True:
                pages += 1
                for m in response.entries:
                    if not isinstance(m,FileMetadata) or Path(m.name).suffix.lower() not in suffixes:
                        continue
                    row = dict(id=m.id,name=m.name,path=m.path_display,type='file',bytes=m.size,
                        content_hash=m.content_hash,revision=m.rev,modified_utc=m.server_modified.isoformat())
                    if m.media_info and m.media_info.is_metadata():
                        media=m.media_info.get_metadata()
                        if media.dimensions:
                            row['dropbox_media_dimensions']=[media.dimensions.width,media.dimensions.height]
                    rows.append(row)
                if not response.has_more:
                    break
                response = db.files_list_folder_continue(response.cursor)
            return dict(folder=folder,status='COMPLETE_NATIVE_FOLDER_LIST',pages=pages,
                matches=rows,checked_utc=datetime.now(timezone.utc).isoformat())
        except Exception as error:
            return dict(folder=folder,status='FOLDER_LIST_UNVERIFIED',pages=pages,
                matches=rows,error_type=type(error).__name__,checked_utc=datetime.now(timezone.utc).isoformat())
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=[pool.submit(scan,f) for f in folders]
        for future in as_completed(pending):
            results.append(future.result())
            (OUT/'archival-family-folder-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
            if len(results)%10==0 or len(results)==len(folders):
                files=[r for result in results for r in result['matches']]
                print(json.dumps(dict(folders_checked=len(results),of=len(folders),image_entries=len(files),
                    unique_image_hashes=len({r['content_hash'] for r in files}),
                    unverified=sum(r['status']!='COMPLETE_NATIVE_FOLDER_LIST' for r in results))),flush=True)
