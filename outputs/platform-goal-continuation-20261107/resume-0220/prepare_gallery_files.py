"""Read exact current Dropbox originals for stale eBay draft galleries."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection

queue = json.loads((OUT / 'ebay-remaining-metadata-queue.json').read_text())
packets = {r['sku']: r for r in queue}
receipts = json.loads((OUT / 'ebay-metadata-receipts.json').read_text())
targets = [r for r in receipts if r.get('gallery_count_matches') is False][:4]
library = json.loads((ROOT / 'outputs/platform-goal-continuation-20261106/resume-2250/library.json').read_text())
images = {i['id']: i for i in library['images']}
manifest_path = OUT / 'ebay-gallery-source-manifest.json'
assert not manifest_path.exists(), 'Reconcile the existing source manifest before rerunning'
manifest = dict(status='PREPARING_EXACT_ORIGINALS', checked_utc=datetime.now(timezone.utc).isoformat(),
                platform_writes=0, original_edits=0, records=[])
save = lambda: manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
save()
total = 0
with connection(ROOT) as (db, _):
    for target in targets:
        packet = packets[target['sku']]
        directory = OUT / 'gallery-staging' / packet['native_draft_id']
        directory.mkdir(parents=True, exist_ok=True)
        files = []
        for index, aid in enumerate(packet['desired_gallery_ids'], 1):
            image = images[aid]
            meta = db.files_get_metadata(aid)
            expected_hash = image['original']['dropbox_content_hash']
            assert meta.id == aid and meta.content_hash == expected_hash, ('Original changed', aid)
            suffix = Path(meta.name).suffix.lower()
            assert suffix in {'.jpg', '.jpeg', '.png'}, ('Needs native file-format review', meta.name)
            assert meta.size < 50_000_000 and total + meta.size < 300_000_000
            path = directory / (f'{index:02d}' + suffix)
            assert not path.exists(), ('Reconcile the existing staged original', path)
            read_meta, response = db.files_download('rev:' + meta.rev)
            try:
                body = response.content
            finally:
                response.close()
            digest = hashlib.sha256(b''.join(hashlib.sha256(body[i:i+4194304]).digest()
                                            for i in range(0, len(body), 4194304))).hexdigest()
            assert read_meta.id == aid and len(body) == meta.size and digest == expected_hash
            path.write_bytes(body)
            with Image.open(path) as photo:
                width, height = photo.size
                photo.verify()
            assert max(width, height) >= 500, ('Below eBay minimum long edge', aid, width, height)
            total += len(body)
            files.append(dict(photo_id=aid, original_name=meta.name, revision=meta.rev,
                              content_hash=digest, sha256=hashlib.sha256(body).hexdigest(),
                              bytes=len(body), width=width, height=height, path=str(path.resolve())))
        manifest['records'].append(dict(sku=packet['sku'], native_draft_id=packet['native_draft_id'],
                                        title=packet['title'], previous_native_photo_count=target['photos'],
                                        desired_photo_count=len(files), directory=str(directory.resolve()),
                                        files=files, status='EXACT_ORIGINALS_READY_NATIVE_REPLACEMENT_NOT_STARTED'))
        save()
        print(json.dumps(dict(sku=packet['sku'], exact_originals=len(files), cumulative_bytes=total)), flush=True)
manifest.update(status='EXACT_ORIGINALS_READY_NO_PLATFORM_CHANGES', bytes=total)
save()
print(json.dumps(dict(status=manifest['status'], products=len(targets), bytes=total)), flush=True)
