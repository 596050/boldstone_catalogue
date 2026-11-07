"""Prepare visually matched Dropbox originals; no catalogue or platform writes."""
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image
import hashlib, json, re, sys

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
PARENT = OUT.parent
sys.path[:0] = [str(ROOT / 'catalogue-review'), str(ROOT / 'catalogue-review/scripts')]
from delete_dropbox import connection
from import_saatchi_snapshot import Xlsx
from prepare_saatchi_catalogue import native_artwork_bindings
from channel_content import saatchi_description, complete_description, values, appearance, has_surface_effect, product_type

read = lambda p: json.loads(p.read_text())
sha = lambda b: hashlib.sha256(b).hexdigest()
app_snapshot = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else OUT / 'specifications.json'
app = read(app_snapshot)
products = {p['id']: p for p in app['products']}
images = {i['id']: i for i in read(OUT / 'library.json')['images']}
headers = {r['image']['id']: r['header'] for r in read(PARENT / 'saatchi-qualifying-photo-review.json')}
bindings = native_artwork_bindings(ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
pointer = read(ROOT / 'sculpture-catalogue/current-master.json')['current_app_review_workbook']
book = Path(pointer['path'])
assert sha(book.read_bytes()) == pointer['sha256']
x = Xlsx(book)
sheet = 'Wall Sculptures'
columns = {x.value(sheet, a): re.sub(r'\d', '', a) for a in x.cells[sheet] if re.fullmatch('[A-Z]+7', a)}
rows = {x.value(sheet, f'AA{r}'): r for r in range(8, 189)}
model = {r['catalogue_id']: r for r in read(PARENT / 'packing/plan.json')['records']}
packing_receipt = read(PARENT / 'packing/dropbox-receipt.json')
assert packing_receipt['status'] == 'PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
cases = [
    ('BSI-7B6291B7C7F9', 'id:cnqzTNngPVsAAAAAAAueFw', 'remaining-photo-comparison.jpg'),
    ('BSI-1CDB2BAE6105', 'id:cnqzTNngPVsAAAAAAAuZ2w', 'remaining-photo-comparison.jpg'),
    ('BSI-21E953F1D523', 'id:cnqzTNngPVsAAAAAAAygZA', 'strata-blue-wash-primary-preview.jpg'),
]
mode = sys.argv[1] if len(sys.argv) > 1 else 'singles'
assert mode in ('singles', 'gleneagles', 'fountain', 'spiralfish', 'bordered', 'moon_shell', 'crater_white')
output_name = 'additional-reviewed-upload-packets.json'
output_directory = OUT
disclosures = {}
reviewed_manual_sources = {}
crater_native_photos = {}
if mode == 'gleneagles':
    output_name = 'gleneagles-reviewed-upload-packets.json'
    positions = [
        ('BSI-53239DE28BCA', 'upper-left'),
        ('BSI-49CB2EDD232C', 'upper-right'),
        ('BSI-48D13D8D7E67', 'lower-left'),
        ('BSI-8957C5C51828', 'lower-right'),
    ]
    cases = [(pid, 'id:cnqzTNngPVsAAAAAAArtyw', 'gleneagles-photo-review.jpg') for pid, _ in positions]
    disclosures = {pid: f'Only the {position} panel in this photograph is supplied. The other three panels are sold separately. The photograph has warm workshop lighting; the offered finish is White.' for pid, position in positions}
elif mode == 'fountain':
    output_name = 'fountain-reviewed-upload-packet.json'
    cases = [('BSI-22E4E4F99696', 'id:cnqzTNngPVsAAAAAAArtmg', 'remaining-camera-and-fountain-review.jpg')]
    disclosures = {'BSI-22E4E4F99696': 'Only the wall-mounted water-feature panel is supplied. The basin, pump, water and plumbing are not included; installation requirements must be agreed separately.'}
elif mode == 'spiralfish':
    output_name = 'spiralfish-reviewed-upload-packets.json'
    positions = [('BSI-B19E0B8602C1', 'left-hand'), ('BSI-A272AC152172', 'right-hand')]
    cases = [(pid, 'id:cnqzTNngPVsAAAAAAArp_w', 'spiralfish-white-review.jpg') for pid, _ in positions]
    disclosures = {pid: f'Only the {position} panel of the rightmost pair in this room photograph is supplied. Its companion and the other artworks are sold separately; the room setting is not included.' for pid, position in positions}
elif mode == 'bordered':
    output_directory = PARENT / 'resume-2346'
    output_name = 'bordered-reviewed-upload-packets.json'
    positions = [('BSI-65A93033A200', 'left-hand'), ('BSI-4515726BBC18', 'right-hand')]
    cases = [(pid, 'id:cnqzTNngPVsAAAAAAAylEw', 'native-png-photo-review.jpg') for pid, _ in positions]
    disclosures = {pid: f'Only the {position} framed panel in this two-panel photograph is supplied. The companion panel is sold separately; the wall and mounting setting are not included.' for pid, position in positions}
    assert (output_directory / 'saatchi-primary-image-requirements.txt').exists()
    assert 'JPEG or PNG format' in (output_directory / 'saatchi-primary-image-requirements.txt').read_text()
elif mode == 'moon_shell':
    output_directory = PARENT / 'resume-2355'
    output_name = 'moon-shellwave-reviewed-upload-packets.json'
    positions = [('BSI-B9E2B67965E2', 'centre'), ('BSI-6FE9343F889E', 'right-hand')]
    aid = 'id:cnqzTNngPVsAAAAAAAuh1w'
    reviewed = read(output_directory / 'moon-shellwave-original-review.json')
    assert reviewed['image_id'] == aid and reviewed['status'] == 'PASS_FULL_ORIGINAL_REVIEW_MATCHED_COMPONENTS'
    headers[aid] = dict(width=reviewed['width'], height=reviewed['height'], expected_content_hash=reviewed['content_hash'])
    cases = [(pid, aid, 'unselected-native-photo-review.jpg') for pid, _ in positions]
    reviewed_manual_sources = {pid: aid for pid, _ in positions}
    disclosures = {pid: f'Only the {position} panel in this three-panel installation photograph is supplied. The other panels and room setting are not included. Warm interior lighting is shown; the offered finish is White.' for pid, position in positions}
elif mode == 'crater_white':
    output_directory = PARENT / 'resume-2355'
    output_name = 'crater-white-reviewed-upload-packets.json'
    positions = [('BSI-27B50C52ED10', 'fourth (rightmost) panel'),
                 ('BSI-8035F91E2A67', 'second panel from the left'),
                 ('BSI-89699A0F5BA9', 'first (leftmost) panel')]
    aid = 'id:cnqzTNngPVsAAAAAAAuYaQ'
    crater_native_photos = read(output_directory / 'crater-native-photo-verification.json')
    reviewed = read(output_directory / 'crater-texture-matching.json')
    assert reviewed['agent_visual_confirmation'] is True
    assert {r['role']: r['candidate_position'] for r in reviewed['records']} == {'I': 4, 'II': 2, 'III': 1}
    native = crater_native_photos['group']
    assert native['image_id'] == aid and native['pixel_edits'] is False
    headers[aid] = dict(width=native['width'], height=native['height'], expected_content_hash=native['content_hash'])
    cases = [(pid, aid, '../resume-2355/crater-match-visual-review.jpg') for pid, _ in positions]
    disclosures = {pid: f'Only the {position} in this four-panel photograph is supplied. The other three panels are sold separately. The offered finish is White.' for pid, position in positions}
packets = []
photo_root = PARENT / 'qualified-originals'
photo_root.mkdir(exist_ok=True)

with connection(ROOT) as (db, _):
    for pid, aid, comparison in cases:
        product = products[pid]
        fields = values(product)
        sku = fields['Seller SKU']
        assert sku not in bindings, 'Existing native artwork must be resumed instead'
        selected_in_situ = aid in {i['id'] for i in product['photos']['in_situ']['images']}
        assert selected_in_situ or reviewed_manual_sources.get(pid) == aid, 'No matching selected or manually reviewed source'
        photo = images[aid]
        header = headers[aid]
        expected = photo['original']['dropbox_content_hash']
        assert expected == header['expected_content_hash']
        meta = db.files_get_metadata(aid)
        assert meta.id == aid and meta.content_hash == expected
        assert meta.path_display == photo['provenance']['path']
        assert meta.path_display.startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/')
        assert meta.size < 50_000_000
        path = photo_root / photo['name']
        if path.exists():
            body = path.read_bytes()
        else:
            downloaded, response = db.files_download('rev:' + meta.rev)
            try:
                body = response.content
            finally:
                response.close()
            assert downloaded.id == aid and downloaded.content_hash == expected
        block_hash = sha(b''.join(hashlib.sha256(body[n:n + 4194304]).digest() for n in range(0, len(body), 4194304)))
        assert len(body) == meta.size and block_hash == expected
        if not path.exists():
            path.write_bytes(body)
        with Image.open(path) as im:
            assert im.size == (header['width'], header['height']) and im.mode == 'RGB'
            assert min(im.size) >= 1200 and max(im.size) >= 1500
            fmt = im.format
            gps_coordinate_tags = set(im.getexif().get_ifd(34853)) - {0}
        allowed_formats = {'MPO'} if mode == 'crater_white' else {'JPEG', 'PNG'} if mode == 'bordered' else {'JPEG'}
        assert fmt in allowed_formats, 'Native container acceptance needs separate review'
        assert not gps_coordinate_tags, 'Review GPS metadata before any external upload'
        row = rows[pid]
        case = model[pid]
        assert x.value(sheet, f'AQ{row}') == sku == case['sku']
        assert case['status'] == 'PLANNING_ESTIMATE'
        dims = [x.value(sheet, columns[h] + str(row)) for h in ['saatchi_width_cm', 'saatchi_height_cm', 'saatchi_depth_cm']]
        assert all(isinstance(v, (int, float)) and v > 0 for v in dims)
        assert x.value(sheet, columns['saatchi_asking_price_usd'] + str(row)) == case['asking_usd']
        disclosure = disclosures.get(pid, 'The photograph shows this single wall sculpture installed on a wall. One sculpture is supplied; the setting is not included.')
        content = dict(sku=sku, description_text=complete_description(product, sku, dispatch_days=3, channel='saatchi'),
                       colour=appearance(product), surface_effect=has_surface_effect(product), product_type=product_type(product))
        description = disclosure + '\n\n' + saatchi_description(content, limit=1000 - len(disclosure) - 2)
        assert len(description) <= 1000 and 'Sally Price' in description and 'gypsum-based' in description
        assert '3 working days' in description
        if content['surface_effect']:
            assert 'pattern will vary' in description
        proof = dict(image_id=aid, photo_path=meta.path_display, content_hash=expected, sha256=sha(body),
                     revision=meta.rev, bytes=meta.size, width=header['width'], height=header['height'],
                     format=fmt, local_path=str(path), native_upload_path=str(path), native_upload_sha256=sha(body),
                     visual_review=({'gleneagles': 'All four matching Gleneagles panels are fully visible in the genuine group photograph. Each corner was compared with the corresponding app primary; the supplied corner is explicitly identified. Warm lighting is disclosed. ',
                                     'spiralfish': 'Full-original inspection establishes that the matching White Spiralfish panels are the rightmost pair in the room photograph. Wave and Tide I is the left member; Wave and Tide II with its spiral is the right member. The initial thumbnail-only position was corrected before any upload. Other room artworks are excluded by the top-of-description disclosure. Contextual-primary suitability and saved appearance require native review. ',
                                     'bordered': 'Full-original inspection shows both complete White bordered panels on a brick wall, matching the current app primaries: Lunar Phase I is left, Lunar Phase II right. Each description identifies the supplied panel. Native primary uploader explicitly allows JPEG or PNG; no conversion is required. ',
                                     'moon_shell': 'Full original compared against both current app primaries. Moon and Shell Wave I is the centre spiral panel; Moon and Shell Wave II is the right-hand curved panel, not its mirrored left-hand neighbour. All panel edges are visible. Per-product location, separate sale and warm lighting are disclosed. This reviewed family original is a Saatchi-only alternative, not a new app Listing or primary selection. ',
                                     'crater_white': 'Original detail files matched separately to all four group positions with SIFT/RANSAC, then visually checked against the app primaries and complete group panels. I is fourth, II second and III first from the left. Each supplied panel is explicit in its description. Container normalization retains identical decoded pixels, colour profile and orientation. '}.get(mode, 'Complete single sculpture and matching design/finish compared with the current app primary. ')) + 'Unaltered original, no crop, upscaling, padding or generated detail added.',
                     comparison_evidence=str(OUT / comparison), gps_metadata_present=False,
                     app_use=('Existing selected In situ photograph; no app Listing or primary change.' if selected_in_situ else 'Manually reviewed family photograph selected as a Saatchi-only alternative; all app image purposes and primary selections remain unchanged.'),
                     checked_utc=datetime.now(timezone.utc).isoformat())
        if mode == 'crater_white':
            native = crater_native_photos['group']
            assert native['sha256'] == proof['sha256']
            proof.update(native_upload_path=native['native_upload_path'], native_upload_sha256=native['native_upload_sha256'],
                         native_upload_format='JPEG', native_upload_bytes=native['native_upload_bytes'],
                         decoded_pixel_sha256=native['decoded_pixel_sha256'], container_verification=str(output_directory / 'crater-native-photo-verification.json'))
        packets.append(dict(catalogue_id=pid, sku=sku, title=product['retail_name'], native_artwork_id=None,
                            native_action='RECONCILE_CURRENT_STUDIO_BEFORE_CREATE_ONCE', description=description,
                            description_characters=len(description), quantity_per_sale=1, dimensions_cm=dims,
                            target_artwork_price_usd=case['asking_usd'], native_packaging='Crate',
                            native_packed_weight_kg_estimate=case['packed_kg'], packed_dimensions_cm_estimate=case['packed_cm'],
                            packing_allowance_gbp=case['packing_allowance_gbp'],
                            packing_model_source=str(PARENT / 'packing/catalogue_wall_sculptures.xlsx'),
                            packing_model_source_sha256=packing_receipt['sha256'],
                            packing_model_dropbox_revision=packing_receipt['current']['rev'],
                            packing_estimate_qualification='Editable Saatchi-only crate planning estimate; labour zero. Weigh, measure and photograph the completed crate before collection. Carrier charges remain separate.',
                            edition_type=x.value(sheet, columns['saatchi_art_edition_type'] + str(row)),
                            edition_cap=x.value(sheet, columns['saatchi_art_edition_size'] + str(row)),
                            edition_scope='Saatchi Art only', creation_year=x.value(sheet, columns['saatchi_art_creation_year'] + str(row)),
                            creation_year_is_estimate=True, photo=proof,
                            publication_status='REVIEWED_CONTEXT_CANDIDATE_NATIVE_TEST_PENDING', app_photo_changes=0,
                            source_app_revision=app['revision'], source_workbook_sha256=pointer['sha256'],
                            required_native_checks=['Fresh whole-portfolio identity reconciliation before creating once',
                                                    'Saatchi CAPTCHA-verification block resolved',
                                                    f'Native {proof.get("native_upload_format", fmt)}/dimension/contextual-primary acceptance',
                                                    'Full saved description, exact price, edition, available quantity and packing readback before publication']))
        detail_proof = OUT / 'spiralfish-additional-original.json'
        if mode == 'spiralfish' and detail_proof.exists():
            additional = read(detail_proof)
            assert additional['status'] == 'PASS_FULL_ORIGINAL_REVIEW_ADDITIONAL_DETAIL_ONLY'
            assert additional['image_id'] == 'id:cnqzTNngPVsAAAAAAArqAg'
            assert sha(Path(additional['native_upload_path']).read_bytes()) == additional['native_upload_sha256']
            side = 'left' if pid == 'BSI-B19E0B8602C1' else 'right'
            additional['caption'] = f'Additional detail view of Spiralfish Wave and Tide I (left) and II (right), both White. This listing supplies the {side} panel only. Each panel is sold separately.'
            packets[-1]['additional_photos'] = [additional]
            packets[-1]['required_native_checks'].append('Save the unaltered two-panel detail photo as additional gallery media; preserve the full room photograph first and verify the supplied-panel disclosure')
        if mode == 'bordered':
            packets[-1]['native_image_requirements_evidence'] = str(output_directory / 'saatchi-primary-image-requirements.txt')
        if mode == 'crater_white':
            numeral = {'BSI-27B50C52ED10': 'I', 'BSI-8035F91E2A67': 'II', 'BSI-89699A0F5BA9': 'III'}[pid]
            detail = dict(crater_native_photos[numeral])
            detail.update(role='ADDITIONAL_DETAIL_ONLY_NOT_PRIMARY', visually_reviewed_full_original=True, original_unaltered=True,
                          caption=f'Detail of Crater Moon {numeral} - White. This listing supplies only that sculpture. Each panel is sold separately.')
            packets[-1]['additional_photos'] = [detail]
            packets[-1]['component_position_verification'] = str(output_directory / 'crater-texture-matching.json')
            packets[-1]['required_native_checks'].append('Keep the full four-panel group photograph first, save the specific numbered detail photograph as additional media, and verify the supplied panel location before publication')
        (output_directory / output_name).write_text(json.dumps(packets, ensure_ascii=False, indent=2) + '\n')
unique_photos = {p['photo']['image_id']: p['photo'] for p in packets}
print(json.dumps({'status': 'PASS_REVIEWED_ORIGINALS_PREPARED_NOT_UPLOADED', 'products': len(packets),
                  'unique_originals': len(unique_photos), 'bytes_retained': sum(p['bytes'] for p in unique_photos.values()), 'native_mutations': 0,
                  'app_category_changes': 0, 'prices_usd': {p['title']: p['target_artwork_price_usd'] for p in packets}}))
