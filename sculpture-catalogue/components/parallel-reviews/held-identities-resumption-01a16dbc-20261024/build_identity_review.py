"""Prepare evidence and four precise identity decisions, without changing the catalogue."""
import hashlib
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageOps

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = Path(__file__).resolve().parent
W = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-03'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
checks, inputs, image_inputs = [], {}, {}


def check(label, passed):
    checks.append({'check': label, 'pass': bool(passed)})
    assert passed, label


def source(path, expected=None):
    path = Path(path)
    actual = sha(path)
    if expected:
        check('Evidence bytes: ' + str(path), actual == expected)
    inputs[str(path)] = actual
    return read(path)


def image_info(path, expected=None):
    path = Path(path)
    actual = sha(path)
    if expected:
        check('Saved image bytes: ' + str(path), actual == expected)
    with Image.open(path) as image:
        image.load()
        rgba = ImageOps.exif_transpose(image).convert('RGBA')
    image_inputs[str(path)] = actual
    return {'path': str(path), 'sha256': actual, 'dimensions': list(rgba.size), 'full_decode_passed': True,
            'decoded_RGBA_sha256': hashlib.sha256(rgba.tobytes()).hexdigest()}


p = source(B / 'current-master.json')
g = source(B / p['register'], p['register_sha256'])
assets = source(B / p['current_asset_reference_map']['path'], p['current_asset_reference_map']['sha256'])
options = {x['product_id']: x for x in g['options']}
crosswalk = source(W / 'WALL_CIRCLE_CROSSWALK.json')
pairwise = source(crosswalk['pairwise_review_ref']['path'], crosswalk['pairwise_review_ref']['sha256'])
bindings = source(B / 'components/parallel-reviews/wall-circle-2026-10-17/family-keep/native-pattern-image-bindings.json')
native_readback = source(H / 'wall-native-binding-readback.json')
source_readback = source(H / 'wall-source-readback.json')
ownership = source(H / 'OWNERSHIP.json')
family_receipts = source(H / 'family-listing-and-history-receipts.json')
replacement_seal = source(H / 'deleted-reference-resolution/sealed-handoff.json', '393fcd0e24b77a32412e142d2efe33bb53402e475f2d07aee55455f22b9baad5')
for path, expected in replacement_seal['files'].items():
    check('Separate link-resolution sealed artifact: ' + path, sha(path) == expected)
link_proposal = source(H / 'deleted-reference-resolution/proposed-reference-replacements.json')
legacy_prior = source(B / 'components/parallel-reviews/frozen-fish-long-source-gap-2026-10-20/EVIDENCE_RECONCILIATION.json')
legacy_source = source(B / 'components/parallel-reviews/frozen-fish-long-source-gap-2026-10-20/SOURCE_RECORD.json')
check('Later captured144 tuples and gallery order independently verified', native_readback['all_144_variant_ID_SKU_attributes_match_later_captured_export'] and native_readback['all_gallery_URLs_and_order_match_later_captured_export'])
check('Eighteen native pattern identities retained', len(bindings) == native_readback['named_patterns'] == 18)
patterns = []
for binding in bindings:
    info = image_info(binding['local_image'], binding['image_sha256'])
    named = [x for x in native_readback['variants'] if x['attributes']['Pattern'] == binding['pattern']]
    check('Eight retained tuples and exact old image binding: ' + binding['pattern'], len(named) == 8 and {x['native_main_image_id_observed_20261021'] for x in named} == {binding['image']['id']})
    patterns.append({'pattern': binding['pattern'], 'native_pattern_image_id': binding['image']['id'], 'source_image_url': binding['image']['assetUrl'],
        'cached_image': info, 'native_variant_ids': [x['native_variant_id'] for x in named],
        'source_clock': 'Image bytes17October; exact native mainImage IDs21October;144 tuple labels/IDs and gallery URL order corroborated by captured24October admin export.'})
records, decisions = [], []
for entry in crosswalk['entries']:
    option = options[entry['product_id']]
    board = image_info(entry['inspection_board_ref']['path'], entry['inspection_board_ref']['sha256'])
    saved = next(x for x in source_readback['rows'] if x['review_id'] == entry['review_id'])
    current_ref = {k: option[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']}
    proposed = next((x for x in link_proposal['changes'] if x['option_id'] == entry['product_id']), None)
    pattern = entry['pattern_assignment']
    check('Current option keeps exact historical appearance identity: ' + entry['review_id'], option['source_scopes'] == [entry['canonical_key']] and len(option['master_fields']) == 6)
    check('No unsupported pattern promotion: ' + entry['review_id'], pattern['state'] in ['CONDITIONAL_VISUAL_PATTERN_DESIGN_LINK', 'UNRESOLVED_NO_SUPPORTED_PATTERN_AMONG_18'])
    record = {'review_id': entry['review_id'], 'product_id': entry['product_id'], 'name': option['name'],
        'whole_option_sha256': digest(option), 'master_fields': option['master_fields'], 'current_reference': current_ref,
        'proposed_equivalent_reference_if_deleted': proposed['proposed'] if proposed else None,
        'source_original': saved, 'comparison_board_reopened': board, 'retained_pattern_assignment': pattern,
        'new_pattern_or_physical_assignment': False, 'native_exact_configuration_verified': False}
    records.append(record)
    if pattern['state'] == 'UNRESOLVED_NO_SUPPORTED_PATTERN_AMONG_18':
        decisions.append({'decision_id': entry['review_id'] + '-PATTERN', 'product_id': entry['product_id'], 'name': option['name'],
            'question': 'Which exact existing Pattern label applies to this image, or is it a custom/unlisted pattern outside these18?',
            'comparison_board': board['path'], 'image_url': option['image_url'], 'folder_url': option['folder_url'],
            'answer_scope': 'This appearance-to-pattern association only. No diameter, lighting, material, stock or SKU is inferred. No new native variant is created.'})
legacy = options['BSI-04D6E8690F30']
candidate = options['BSI-FE10273D3655']
maker = image_info('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z/manufacturing-images/picture-045.jpg')
candidate_image = image_info(assets[candidate['file_id']]['full'])
candidate_bytes = Path(candidate_image['path']).read_bytes()
candidate_hash = hashlib.sha256(b''.join(hashlib.sha256(candidate_bytes[i:i + 4194304]).digest() for i in range(0, len(candidate_bytes), 4194304))).hexdigest()
check('Frozen Fish cached original matches recorded native content hash and size', candidate_hash == assets[candidate['file_id']]['source_content_hash'] and len(candidate_bytes) == assets[candidate['file_id']]['bytes'])
check('Frozen Fish comparison file ID and exact path occur in complete fresh family listing', any(x.get('file_id') == candidate['file_id'] and x.get('path') == assets[candidate['file_id']]['path'] for x in family_receipts['requests'][1]['result']['structuredContent']['entries']))
candidate_image['verification_scope'] = 'Cached original matches recorded asset-map hash and size; exact file ID/path occurs in fresh family listing. No fresh native original content-hash check for this comparison file in this packet.'
check('Legacy record remains unbound at current owner70x15 size', legacy['canonical_component_id'] is None and not legacy['file_id'] and legacy['current_legacy_identity_disposition']['same_as_FFS2_not_assumed'] is True and legacy['current_legacy_identity_disposition']['current_face_cm'] == {'height': 70, 'width': 15})
records.append({'review_id': 'LEGACY-FFL1', 'product_id': legacy['product_id'], 'name': legacy['name'],
    'whole_option_sha256': digest(legacy), 'master_fields': legacy['master_fields'], 'current_reference': {k: legacy[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']},
    'current_legacy_identity_disposition': legacy['current_legacy_identity_disposition'], 'historical_size_relationship': legacy['source_size_relationship'],
    'maker_illustration': maker, 'candidate_comparison_only': {'product_id': candidate['product_id'], 'name': candidate['name'],
        **{k: candidate[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']}, 'saved_image': candidate_image},
    'finding': 'Maker row73 explicitly places FFS2-70x15 in SizeA and FFL1-100x22 in SizeB, and reuses picture045 for both. Owner current70x15 instruction removes a current100x22 default; it does not establish whether legacyFFL1 aliases FFS2 or a different relief. The current52-file family listing and shared maker image do not supply that missing declaration. No photograph is assigned to the legacy row.'})
decisions.insert(0, {'decision_id': 'LEGACY-FFL1-FFS2-RELIEF', 'product_id': legacy['product_id'],
    'question': 'Does legacy Frozen Fish Long (FFL1) mean the same relief design as Frozen Fish Two White (FFS2) shown here, now that all current Frozen Fish use70×15cm?',
    'image_url': candidate['image_url'], 'folder_url': candidate['folder_url'], 'maker_reference': maker['path'],
    'answer_scope': 'Exact FFL1-to-FFS2 relief-design relationship only. Historical100x22 sources, separate finishes, commercial fields, stock and actual cast measurements are retained separately.',
    'not_yet_asked': True})
check('Eight identity records retain all48 complete fields', len(records) == 8 and sum(len(x['master_fields']) for x in records) == 48)
check('Four exact owner identity decisions remain; none fabricated', len(decisions) == 4 and {x['decision_id'] for x in decisions} == {'LEGACY-FFL1-FFS2-RELIEF', 'WC-03-PATTERN', 'WC-06-PATTERN', 'WC-07-PATTERN'})
for path, expected in inputs.items():
    check('Evidence unchanged after local review: ' + path, sha(path) == expected)
report = {'status': 'EVIDENCE_REVIEW_COMPLETE_FOUR_IDENTITY_DECISIONS_STILL_REQUIRED', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'source_pointer_sha256': inputs[str(B / 'current-master.json')], 'register_sha256': p['register_sha256'], 'workbook_sha256': p['workbook_sha256'],
    'identity_records': records, 'native_patterns': patterns, 'owner_decisions_prepared_not_submitted': decisions,
    'counts': {'identity_records': 8, 'full_qualified_fields_retained': 48, 'WallCircle_appearance_records': 7,
        'native_pattern_swatches': 18, 'comparison_boards_reopened': 7, 'retained_pairwise_comparisons': 126,
        'retained_conditional_pattern_links': 4, 'unresolved_pattern_labels': 3, 'unresolved_legacy_relief_relationship': 1,
        'current_WallCircle_family_files': 159, 'current_FrozenFish_family_files': 52,
        'prepared_current_equivalent_reference_replacements': 2, 'new_identity_decisions': 0, 'new_owner_questions_issued': 0,
        'live_connector_read_calls_in_this_investigation': 30, 'new_downloads': 0, 'native_or_platform_or_canonical_writes': 0},
    'source_inputs': inputs, 'image_inputs': image_inputs,
    'full_gallery_role_review_owner': 'Directory session01a159af; this packet does not claim a whole211-image visual role review.',
    'physical_and_photo_holds': '22 installation gaps and1 series gap stay deferred. Acanthus physical question remains with its existing owner; no physical details reasked.',
    'completion_requirement': 'Owner identity declarations or independently labelled source evidence are required for the three unmatched Pattern labels and legacyFFL1 relationship. If an appearance is custom/unlisted, record that explicitly instead of forcing a native Pattern match. Conditional matches and source-image reuse are not exact physical/variant verification.',
    'live_sandbox_tested': False}
(H / 'identity-review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
e = html.escape
local = lambda p: e(quote(os.path.relpath(p, H), safe='/'), quote=True)
parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wall Circle and legacy Frozen Fish identity review</title><style>body{font:16px/1.5 system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#222}section{border-top:1px solid #bbb;padding:1.5rem 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem}img{width:100%;max-height:620px;object-fit:contain;background:#eee}.swatch img{height:280px}figure{margin:0}a{overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{padding:.7rem;border:1px solid #ccc;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}</style></head><body><h1>Wall Circle and legacy Frozen Fish: identity evidence</h1><p>Four existing conditional pattern links remain supported. Three Wall Circle appearances still have no safe named-pattern assignment. LegacyFFL1 still needs an exact design declaration. No owner answer, new native variant or physical specification is inferred.</p><p><a href="deleted-reference-resolution/index.html">Two verified current equivalents for deleted references</a> · <a href="#LEGACY-FFL1">Frozen Fish comparison</a> · <a href="#patterns">All18 named pattern references</a> · <a href="identity-review.json">Full structured evidence</a></p>']
legacy_record = records[-1]
comparison = legacy_record['candidate_comparison_only']
parts += ['<section id="LEGACY-FFL1"><h2>LegacyFFL1 compared with current Frozen Fish Two White</h2><p>' + e(legacy_record['finding']) + '</p>',
    '<p><strong>Prepared identity question:</strong> ' + e(decisions[0]['question']) + '</p>',
    f'<p><a href="{e(comparison["image_url"], quote=True)}">Current FFS2 comparison image</a> · <a href="{e(comparison["folder_url"], quote=True)}">Containing folder</a></p><div class="grid">',
    f'<figure><a href="{local(maker["path"])}"><img src="{local(maker["path"])}" alt="Maker picture045 shared by two historical size codes"></a><figcaption>Maker picture045 reused for both historical size codes;178×282px</figcaption></figure>',
    f'<figure><a href="{local(candidate_image["path"])}"><img src="{local(candidate_image["path"])}" alt="Current FFS2 White comparison image"></a><figcaption>Current FFS2 comparison reference; no FFL1 binding asserted</figcaption></figure></div></section>']
for record in records[:-1]:
    ref = record['current_reference']
    assignment = record['retained_pattern_assignment']
    parts += [f'<section id="{record["review_id"]}"><h2>{e(record["name"])}</h2><p>{e(assignment["state"])}: {e(assignment.get("pattern_short_name") or "No supported existing Pattern label")}</p><p>{e(assignment["basis"])}</p>',
        f'<p><a href="{e(ref["image_url"], quote=True)}">Saved Dropbox image</a> · <a href="{e(ref["folder_url"], quote=True)}">Containing folder</a></p>',
        f'<a href="{local(record["comparison_board_reopened"]["path"])}"><img src="{local(record["comparison_board_reopened"]["path"])}" alt="{record["review_id"]} compared with18 named patterns"></a>']
    if record['proposed_equivalent_reference_if_deleted']:
        new = record['proposed_equivalent_reference_if_deleted']
        parts += [f'<p>Saved ID has a deleted history. <a href="{e(new["image_url"], quote=True)}">Verified current equivalent</a>; <a href="deleted-reference-resolution/index.html#{record["product_id"]}">comparison and guarded correction</a>.</p>']
    if assignment['state'] == 'UNRESOLVED_NO_SUPPORTED_PATTERN_AMONG_18':
        parts += ['<p><strong>Prepared identity question:</strong> Which exact existing Pattern label applies, or is this a custom/unlisted pattern outside these18?</p>']
    parts += ['</section>']
parts += ['<section id="patterns"><h2>The18 retained named Pattern references</h2><p>Native labels and variant image bindings retain their21October observation clock. All144 variant ID/SKU/attribute tuples and24 gallery URLs/order agree with the later24October captured admin export.</p><div class="grid">']
for pattern in patterns:
    parts += [f'<figure class="swatch"><a href="{local(pattern["cached_image"]["path"])}"><img loading="lazy" src="{local(pattern["cached_image"]["path"])}" alt="{e(pattern["pattern"], quote=True)}"></a><figcaption>{e(pattern["pattern"])}</figcaption></figure>']
parts += ['</div></section><section><h2>Complete current qualified working fields retained</h2>']
for record in records:
    parts += ['<details><summary>' + e(record['name']) + '</summary><table>']
    for label, field in record['master_fields'].items():
        parts += [f'<tr><th>{e(label)}</th><td>{e(field["display"])}<details><summary>Full state and basis</summary><pre>{e(json.dumps(field, ensure_ascii=False, indent=2))}</pre></details></td></tr>']
    parts += ['</table></details>']
parts += ['</section><p>' + e(report['completion_requirement']) + '</p><p>' + e(report['physical_and_photo_holds']) + '</p></body></html>']
(H / 'identity-review.html').write_text('\n'.join(parts))
verification = {'status': 'PASS', 'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks,
    'review_sha256': sha(H / 'identity-review.json'), 'html_sha256': sha(H / 'identity-review.html')}
(H / 'identity-verification.json').write_text(json.dumps(verification, indent=2) + '\n')
names = ['build_identity_review.py', 'identity-review.json', 'identity-review.html', 'identity-verification.json', 'wall-source-readback.json', 'wall-native-binding-readback.json']
(H / 'sealed-identity-review.json').write_text(json.dumps({'status': 'SEALED_EVIDENCE_WITH_FOUR_IDENTITY_DECISIONS_OPEN', 'recorded_utc': report['recorded_utc'],
    'files': {n: sha(H / n) for n in names}}, indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'checks_passed': len(checks), 'identity_decisions_still_required': 4,
    'review': str(H / 'identity-review.html'), 'seal_sha256': sha(H / 'sealed-identity-review.json')}))
