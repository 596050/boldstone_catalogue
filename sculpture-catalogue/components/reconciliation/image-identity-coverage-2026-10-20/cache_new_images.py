"""Consume authorized temporary read links once and bind new image bytes to IDs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import urllib.request

HERE = Path(__file__).resolve().parent
cache = HERE / 'cache'
cache.mkdir(exist_ok=True)
records = json.loads((HERE / 'download-links.private.json').read_text())['entries']


def fetch(record):
    key = record['id'].split(':', 1)[1]
    target = cache / (key + '.original')
    metadata_path = cache / (key + '.metadata.json')
    assert not target.exists(), 'Read link must not be consumed twice'
    with urllib.request.urlopen(record['download_url'], timeout=60) as response:
        content = response.read()
    assert len(content) == record['size']
    block_hashes = b''.join(hashlib.sha256(content[i:i+4*1024*1024]).digest() for i in range(0, len(content), 4*1024*1024))
    content_hash = hashlib.sha256(block_hashes).hexdigest()
    assert content_hash == record['content_hash']
    target.write_bytes(content)
    public = {k: v for k, v in record.items() if k not in ['download_url', 'expiration_in_sec']}
    public.update(local_path=str(target), sha256=hashlib.sha256(content).hexdigest(), dropbox_content_hash_verified=True)
    metadata_path.write_text(json.dumps(public, ensure_ascii=False, indent=2)+'\n')
    return {'id': record['id'], 'bytes': len(content), 'status': 'CURRENT_BYTES_HASH_VERIFIED'}


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(fetch, records))
(HERE / 'new-image-cache-receipt.json').write_text(json.dumps({'status': 'PASS', 'results': results}, indent=2)+'\n')
(HERE / 'download-links.private.json').unlink()
print(json.dumps({'status': 'PASS', 'files': len(results), 'bytes': sum(x['bytes'] for x in results)}))
