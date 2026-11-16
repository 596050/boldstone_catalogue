import argparse
import hashlib
import json
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
manifest_path = BASE / 'manifest.json'
manifest = json.loads(manifest_path.read_text())
parser = argparse.ArgumentParser()
parser.add_argument('--final', action='store_true')
args = parser.parse_args()


def verify_png(path, expected):
    data = path.read_bytes()
    assert data.startswith(b'\x89PNG\r\n\x1a\n'), str(path)
    assert struct.unpack('>II', data[16:24]) == (expected['width'], expected['height']), str(path)
    offset = 8
    chunks = []
    while offset < len(data):
        size = struct.unpack('>I', data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + size
        assert end <= len(data), str(path)
        crc = struct.unpack('>I', data[offset + 8 + size:end])[0]
        assert zlib.crc32(data[offset + 4:offset + 8 + size]) & 0xffffffff == crc, str(path)
        chunks.append(kind.decode('ascii'))
        offset = end
        if kind == b'IEND':
            break
    assert offset == len(data) and chunks[-1] == 'IEND', str(path)
    digest = hashlib.sha256(data).hexdigest()
    assert digest != expected['sha256'], 'Output is identical to input: ' + str(path)
    return {'path': str(path), 'size': len(data), 'sha256': digest, 'png_chunks': chunks}


newly_verified = []
for group in manifest['groups']:
    output = Path(group.get('output_folder') or Path(manifest['processed_root']) / group['label'])
    expected = {f['sha256'] + '.png': f for f in group['files']}
    actual = {p.name for p in output.glob('*.png')} if output.exists() else set()
    if actual != set(expected):
        if group['status'] == 'processed_verified':
            group['status'] = 'output_missing_or_changed'
        continue
    if not group.get('verified_outputs'):
        group['verified_outputs'] = [verify_png(output / name, source) for name, source in sorted(expected.items())]
        group['verified_at'] = datetime.now(timezone.utc).isoformat()
        newly_verified.append(group['label'])
    group['status'] = 'processed_verified'
    group['output_folder'] = str(output)

for batch in manifest['batches']:
    if all(next(g for g in manifest['groups'] if g['label'] == name)['status'] == 'processed_verified' for name in batch['groups']):
        batch['status'] = 'processed_verified'

verified = [g for g in manifest['groups'] if g['status'] == 'processed_verified']
summary = {
    'verified_groups': len(verified),
    'total_groups': len(manifest['groups']),
    'verified_images': sum(len(g['verified_outputs']) for g in verified),
    'total_images': sum(len(g['files']) for g in manifest['groups']),
    'newly_verified': newly_verified,
    'processed_root': manifest['processed_root'],
}
if args.final:
    assert len(verified) == len(manifest['groups']), 'Processing is incomplete'
    for group in manifest['groups']:
        for source in group['files']:
            with Path(source['source']).open('rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == source['sha256'], source['filename']
    summary['original_images_unchanged'] = True
    summary['completed_at'] = datetime.now(timezone.utc).isoformat()
    (BASE / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n')

manifest['progress'] = summary
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(summary, indent=2))
