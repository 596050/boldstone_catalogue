"""Search six precise archival photo terms without changing Dropbox content."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import FileMetadata, FolderMetadata, SearchOptions

additional = '--remaining-families' in sys.argv
queries = (['riyadh', 'lava', 'crater', 'spiralfish', 'raked', 'quarter', 'chelsea', 'moonring', 'strata']
    if additional else ['circle', 'marbled', 'brass', 'magnolia', 'cup', 'egyptian'])
target = OUT / ('remaining-family-search.json' if additional else 'archived-photo-search.json')
results = []
with connection(ROOT) as (db, _):
    for query in queries:
        response = db.files_search_v2(query, options=SearchOptions(
            path='/BOLDSTONE MASTER/Documents', filename_only=True, max_results=1000))
        matches, pages = [], 0
        while True:
            pages += 1
            for item in response.matches:
                if not item.metadata.is_metadata():
                    continue
                meta = item.metadata.get_metadata()
                if isinstance(meta, FolderMetadata):
                    matches.append(dict(id=meta.id, name=meta.name, path=meta.path_display, type='folder'))
                elif isinstance(meta, FileMetadata) and Path(meta.name).suffix.lower() in {
                        '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.heic', '.webp', '.mpo'}:
                    matches.append(dict(id=meta.id, name=meta.name, path=meta.path_display,
                        type='file', bytes=meta.size, content_hash=meta.content_hash, revision=meta.rev,
                        modified_utc=meta.server_modified.isoformat()))
            if not response.has_more:
                break
            response = db.files_search_continue_v2(response.cursor)
        results.append(dict(query=query, pages=pages, has_more=False, matches=matches,
            checked_utc=datetime.now(timezone.utc).isoformat()))
        target.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(dict(query=query, file_matches=sum(x['type']=='file' for x in matches),
            folder_matches=sum(x['type']=='folder' for x in matches))), flush=True)
