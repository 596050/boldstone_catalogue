"""Recheck the actual upload files against Saatchi's observed width/height rule."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from PIL import Image

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
PACKETS = OUT.parent / 'resume-0512/packets'
spec = importlib.util.spec_from_file_location('saatchi', ROOT / 'catalogue-review/scripts/prepare_saatchi_catalogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
registry = ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json'
bindings = module.native_artwork_bindings(registry)
records, ready = [], []
for path in sorted(PACKETS.glob('BSI-*.json')):
    packet = json.loads(path.read_text())
    photo = packet['photo']
    native = Path(photo['native_upload_path'])
    digest = hashlib.sha256(native.read_bytes()).hexdigest()
    assert digest == photo['native_upload_sha256'], packet['sku']
    with Image.open(native) as image:
        image.load()
        width, height = image.size
        assert [width, height] == [photo['width'], photo['height']]
        assert image.format in ('JPEG', 'PNG') and image.mode == 'RGB'
        dimensions_pass = width >= 1500 and height >= 1200
        item = dict(sku=packet['sku'], catalogue_id=packet['catalogue_id'],
                    title=packet['title'], packet_path=str(path),
                    native_upload_path=str(native), sha256=digest,
                    width=width, height=height, format=image.format,
                    mode=image.mode, native_dimensions_pass=dimensions_pass,
                    native_artwork_id=bindings.get(packet['sku']),
                    status=('EXISTING_NATIVE_ARTWORK_COMPLETE_THAT_ID_ONLY' if packet['sku'] in bindings
                            else 'PREPARED_NOT_UPLOADED' if dimensions_pass
                            else 'HOLD_WIDTH_OR_HEIGHT_BELOW_NATIVE_MINIMUM'))
        records.append(item)
        if dimensions_pass and packet['sku'] not in bindings:
            assert not packet.get('native_artwork_id')
            ready.append(dict(packet=packet, validation=item))
assert len(records) == 16 and len(ready) == 13
assert len({r['sku'] for r in records}) == 16
assert [r['sku'] for r in records if not r['native_dimensions_pass']] == ['BOLD-21E953F1D523']
assert len(bindings) == len(set(bindings.values())) == 126
result = dict(checked_utc=datetime.now(timezone.utc).isoformat(),
              rule='At least 1500 pixels wide and 1200 pixels high in intended viewing orientation',
              inspected_packets=16, existing_bound_artworks=2,
              ready_uncreated_packets=13, rejected_dimension_packets=1,
              native_artwork_bindings=126, native_mutations_this_check=0,
              source_images_edited=False, records=records)
(OUT / 'saatchi-primary-file-verification.json').write_text(json.dumps(result, indent=2) + '\n')
(OUT / 'remaining-native-ready-queue.json').write_text(json.dumps(ready, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k != 'records'}, indent=2))
