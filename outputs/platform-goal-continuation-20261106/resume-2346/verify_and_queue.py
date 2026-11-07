"""Independently verify retained inputs and reconcile the remaining Saatchi scope."""
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image
import hashlib, json, sys, subprocess

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
PARENT = OUT.parent
PREVIOUS = PARENT / 'resume-2250'
sys.path[:0] = [str(ROOT / 'catalogue-review/scripts')]
from prepare_saatchi_catalogue import native_artwork_bindings

read = lambda p: json.loads(p.read_text())
sha = lambda b: hashlib.sha256(b).hexdigest()
scope = set(read(ROOT / 'outputs/platform-live-completion-20261104/scope.json')['publication_skus'])
bindings = native_artwork_bindings(ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
app = read(OUT / 'specifications-current.json')
products = {next(f['value'] for f in p['fields'] + p['listing_fields'] if f['key'] == 'Seller SKU'): p for p in app['products']}
pointer = read(ROOT / 'sculpture-catalogue/current-master.json')['current_app_review_workbook']
book = Path(pointer['path'])
assert sha(book.read_bytes()) == pointer['sha256']
reader_code = '''
import sys,json,hashlib
sys.path.insert(0,'/tmp/boldstone-20261106-readback')
from python_calamine import CalamineWorkbook
from pathlib import Path
p=Path(sys.argv[1]);s=CalamineWorkbook.from_path(str(p)).get_sheet_by_name('Wall Sculptures');r=s.to_python();n=6-s.start[0];h=r[n]
keys=['SKU','saatchi_asking_price_usd','saatchi_art_edition_size','saatchi_art_creation_year']
print(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':{str(v[h.index('SKU')]):{k:v[h.index(k)] for k in keys} for v in r[n+1:]}}))
'''
independent = json.loads(subprocess.check_output(['python3', '-c', reader_code, str(book)], text=True))
assert independent['sha256'] == pointer['sha256']
by_sku = independent['rows']
assert len(scope) == 176 and len(by_sku) == 181 and len(bindings) == 119

paths = [PARENT / name for name in ['ammonite-upload-packet.json', 'moon-fish-upload-packet.json',
                                   'lunar-phase-iv-upload-packet.json', 'context-upload-packets.json']]
new_paths = [PREVIOUS / name for name in ['additional-reviewed-upload-packets.json', 'gleneagles-reviewed-upload-packets.json',
                                    'fountain-reviewed-upload-packet.json', 'spiralfish-reviewed-upload-packets.json']]
new_paths.append(OUT / 'bordered-reviewed-upload-packets.json')
queue = []
proofs = []
photo_paths = {}
for path in paths + new_paths:
    for packet in read(path):
        sku = packet['sku']
        if sku in bindings:
            continue
        assert sku in scope and packet['catalogue_id'] == products[sku]['id']
        assert packet['title'] == products[sku]['retail_name']
        row = by_sku[sku]
        for target, column in [('target_artwork_price_usd', 'saatchi_asking_price_usd'),
                               ('edition_cap', 'saatchi_art_edition_size'), ('creation_year', 'saatchi_art_creation_year')]:
            assert packet[target] == row[column], (sku, target)
        assert packet['edition_cap'] == 50 and packet['edition_scope'] == 'Saatchi Art only'
        assert packet['quantity_per_sale'] == 1 and packet['native_packaging'] == 'Crate'
        assert packet['native_packed_weight_kg_estimate'] > 0 and packet['packing_allowance_gbp'] > 0
        assert packet['packing_model_source_sha256']
        text = packet['description']
        assert len(text) <= 1000 and packet['description_characters'] == len(text)
        for required in ['gypsum-based', 'Sally Price', '3 working days']:
            assert required in text, (sku, required)
        source = Path(packet['photo']['local_path'])
        native = Path(packet['photo']['native_upload_path'])
        source_body = source.read_bytes()
        native_body = native.read_bytes()
        assert sha(source_body) == packet['photo']['sha256']
        assert sha(native_body) == packet['photo']['native_upload_sha256']
        content_hash = sha(b''.join(hashlib.sha256(source_body[n:n + 4194304]).digest() for n in range(0, len(source_body), 4194304)))
        assert content_hash == packet['photo']['content_hash']
        with Image.open(native) as im:
            assert im.format in ('JPEG', 'PNG') and im.mode == 'RGB'
            assert im.size == (packet['photo']['width'], packet['photo']['height'])
            assert min(im.size) >= 1200 and max(im.size) >= 1500
            if im.format == 'PNG':
                assert native_body == source_body, 'No image conversion or editing is authorized by the preparation'
                evidence = Path(packet['native_image_requirements_evidence'])
                assert evidence.parent == OUT
                assert 'JPEG or PNG format' in evidence.read_text()
                assert 'At least 1500W x 1200H pixels' in evidence.read_text()
                assert im.width >= 1500 and im.height >= 1200
            exif = im.getexif()
            gps = exif.get_ifd(34853) if exif.get(34853) else {}
            assert not (set(gps) - {0}), 'Location metadata requires review before upload; a version-only GPS block is harmless'
        if sku in ['BOLD-B19E0B8602C1', 'BOLD-A272AC152172']:
            expected_side = 'left-hand' if sku == 'BOLD-B19E0B8602C1' else 'right-hand'
            assert text.startswith('Only the ' + expected_side + ' panel of the rightmost pair')
            assert 'leftmost pair' not in text
        queue.append({'source_packet': str(path), 'packet': packet,
                      'native_action': 'Fresh portfolio reconciliation, resolve verification failure, then create once only if still unbound'})
        proofs.append({'sku': sku, 'catalogue_id': packet['catalogue_id'], 'title': packet['title'],
                       'price_usd': packet['target_artwork_price_usd'], 'packed_kg_estimate': packet['native_packed_weight_kg_estimate'],
                       'source_photo_sha256': sha(source_body), 'native_photo_sha256': sha(native_body),
                       'prepared_only': True})
        photo_paths[str(source)] = len(source_body)
        for additional in packet.get('additional_photos', []):
            additional_path = Path(additional['native_upload_path'])
            body = additional_path.read_bytes()
            assert sha(body) == additional['sha256'] == additional['native_upload_sha256']
            assert len(body) == additional['bytes']
            expected_hash = sha(b''.join(hashlib.sha256(body[n:n + 4194304]).digest() for n in range(0, len(body), 4194304)))
            assert expected_hash == additional['content_hash']
            assert additional['role'] == 'ADDITIONAL_DETAIL_ONLY_NOT_PRIMARY'
            assert additional['visually_reviewed_full_original'] is True
            assert additional['original_unaltered'] is True
            assert additional['caption'].endswith('Each panel is sold separately.')
            with Image.open(additional_path) as detail:
                assert detail.format == 'JPEG' and detail.mode == 'RGB'
                assert detail.size == (additional['width'], additional['height'])
                assert min(detail.size) >= 1200 and max(detail.size) >= 1500
                gps = detail.getexif().get_ifd(34853)
                assert not (set(gps) - {0}), 'Additional photo contains unreviewed location data'
            photo_paths[str(additional_path)] = len(body)

assert len(queue) == 16 and len({x['packet']['sku'] for x in queue}) == 16
new_packets = [p for path in new_paths for p in read(path)]
assert len(new_packets) == 12 and len({p['sku'] for p in new_packets}) == 12
new_border_packets = read(OUT / 'bordered-reviewed-upload-packets.json')
assert {p['catalogue_id'] for p in new_border_packets} == {'BSI-65A93033A200', 'BSI-4515726BBC18'}
for packet in new_border_packets:
    side = 'left-hand' if packet['catalogue_id'] == 'BSI-65A93033A200' else 'right-hand'
    assert packet['description'].startswith(f'Only the {side} framed panel')
    assert packet['photo']['format'] == 'PNG'
queued = {x['packet']['sku'] for x in queue}
gaps = [{'catalogue_id': products[sku]['id'], 'sku': sku, 'title': products[sku]['retail_name'],
         'status': 'PHOTOGRAPHY_OR_VISUAL_REVIEW_STILL_REQUIRED',
         'native_creation_authorized_by_this_record': False}
        for sku in sorted(scope - set(bindings) - queued)]
assert len(gaps) == 41
result = {'status': 'PASS_16_PREPARED_UPLOADS_CURRENT_SCOPE_AND_INPUTS_ONLY',
          'checked_utc': datetime.now(timezone.utc).isoformat(),
          'current_workbook_sha256': pointer['sha256'], 'current_app_revision': app['revision'],
          'publication_scope': 176, 'existing_native_bindings': 119,
          'published_last_full_audit': 117, 'existing_incomplete_drafts': 2,
          'unbound_ready_for_native_tests': 16, 'newly_prepared_this_turn': 2,
          'previous_prepared_queue': 14,
          'remaining_photography_or_review': 41, 'queue_original_bytes': sum(photo_paths.values()),
          'products_with_additional_detail_photo': sum(bool(q['packet'].get('additional_photos')) for q in queue),
          'native_creations_this_turn': 0, 'native_publications_this_turn': 0,
          'app_photo_changes': 0, 'master_workbook_changed': False,
          'authoritative_native_reconciliation_still_required_before_any_creation': True,
          'native_file_requirements_source': 'https://support.saatchiart.com/hc/en-us/articles/17737130295963-How-to-photograph-an-artwork',
          'current_native_file_requirements_evidence': str(OUT / 'saatchi-primary-image-requirements.txt'),
          'records': proofs}
(OUT / 'remaining-saatchi-upload-queue.json').write_text(json.dumps(queue, indent=2) + '\n')
(OUT / 'remaining-saatchi-photo-gaps.json').write_text(json.dumps(gaps, indent=2) + '\n')
(OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'records'}))
