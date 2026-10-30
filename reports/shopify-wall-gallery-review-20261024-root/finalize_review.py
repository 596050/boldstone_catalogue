"""Publish an isolated, hash-bound visual review; never the canonical catalogue."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
from urllib.parse import quote

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
N = ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z'

def read(p):
    return json.loads(Path(p).read_text())

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write(p, v):
    Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')

def main():
    checks = []
    def check(name, value):
        checks.append({'check': name, 'pass': bool(value)})
        assert value, name
    prep = read(H / 'preparation-receipt.json')
    cross = read(prep['crosswalk']['path'])
    check('Frozen R5 crosswalk exact', sha(prep['crosswalk']['path']) == prep['crosswalk']['sha256'])
    check('Canonical pointer unchanged', sha(ROOT / 'sculpture-catalogue/current-master.json') == prep['baseline_pointer_sha256'])
    pointer = read(ROOT / 'sculpture-catalogue/current-master.json')
    protected = {}
    for path in ['current-master.json', pointer['register'], pointer['workbook'],
                 pointer['current_asset_reference_map']['path'], pointer['current_native_reference_map']['path'],
                 'components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']:
        p = ROOT / 'sculpture-catalogue' / path
        protected[str(p)] = sha(p)
    rows = read(H / 'ranked-gallery-register.json')
    native = read(N / 'complete-current-native-object-map.json')
    evidence = {v['file_id']: v for v in read(N / 'current-6360-visual-source-evidence.json')}
    check('Fresh native map exact', sha(N / 'complete-current-native-object-map.json') == prep['native_map']['sha256'])
    check('Fresh visual source evidence exact', sha(N / 'current-6360-visual-source-evidence.json') == prep['native_visual_evidence']['sha256'])
    spec = importlib.util.spec_from_file_location('explicit_review', H / 'manual_visual_review.py')
    manual = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manual)
    observations = {}
    for line in manual.OBSERVATIONS.strip().splitlines():
        rid, role, correspondence, sq, note = line.split('|', 4)
        check('One explicit review row ' + rid, rid not in observations)
        observations[rid] = {'role': role, 'correspondence': correspondence, 'sq': sq, 'note': note}
    check('All117 explicit manual observations present', len(observations) == len(rows) == 117 and set(observations) == {r['review_id'] for r in rows})
    boards = read(H / 'boards/manifest.json')
    board_for = {}
    for b in boards:
        check('Analytical board unchanged ' + Path(b['path']).name, sha(b['path']) == b['sha256'])
        for item in b['items']:
            board_for[item['review_id']] = {'path': b['path'], 'sha256': b['sha256'], 'slot': item['slot']}
    sq_frames = read(H / 'input-snapshots/squarespace-renditions.json')
    final = []
    for row in rows:
        rid = row['review_id']
        obs = observations[rid]
        receipt = row['source_download']
        check('Shopify source bytes unchanged ' + rid, sha(receipt['path']) == receipt['sha256'])
        check('No explicit variant image exported ' + rid, row['exported_gallery_row']['variant_image_raw'] == '')
        candidate = row['ranked_native_candidates'][0]
        chosen = manual.OVERRIDE_NATIVE_IDS.get(rid, candidate['native']['file_id'])
        e = evidence[chosen]
        n = native[chosen]
        check('Native source bytes bound ' + rid, sha(e['source_image_path']) == e['actual_visual_source_sha256'])
        check('Actual native parent linked ' + rid, n['parent_id'] == n['folder_id'] and native[n['parent_id']]['display_path'] == n['folder_path'])
        photo = obs['correspondence'] != 'U'
        disposition = {'F': 'VISUALLY_CORRESPONDING_PHOTOGRAPH_AT_DISPLAYED_RESOLUTION',
                       'R': 'VISUAL_CROP_FRAMING_OR_CONTRAST_RENDITION_CORRESPONDENCE',
                       'U': 'SAME_SCENE_OR_DESIGN_CANDIDATE_EXACT_PHOTOGRAPH_UNRESOLVED'}[obs['correspondence']]
        sq = row['ranked_squarespace_candidates'][0]
        sq_matches = []
        if obs['sq'] == 'A':
            selected = sq['selected_rendition']
            check('SQ frame bytes bound ' + rid, sha(selected['path']) == selected['sha256'])
            # Duplicate gallery occurrences share the exact same retained image
            # bytes; these are occurrence links, never extra visual reviews.
            same = [v for v in sq_frames if v.get('selected_rendition', {}).get('sha256') == selected['sha256']]
            for frame in same:
                sq_matches.append({'offer_ref': frame['offer_ref'], 'gallery_order': frame['gallery_order'],
                    'gallery_entry_id': frame['gallery_entry_id'], 'source_url': frame['source_url'],
                    'csv_record_including_header_1based': frame['csv_record_including_header_1based'],
                    'squarespace_product_id': frame['native_product_id'],
                    'source_document': frame['source_document'], 'source_document_sha256': frame['source_document_sha256'],
                    'selected_rendition': frame['selected_rendition'],
                    'proof_scope': 'Shopify and displayed SQ frames visually compared; additional occurrences use same retained SQ rendition SHA256.',
                    'variant_specific_assignment_certified': False})
        f = {k: row[k] for k in ['review_id', 'handle', 'title', 'gallery_order', 'exported_gallery_row', 'matched_squarespace_offer_refs', 'exported_skus']}
        f.update({'source_download': receipt, 'source_visual_role': obs['role'],
            'native_correspondence_disposition': disposition,
            'native_photo_correspondence': ({'file_id': chosen, 'native_reference': n, 'visual_source': e} if photo else None),
            'native_scene_or_design_candidate': (None if photo else {'file_id': chosen, 'native_reference': n, 'visual_source': e}),
            'squarespace_photo_correspondences': sq_matches,
            'squarespace_correspondence_status': ('VISUALLY_CORRESPONDING_SOURCE_FRAME' if sq_matches else 'NO_SAME_FRAME_SQ_CORRESPONDENCE_ESTABLISHED_IN_REVIEWED_445_ENTRIES'),
            'rejected_numerical_top_is_not_a_match': (candidate['native']['file_id'] if rid in manual.OVERRIDE_NATIVE_IDS else None),
            'source_role_and_uncertainty_note': obs['note'],
            'evidence_board': board_for[rid],
            'focused_evidence_board': None,
            'exact_encoded_original_bytes_or_pixel_identity_claimed': False,
            'new_physical_specification_or_cast_identity_verified': False,
            'variant_specific_assignment_certified': False,
            'stock_price_or_configuration_field_transfer': False,
            'installation_creation_origin_newly_verified': False,
            'new_component_or_finish_record_created': False,
            'canonical_binding_applied': False})
        if rid in manual.FOCUSED_REVIEW_IDS:
            p = H / 'boards' / ('focused-' + rid + '.jpg')
            f['focused_evidence_board'] = {'path': str(p), 'sha256': sha(p)}
        final.append(f)
    role_counts = dict(Counter(r['source_visual_role'] for r in final))
    count = {'local_shopify_wall_products': len({r['handle'] for r in final}),
             'gallery_occurrences_visually_reviewed': len(final), 'unique_exported_image_urls': len({r['exported_gallery_row']['image_src'] for r in final}),
             'source_role_counts': role_counts,
             'native_photo_correspondences': sum(r['native_photo_correspondence'] is not None for r in final),
             'distinct_corresponding_native_file_ids': len({r['native_photo_correspondence']['file_id'] for r in final if r['native_photo_correspondence']}),
             'exact_photo_unresolved_scene_candidates': sum(r['native_scene_or_design_candidate'] is not None for r in final),
             'shopify_frames_with_squarespace_photo_correspondence': sum(bool(r['squarespace_photo_correspondences']) for r in final),
             'shopify_frames_without_established_squarespace_photo_correspondence': sum(not r['squarespace_photo_correspondences'] for r in final),
             'new_variant_image_assignments': 0, 'new_component_identities': 0, 'new_actual_specifications': 0,
             'native_or_platform_writes': 0, 'canonical_writes': 0}
    check('Counts reconcile all117 source frames', sum(role_counts.values()) == 117 and count['native_photo_correspondences'] + count['exact_photo_unresolved_scene_candidates'] == 117)
    packet = {'schema': 'boldstone.local-shopify-wall-full-gallery-visual-review.v1',
        'status': 'VISUAL_REVIEW_COMPLETE_WITH_QUALIFIED_CORRESPONDENCES_AND_THREE_EXACT_PHOTO_UNCERTAINTIES',
        'reviewed_utc': datetime.now(timezone.utc).isoformat(), 'preparing_thread': '01a144ab-1a7c-7223-a403-73a4d53d70ff',
        'baseline_pointer_sha256': prep['baseline_pointer_sha256'], 'counts': count,
        'source_authority': 'User requested the existing local Shopify export, not a live store/admin review. Exact handle, raw SKU and local CSV row locators retained.',
        'local_shopify_csv': prep['original_local_shopify_csv'], 'crosswalk': prep['crosswalk'],
        'native_inventory': prep['native_map'], 'native_visual_evidence': prep['native_visual_evidence'],
        'squarespace_gallery_input_snapshot': {'path': str(H / 'input-snapshots/squarespace-renditions.json'), 'sha256': sha(H / 'input-snapshots/squarespace-renditions.json')},
        'scope': 'Product gallery membership and visual photo correspondences only. CSV Variant Image is blank for every reviewed occurrence. Numeric Shopify product/variant IDs are not exported.',
        'frozen_holds': {'installation_gaps': 22, 'series_gaps': 1, 'legacy_frozen_fish_identity': 'DEFERRED_OWNER_QUESTION_OWNED_BY_RECOVERY', 'Frozen_Fish_current_dimensions': '70 H x 15 W cm', 'no_squarespace_writes': True},
        'protected_current_files': protected, 'records': final}
    write(H / 'shopify-wall-gallery-visual-review.json', packet)
    esc = html.escape
    def link(url, text):
        return '<a href="' + esc(url, quote=True) + '">' + esc(text) + '</a>'
    def local(path):
        return quote(os.path.relpath(path, H), safe='/')
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>117 local Shopify wall gallery images</title><style>body{font:17px/1.5 system-ui;max-width:1260px;margin:2rem auto;padding:0 1rem;color:#222}h2{border-top:2px solid #777;padding-top:1rem}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1rem}.card{border:1px solid #bbb;border-radius:8px;padding:1rem;overflow-wrap:anywhere}img{width:100%;height:290px;object-fit:contain;background:#eee}.uncertain{border:3px solid #b87816}.tag{font-weight:700}.meta{font-size:14px}pre{white-space:pre-wrap}nav ul{columns:2}.legend{background:#f0f3f6;padding:1rem}small{display:block}</style></head><body><h1>Local Shopify wall-sculpture gallery review</h1>',
        '<p>All117 exported image entries across38 products visually reviewed. 114 visual photograph/rendition correspondences to current Dropbox file IDs; three scene/design candidates remain uncertain as exact photographs. These are gallery-entry counts, not sculpture or physical stock counts.</p>',
        '<p class="legend">Every image has its exported handle, raw SKU, source row, visual role, and current Dropbox image/folder links. Group and cross-finish photographs retain their qualifications. No explicit Variant Image values were exported, so product galleries are not promoted to variant-specific images. All working specifications, owner holds, prices and availability remain separate.</p>',
        '<p>' + link('shopify-wall-gallery-visual-review.json', 'Structured review') + ' · ' + link('verification.json', 'Verification') + ' · ' + link('../local-platform-crosswalk-corrected-20261024-root/index.html', 'Full local source comparison') + '</p><nav><ul>']
    products = defaultdict(list)
    for r in final:
        products[r['handle']].append(r)
    for handle, product in products.items():
        parts.append('<li>' + link('#' + handle, product[0]['title']) + ' (' + str(len(product)) + ' images)</li>')
    parts.append('</ul></nav>')
    for handle, product in products.items():
        parts += ['<section id="' + esc(handle) + '"><h2>' + esc(product[0]['title']) + '</h2><p>Handle: <code>' + esc(handle) + '</code> · raw SKU: ' + esc(', '.join(product[0]['exported_skus']) or '(blank)') + '</p><div class="gallery">']
        for r in product:
            unresolved = r['native_photo_correspondence'] is None
            ref = (r['native_photo_correspondence'] or r['native_scene_or_design_candidate'])['native_reference']
            parts += ['<article class="card' + (' uncertain' if unresolved else '') + '" id="' + r['review_id'] + '"><h3>' + r['review_id'] + ' · gallery ' + str(r['gallery_order']) + '</h3>',
                      '<a href="' + local(r['source_download']['path']) + '"><img loading="lazy" src="' + local(r['source_download']['path']) + '" alt="Exported Shopify source photograph"></a>',
                      '<p class="tag">' + esc(r['source_visual_role'].replace('_', ' ')) + (' · exact photograph unresolved' if unresolved else '') + '</p><p>' + esc(r['source_role_and_uncertainty_note']) + '</p>',
                      '<p>' + link(ref['image_url'], 'Dropbox scene candidate' if unresolved else 'Dropbox image') + ' · ' + link(ref['folder_url'], 'Actual containing folder') + '</p>',
                      '<p class="meta">File ID: <code>' + esc(ref['file_id']) + '</code><br>Folder ID: <code>' + esc(ref['folder_id']) + '</code><br>' + esc(r['native_correspondence_disposition'].replace('_', ' ').lower()) + '</p>',
                      '<p class="meta">' + link(r['exported_gallery_row']['image_src'], 'Exact exported Shopify image URL') + ' · CSV row ' + str(r['exported_gallery_row']['source_row']['logical_row_including_header']) + '</p>']
            if r['squarespace_photo_correspondences']:
                labels = [x['offer_ref'] + '/' + str(x['gallery_order']) for x in r['squarespace_photo_correspondences']]
                parts.append('<p class="meta">Corresponding SQ gallery frame(s): ' + esc(', '.join(labels)) + '</p>')
            else:
                parts.append('<p class="meta">No same-frame SQ correspondence established in the reviewed445-entry comparison.</p>')
            parts.append('<p class="meta">' + link(local(r['evidence_board']['path']), 'Analytical comparison sheet') + (' · ' + link(local(r['focused_evidence_board']['path']), 'Focused comparison') if r['focused_evidence_board'] else '') + '</p></article>')
        parts.append('</div></section>')
    parts.append('<p>Display and room photographs have no new creation-origin certification. Physical measurements, weights, material composition and fitted hardware remain as qualified working records until verified.</p></body></html>')
    (H / 'index.html').write_text('\n'.join(parts) + '\n')
    for path, digest in protected.items():
        check('Protected canonical/source file unchanged ' + path, sha(path) == digest)
    write(H / 'verification.json', {'status': 'PASS', 'checks_passed': len(checks), 'checks_total': len(checks),
        'checks': checks, 'review_sha256': sha(H / 'shopify-wall-gallery-visual-review.json'),
        'reader_sha256': sha(H / 'index.html'), 'counts': count})
    files = [H / 'prepare_review.py', H / 'manual_visual_review.py', H / 'finalize_review.py', H / 'preparation-receipt.json',
             H / 'download-receipts.json', H / 'ranked-gallery-register.json', H / 'boards/manifest.json',
             H / 'input-snapshots/squarespace-renditions.json', H / 'shopify-wall-gallery-visual-review.json', H / 'index.html', H / 'verification.json']
    files += [Path(b['path']) for b in boards]
    files += sorted((H / 'boards').glob('focused-*.jpg'))
    write(H / 'sealed-handoff.json', {'status': 'SEALED_LOCAL_SHOPIFY_WALL_GALLERY_VISUAL_REVIEW',
        'recorded_utc': datetime.now(timezone.utc).isoformat(), 'files': {str(p): sha(p) for p in files},
        'counts': count, 'independent_qa_pending': True})
    print(json.dumps({'status': 'PASS', 'checks': len(checks), 'counts': count, 'seal_sha256': sha(H / 'sealed-handoff.json')}, indent=2))

if __name__ == '__main__':
    main()
