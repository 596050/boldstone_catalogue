"""Retain reviewed originals and expose their unchanged primary JPEG frames."""
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image
import json, hashlib

OUT = Path(__file__).parent
BASE = OUT.parent
DEST = BASE / 'qualified-originals'
NATIVE = BASE / 'native-upload-jpegs'
NATIVE.mkdir(exist_ok=True)
sha = lambda b: hashlib.sha256(b).hexdigest()

def extract(data):
    assert data[:2] == b'\xff\xd8'
    parts, pos, removed = [data[:2]], 2, []
    while True:
        start = pos
        assert data[pos] == 255
        pos += 1
        while data[pos] == 255:
            pos += 1
        marker = data[pos]
        pos += 1
        if marker == 0xd9:
            parts.append(data[start:pos])
            break
        assert marker not in (0, 0xd8) and not 0xd0 <= marker <= 0xd7
        length = int.from_bytes(data[pos:pos + 2], 'big')
        end = pos + length
        assert length >= 2
        payload = data[pos + 2:end]
        if marker == 0xe2 and payload.startswith(b'MPF\x00'):
            removed.append(dict(marker='APP2 MPF', start=start, end=end))
        else:
            parts.append(data[start:end])
        pos = end
        if marker == 0xda:
            scan_start = pos
            while True:
                at = data.find(b'\xff', pos)
                assert at >= 0
                q = at + 1
                while data[q] == 255:
                    q += 1
                m = data[q]
                if m == 0 or 0xd0 <= m <= 0xd7:
                    pos = q + 1
                    continue
                parts.append(data[scan_start:at])
                pos = at
                break
    assert len(removed) == 1 and data[pos - 2:pos] == b'\xff\xd9'
    return b''.join(parts), removed, pos

review = json.loads((OUT / 'crater-texture-matching.json').read_text())
assert review['original_files_unchanged'] is True
assert {r['role']: r['candidate_position'] for r in review['records']} == {'I': 4, 'II': 2, 'III': 1}
assert (OUT / 'crater-match-visual-review.jpg').exists()
records = json.loads((OUT / 'crater-matching-inputs.json').read_text())
proofs = {}
for record in records:
    source = Path(record['local_path'])
    data = source.read_bytes()
    assert sha(data) == record['sha256'] and record['location_metadata_present'] is False
    retained = DEST / source.name
    if retained.exists():
        assert retained.read_bytes() == data
    else:
        retained.write_bytes(data)
    body, removed, end = extract(data)
    target = NATIVE / (source.stem + '--primary-jpeg.jpg')
    if target.exists():
        assert target.read_bytes() == body
    else:
        target.write_bytes(body)
    with Image.open(retained) as original, Image.open(target) as native:
        original.seek(0)
        original.load()
        native.load()
        assert original.format == 'MPO' and native.format == 'JPEG'
        assert original.mode == native.mode == 'RGB'
        assert original.size == native.size and getattr(native, 'n_frames', 1) == 1
        assert original.getexif().get(274) == native.getexif().get(274)
        assert original.info.get('icc_profile') == native.info.get('icc_profile')
        pixel_sha = sha(original.tobytes())
        assert pixel_sha == sha(native.tobytes())
        assert not (set(original.getexif().get_ifd(34853)) - {0})
    assert source.read_bytes() == retained.read_bytes() == data
    proofs[record['role']] = dict(record, status='PASS_LOSSLESS_PRIMARY_JPEG_IDENTICAL_DECODED_PIXELS',
        local_path=str(retained), native_upload_path=str(target), native_upload_format='JPEG',
        native_upload_sha256=sha(body), native_upload_bytes=len(body), decoded_pixel_sha256=pixel_sha,
        removed_markers=removed, primary_end_offset=end, source_original_unchanged=True,
        pixel_edits=False, checked_utc=datetime.now(timezone.utc).isoformat())
    print(json.dumps({'role': record['role'], 'source_bytes': len(data), 'native_bytes': len(body),
                      'decoded_pixels_identical': True}), flush=True)
(OUT / 'crater-native-photo-verification.json').write_text(json.dumps(proofs, indent=2) + '\n')
