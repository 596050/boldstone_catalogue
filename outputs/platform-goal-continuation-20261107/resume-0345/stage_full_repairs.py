"""Stage full-source eBay repairs, reusing exact verified originals where possible."""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
PRIOR = OUT.parent / 'resume-0220'
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection

full = json.loads((OUT / 'full-gallery-reconciliation.json').read_text())
records = {r['sku']: r for r in full['records']}
old_manifest = json.loads((PRIOR / 'ebay-gallery-source-manifest.json').read_text())
old_queue = json.loads((PRIOR / 'ebay-remaining-metadata-queue.json').read_text())
packets = [{k:v for k,v in records[r['sku']].items() if k not in ['image_sources','historical_gallery_ids','changed_content_hashes']} for r in old_queue]
(OUT / 'ebay-full-metadata-queue.json').write_text(json.dumps(packets,indent=2)+'\n')
path = OUT / 'full-gallery-repair-manifest.json'
assert not path.exists(), 'Reconcile existing staged repair before rerunning'
manifest = dict(status='STAGING_COMPLETE_SELECTION_REPAIRS',source_app_revision=full['source_app_revision'],
                source_workbook_sha256=full['source_workbook_sha256'],records=[],original_edits=0,native_writes=0)
save = lambda: path.write_text(json.dumps(manifest,indent=2)+'\n')
save()
total = downloaded = reused = 0
with connection(ROOT) as (db, _):
    for old in reversed(old_manifest['records']):
        record = records[old['sku']]
        old_files = {f['photo_id']: f for f in old['files']}
        old_ids = [f['photo_id'] for f in old['files']]
        desired = record['desired_gallery_ids']
        append = old_ids == desired[:len(old_ids)]
        directory = OUT / 'full-gallery-staging' / record['native_draft_id']
        upload_directory = OUT / 'upload-batches' / record['native_draft_id']
        directory.mkdir(parents=True,exist_ok=True)
        upload_directory.mkdir(parents=True,exist_ok=True)
        files = []
        for index, image in enumerate(record['image_sources'],1):
            aid = image['id']
            meta = db.files_get_metadata(aid)
            expected_hash = image['original']['dropbox_content_hash']
            assert meta.id == aid and meta.content_hash == expected_hash
            suffix = Path(meta.name).suffix.lower()
            assert suffix in {'.jpg','.jpeg','.png'} and meta.size < 50_000_000
            assert total + meta.size < 300_000_000
            staged = directory / (f'{index:02d}'+suffix)
            assert not staged.exists()
            previous = old_files.get(aid)
            if previous:
                source = Path(previous['path'])
                body = source.read_bytes()
                assert hashlib.sha256(body).hexdigest()==previous['sha256']
                os.link(source,staged)
                reused += 1
            else:
                read_meta,response = db.files_download('rev:'+meta.rev)
                try: body = response.content
                finally: response.close()
                assert read_meta.id == aid
                staged.write_bytes(body)
                downloaded += 1
            content_hash = hashlib.sha256(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304))).hexdigest()
            assert len(body)==meta.size and content_hash==expected_hash
            with Image.open(staged) as photo:
                width,height=photo.size
                photo.verify()
            assert max(width,height)>=500
            total += meta.size
            item=dict(photo_id=aid,original_name=meta.name,revision=meta.rev,content_hash=content_hash,
                      sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),width=width,height=height,path=str(staged.resolve()))
            files.append(item)
            if not append or aid not in old_files:
                os.link(staged,upload_directory/staged.name)
        upload_files = [f for f in files if not append or f['photo_id'] not in old_files]
        manifest['records'].append(dict(sku=record['sku'],native_draft_id=record['native_draft_id'],title=record['title'],
                                       previous_native_photo_count=len(old_ids),desired_photo_count=len(files),
                                       mode='APPEND_MISSING_COMPLETE_SELECTIONS' if append else 'REPLACE_TO_RESTORE_LISTING_BEFORE_IN_SITU_ORDER',
                                       directory=str(directory.resolve()),upload_directory=str(upload_directory.resolve()),
                                       files=files,upload_files=upload_files,status='EXACT_ORIGINALS_READY_NATIVE_REPAIR_PENDING'))
        save()
        print(json.dumps(dict(sku=record['sku'],full_count=len(files),upload_count=len(upload_files),append=append)),flush=True)
manifest.update(status='READY_EXACT_FULL_GALLERY_REPAIRS',checked_utc=datetime.now(timezone.utc).isoformat(),
                bytes=total,downloaded_files=downloaded,reused_files=reused)
save()
print(json.dumps({k:v for k,v in manifest.items() if k!='records'},indent=2),flush=True)
