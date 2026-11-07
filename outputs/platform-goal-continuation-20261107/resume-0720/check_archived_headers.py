"""Read only image headers for content-distinct archival search matches."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from PIL import ImageFile

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection

additional = '--remaining-families' in sys.argv
folder_contents = '--folder-contents' in sys.argv
search_path = OUT / ('remaining-family-search.json' if additional else 'archived-photo-search.json')
target = OUT / ('remaining-family-headers.json' if additional else 'archived-photo-headers.json')
if folder_contents:
    target = OUT / 'folder-content-headers.json'
known = set()
if additional:
    library = json.loads((OUT.parent.parent / 'platform-goal-continuation-20261106/resume-2250/library.json').read_text())
    known.update(i['original']['dropbox_content_hash'] for i in library['images']
        if i.get('original',{}).get('dimensions') and i.get('original',{}).get('dropbox_content_hash'))
    for name, key in [('archival-original-headers.json','content_hash'),
                      ('saatchi-new-original-headers.json','expected_content_hash')]:
        prior = json.loads((OUT.parent.parent / 'platform-goal-continuation-20261106' / name).read_text())
        known.update(r[key] for r in prior if r.get(key) and r.get('width') and r.get('height'))
    known.update(r['content_hash'] for r in json.loads((OUT / 'archived-photo-headers.json').read_text())
        if r.get('width') and r.get('height'))
unique = {}
searches = ([dict(query='folder-content',matches=json.loads((OUT/'folder-content-header-targets.json').read_text()))]
    if folder_contents else json.loads(search_path.read_text()))
for search in searches:
    for row in search['matches']:
        if row['type'] != 'file':
            continue
        key = row['content_hash']
        if key in known:
            continue
        if key not in unique:
            unique[key] = dict(row, queries=[search['query']])
        elif search['query'] not in unique[key]['queries']:
            unique[key]['queries'].append(search['query'])
assert len(unique) <= 300
results = []
with connection(ROOT) as (db, _):
    def check(row):
        record = dict(row, checked_utc=datetime.now(timezone.utc).isoformat())
        response = None
        try:
            meta, response = db.files_download('rev:' + row['revision'])
            assert meta.id == row['id'] and meta.content_hash == row['content_hash'] and meta.size == row['bytes']
            parser, count = ImageFile.Parser(), 0
            for chunk in response.iter_content(chunk_size=16384):
                if not chunk:
                    continue
                count += len(chunk)
                parser.feed(chunk)
                if parser.image or count >= 1048576:
                    break
            assert parser.image is not None, 'Image header not found within 1 MiB'
            width, height = parser.image.size
            record.update(status='NATIVE_REVISION_HEADER_VERIFIED', width=width, height=height,
                format=parser.image.format, mode=parser.image.mode, bytes_read=count,
                saatchi_native_dimensions_pass=width>=1500 and height>=1200,
                chairish_dimensions_pass=width>=575 or height>=575)
        except Exception as error:
            record.update(status='READ_UNVERIFIED', error_type=type(error).__name__)
        finally:
            if response is not None:
                response.close()
        return record
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(check, row) for row in unique.values()]
        for future in as_completed(pending):
            results.append(future.result())
            target.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
            if len(results) % 15 == 0 or len(results) == len(unique):
                print(json.dumps(dict(checked=len(results), total=len(unique),
                    saatchi_size_pass=sum(r.get('saatchi_native_dimensions_pass', False) for r in results),
                    full_originals_retained=0)), flush=True)
