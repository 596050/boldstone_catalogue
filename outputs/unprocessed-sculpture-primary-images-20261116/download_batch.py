import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def dropbox_hash(path):
    blocks = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            blocks.update(hashlib.sha256(block).digest())
    return blocks.hexdigest()


def download(item):
    target = Path(item['destination'])
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name('.' + target.name + '.' + uuid.uuid4().hex + '.part')
    result = {key: value for key, value in item.items() if key != 'download_url'}
    try:
        if target.exists():
            if target.stat().st_size == item['size'] and dropbox_hash(target) == item['content_hash']:
                result.update(status='verified_existing', bytes=target.stat().st_size, checked_at=now())
                return result
            raise FileExistsError('Destination already exists with different contents')
        request = urllib.request.Request(item['download_url'], headers={'User-Agent': 'Boldstone-primary-image-download/1.0'})
        with urllib.request.urlopen(request, timeout=90) as response, temp.open('xb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temp.stat().st_size != item['size']:
            raise ValueError('Downloaded size differs from Dropbox metadata')
        actual_hash = dropbox_hash(temp)
        if actual_hash != item['content_hash']:
            raise ValueError('Downloaded content hash differs from Dropbox metadata')
        inspected = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', '-g', 'format', str(temp)], capture_output=True, text=True, check=True).stdout
        width = re.search(r'pixelWidth: (\d+)', inspected)
        height = re.search(r'pixelHeight: (\d+)', inspected)
        format_match = re.search(r'format: (\w+)', inspected)
        if not width or not height or not format_match:
            raise ValueError('Downloaded image could not be decoded')
        dimensions = [int(width[1]), int(height[1])]
        image_format = format_match[1]
        os.replace(temp, target)
        result.update(status='downloaded_verified', bytes=target.stat().st_size,
                      content_hash_verified=actual_hash, dimensions=dimensions,
                      image_format=image_format, sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                      checked_at=now())
    except Exception as error:
        if temp.exists():
            temp.unlink()
        result.update(status='failed', error_type=type(error).__name__, checked_at=now())
    return result


batch = json.load(sys.stdin)
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    for result in pool.map(download, batch):
        with (BASE / 'download-receipts.jsonl').open('a') as stream:
            stream.write(json.dumps(result) + '\n')
        print(json.dumps({key: result.get(key) for key in ['component_name', 'status', 'bytes', 'error_type']}), flush=True)
