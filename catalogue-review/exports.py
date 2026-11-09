"""Review bundles and separate listing/advertising media collections."""
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import sqlite3
import uuid
import zipfile
from projection import Projection
from presentation import listing_value
from component_photos import component_photos
from costing import product_cost, priced_listing_value, settings as cost_settings
from image_formats import IMAGE_HEADER_BYTES, image_type_from_header


def field_review_matches_source(record, field, source_hash):
    """A publication elsewhere is harmless only when this source field is exact.

    The first-review snapshot remains provenance, not something to rewrite to
    make an old review pass. Missing or changed snapshots still require review.
    """
    return record.get('source_hash') == source_hash or record.get('original') == field


def image_review_matches_source(view, pid, aid):
    """Prove unchanged original bytes for every contributing older review.

    Names, URLs and revisions can change during organisation. They are not
    image identity. No comparable original hash means no automatic carryover.
    """
    current = view.cat.assets[aid].get('original', {})
    for record in view.raw:
        if (record['kind'] != 'image' or record['product_id'] != pid or
                view.cid(record['item_id']) != aid):
            continue
        if record.get('source_hash') == view.cat.source['register_sha256']:
            continue
        reviewed = record['data'].get('reviewed_content_hash')
        if reviewed:
            if reviewed != current.get('dropbox_content_hash'):
                return False
        else:
            original = record.get('original', {}).get('asset', {}).get('original', {})
            comparable = [key for key in ('dropbox_content_hash', 'sha256')
                          if original.get(key) and current.get(key)]
            if not comparable or any(original[key] != current[key] for key in comparable):
                return False
    return True


def safe_name(value):
    return re.sub(r'[^a-zA-Z0-9_-]+', '-', value).strip('-')[:95] or 'item'


def image_type(path):
    with Path(path).open('rb') as stream:
        return image_type_from_header(stream.read(IMAGE_HEADER_BYTES))


def copied_identity(stream):
    """Hash the copied payload through its open descriptor, never a reopened path."""
    stream.seek(0)
    sha, blocks = hashlib.sha256(), hashlib.sha256()
    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
        sha.update(block)
        blocks.update(hashlib.sha256(block).digest())
    return {'sha256': sha.hexdigest(), 'dropbox_content_hash': blocks.hexdigest()}


def csv_write(path, columns, rows):
    def value(v):
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False)
        if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')):
            v = "'" + v
        return v
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: value(v) for k, v in row.items()})


def create_export(catalogue, store, include_media=False):
    export_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    root = store.root / 'exports' / export_id
    root.mkdir(parents=True)
    store.backup(root / 'review-backup.sqlite3')
    with closing(sqlite3.connect(root / 'review-backup.sqlite3')) as snapshot:
        snapshot.row_factory = sqlite3.Row
        reviews = [store.unpack(row) for row in snapshot.execute('SELECT * FROM reviews ORDER BY updated_at')]
    view = Projection(catalogue, reviews)
    lookup = view.effective
    def decision(kind, pid='', item=''):
        return lookup.get((kind, pid, item), {}).get('data', {})
    payload = {'schema': 'boldstone-review/v2', 'created_utc': datetime.now(timezone.utc).isoformat(),
               'source': catalogue.source, 'reviews': reviews,
               'duplicate_groups': getattr(catalogue, 'duplicate_groups', []),
               'effective_reviews': view.reviews,
               'application_status': ('Review decisions and native-file deletion receipts. Canonical catalogue and online stores are unchanged.'
                                      if any(r['kind'] == 'deletion' for r in reviews) else
                                      'Local review decisions only. Canonical catalogue and online stores are unchanged.')}
    (root / 'review-decisions.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    config, config_version = cost_settings(reviews)
    costs = [{'product_id': pid, 'name': product['name'], **product_cost({**product, 'id': pid}, reviews, (config, config_version))} for pid, product in catalogue.products.items()]
    (root / 'manufacturing-costs.json').write_text(json.dumps({'settings': config, 'settings_version': config_version, 'products': costs}, ensure_ascii=False, indent=2))
    for cost in costs:
        cost.update(pricing_mode=cost['pricing']['mode'], markup_percent=cost['pricing']['markup_percent'],
                    marked_up_price=cost['pricing']['marked_up_price'], listing_price=cost['pricing']['listing_value'])
    csv_write(root / 'manufacturing-costs.csv', ['product_id','name','status','material_label','material_cost','finish_cost','fixing_cost','overhead_cost','other_cost','manufacturing_cost','labour_hours','labour_cost','subtotal_before_labour','total_cost','pricing_mode','markup_percent','marked_up_price','listing_price','inputs'], costs)
    packages = [{'product_id': r['product_id'], 'name': catalogue.products[r['product_id']]['name'],
                 'saved_at': r['updated_at'], **r['data']} for r in reviews
                if r['kind'] == 'delivery' and r['product_id'] in catalogue.products]
    csv_write(root / 'delivery-packages.csv', ['product_id', 'name', 'saved_at', 'length_cm', 'width_cm', 'depth_cm',
              'weight_kg', 'destination', 'collection', 'packaging_gbp'], packages)
    costs_by_id = {c['product_id']: c for c in costs}
    field_rows, product_rows, media_rows = [], [], []
    for pid, product in catalogue.products.items():
        cost = costs_by_id[pid]
        p = decision('product', pid)
        output = {'product_id': pid, 'name': product['name'], 'family': product['family'],
                  'listing_decision': p.get('decision', 'pending'), 'review_status': p.get('status', 'unreviewed'),
                  'notes': p.get('notes', ''), 'pricing_method': cost['pricing_mode'],
                  'markup_percent': cost['markup_percent'], 'manufacturing_cost': cost.get('manufacturing_cost', ''),
                  'labour_cost': cost.get('labour_cost', ''), 'total_cost': cost.get('total_cost', '')}
        listing_images = []
        blockers = []
        if p.get('decision') != 'include':
            blockers.append('Product not selected for listing')
        if p.get('status') != 'reviewed':
            blockers.append('Product review not complete')
        for field in product['fields']:
            f = decision('field', pid, field['key'])
            action = f.get('decision', 'pending')
            effective = priced_listing_value(field, f, cost) or ''
            certainty = f.get('certainty', 'retain')
            calculated_price = field['key'] == 'Price' and action != 'exclude' and cost['pricing_mode'] == 'markup'
            if calculated_price:
                action, certainty = 'calculated', 'estimate'
                if cost['status'] != 'calculated':
                    blockers.append('Complete manufacturing costs for markup pricing')
            # A separate qualification column always preserves the original source claim.
            field_rows.append({'product_id': pid, 'field': field['key'], 'decision': action,
                               'original': field['value'], 'listing_value': effective,
                               'certainty': certainty, 'original_qualification': field['qualification'],
                               'source_basis': field['basis'], 'evidence': (f"Manufacturing cost plus separate labour, with {cost['markup_percent']}% markup; shared rates revision {config_version}." if calculated_price else f.get('evidence', '')), 'notes': f.get('notes', '')})
            output[field['key']] = effective
            if field['key'] == 'Name':
                output['name'] = effective
                if not effective.strip():
                    blockers.append('Product name omitted')
            if field['key'] == 'Family':
                output['family'] = effective
            output[field['key'] + ' qualification'] = (certainty + '; ' + field['qualification']).strip('; ')
            if action == 'pending' and field['section'] != 'Listing copy':
                blockers.append('Review ' + field['label'])
            if action == 'edit' and certainty == 'retain' and field['section'] != 'Listing copy':
                blockers.append('Classify edited ' + field['label'])
            record = lookup.get(('field', pid, field['key']))
            if record and not calculated_price and not field_review_matches_source(record, field, catalogue.source['register_sha256']):
                blockers.append('Source changed since field review: ' + field['label'])
        for aid in view.edges[pid]:
            image = decision('image', pid, aid)
            if view.record('image', pid, aid).get('duplicate_conflicts'):
                blockers.append('Resolve conflicting choices on identical image copies: ' + catalogue.assets[aid]['name'])
            if image.get('decision') == 'reviewed' and 'listing' in image.get('uses', []):
                listing_images.append((not image.get('primary'), image.get('order', 0), aid))
                if image.get('edit_notes', '').strip():
                    blockers.append('Image edit requested: ' + catalogue.assets[aid]['name'])
                if decision('asset', '', aid).get('rights') == 'restricted':
                    blockers.append('Restricted image rights: ' + catalogue.assets[aid]['name'])
                if view.record('asset', '', aid).get('duplicate_conflicts'):
                    blockers.append('Resolve conflicting shared metadata on identical copies: ' + catalogue.assets[aid]['name'])
                if aid not in catalogue.paths and not catalogue.assets[aid].get('url'):
                    blockers.append('Image source unavailable: ' + catalogue.assets[aid]['name'])
                record = lookup.get(('image', pid, aid))
                if record and not image_review_matches_source(view, pid, aid):
                    blockers.append('Source changed since image review: ' + catalogue.assets[aid]['name'])
        if not listing_images:
            blockers.append('Select a listing image')
        if listing_images:
            primary = component_photos(view, pid)['primary_listing']
            if primary['status'] != 'set':
                blockers.append('Resolve the primary listing image selection' if primary['status'] == 'needs_review'
                                else 'Choose the primary listing image')
        # Keep carousel ordering identical to component cards/coverage, including
        # their stable name/ID tie breakers when several photos have order zero.
        output['listing_image_ids'] = component_photos(view, pid)['listing_ids']
        output['ready_for_listing'] = not blockers
        output['review_blockers'] = blockers
        product_rows.append(output)
    names = {p['product_id']: p['name'] for p in product_rows}
    for record in view.reviews:
        if record['kind'] != 'image':
            continue
        pid, aid, review = record['product_id'], record['item_id'], record['data']
        asset = catalogue.assets.get(aid)
        if not asset:
            continue
        meta = decision('asset', '', aid)
        deleted = aid in view.deleted
        attached = not deleted and (pid == '__library__' or aid in view.edges[pid])
        conflicts = record.get('duplicate_conflicts', []) + view.record('asset', '', aid).get('duplicate_conflicts', [])
        uses = review.get('uses', []) if review.get('decision') == 'reviewed' and attached and not conflicts else []
        for use in uses or ['deleted_or_pending_verification' if deleted else 'removed' if not attached else 'conflict' if conflicts else 'excluded' if review.get('decision') == 'exclude' else 'pending']:
            product_name = names.get(pid, 'Image library')
            row = {'product_id': pid, 'product_name': catalogue.products.get(pid, {}).get('name', 'Image library'),
                   'asset_id': aid, 'file_name': asset['name'], 'use': use, 'decision': review.get('decision'),
                   'product_selected_for_listing': decision('product', pid).get('decision') == 'include',
                   'primary': review.get('primary', False), 'order': review.get('order', 0),
                   'tags': meta.get('tags', []), 'collection': meta.get('collection', ''),
                   'rights': meta.get('rights', 'unknown'), 'alt': review.get('alt', ''),
                   'caption': review.get('caption', ''), 'edit_request': review.get('edit_notes', ''),
                   'notes': review.get('notes', ''), 'source': asset['source'], 'source_url': asset['url'],
                   'folder_url': asset['folder_url'], 'source_role': asset['role'],
                   'representation': asset['representation'], 'media_file': '', 'media_sha256': '',
                   'export_status': 'Metadata only', 'types': meta.get('types', view.asset(aid).get('types', [])),
                   'source_asset_ids': view.member_ids(aid), 'association_state': 'attached' if attached else 'removed',
                   'duplicate_conflicts': conflicts, 'original_bytes': asset.get('original', {}).get('bytes'),
                   'original_dimensions': asset.get('original', {}).get('dimensions'),
                   'original_size_basis': asset.get('original', {}).get('dimension_basis'),
                   'dropbox_content_hash': asset.get('original', {}).get('dropbox_content_hash')}
            row['product_name'] = product_name
            allowed_media = use in ('advertising', 'social', 'reference') or (use == 'listing' and row['product_selected_for_listing'])
            if meta.get('rights') == 'restricted' and use in ('listing', 'advertising', 'social'):
                allowed_media = False
                row['export_status'] = 'Media withheld: usage rights marked restricted'
            if include_media and allowed_media:
                if aid in catalogue.paths:
                    path, representation = catalogue.paths[aid]
                    # A cache can disappear after this catalogue snapshot was
                    # built. Preserve the decisions and source link, and keep
                    # exporting other files. Do not swallow output/disk errors.
                    try:
                        source_bytes = Path(path).open('rb')
                    except OSError:
                        row['export_status'] = 'Local media unavailable; source link retained'
                        media_rows.append(row)
                        continue
                    is_preview = 'preview' in representation.lower() or 'thumbnail' in representation.lower()
                    with source_bytes:
                        mime, ext = image_type_from_header(source_bytes.read(IMAGE_HEADER_BYTES))
                        source_bytes.seek(0)
                        # Preview derivatives stay separate from upload originals.
                        destination = root / ('preview-references' if is_preview else 'media') / use / safe_name(row['product_name'])
                        destination.mkdir(parents=True, exist_ok=True)
                        target = destination / (safe_name(asset['name'])[:70] + '-' + hashlib.sha256(aid.encode()).hexdigest()[:10] + ext)
                        with target.open('w+b') as output_file:
                            shutil.copyfileobj(source_bytes, output_file)
                            output_file.flush()
                            copied = copied_identity(output_file)
                        original = asset.get('original', {})
                        expected = {key: original[key] for key in ('sha256', 'dropbox_content_hash') if original.get(key)}
                        if not is_preview and original.get('locally_verified') and (not expected or any(copied[key] != value for key, value in expected.items())):
                            target.unlink()
                            row['export_status'] = 'Local cached bytes changed; source link retained'
                            media_rows.append(row)
                            continue
                        row['media_file'] = str(target.relative_to(root))
                        row['media_sha256'] = copied['sha256']
                    row['export_status'] = 'Preview reference only' if is_preview else 'Cached source copied; verify production resolution'
                else:
                    row['export_status'] = 'Local media unavailable; source link retained'
            media_rows.append(row)
    columns = ['product_id', 'name', 'family', 'listing_decision', 'review_status', 'ready_for_listing', 'review_blockers', 'listing_image_ids', 'notes']
    for p in product_rows:
        for key in p:
            if key not in columns:
                columns.append(key)
    csv_write(root / 'all-product-decisions.csv', columns, product_rows)
    csv_write(root / 'listing-drafts.csv', columns, [p for p in product_rows if p['listing_decision'] == 'include'])
    csv_write(root / 'listing-ready.csv', columns, [p for p in product_rows if p['ready_for_listing']])
    csv_write(root / 'specification-decisions.csv', ['product_id', 'field', 'decision', 'original', 'listing_value', 'certainty', 'original_qualification', 'source_basis', 'evidence', 'notes'], field_rows)
    media_columns = ['product_id', 'product_name', 'asset_id', 'source_asset_ids', 'association_state', 'duplicate_conflicts', 'file_name', 'use', 'decision', 'product_selected_for_listing', 'primary', 'order', 'types', 'tags', 'collection', 'rights', 'alt', 'caption', 'edit_request', 'notes', 'source', 'source_url', 'folder_url', 'source_role', 'representation', 'original_bytes', 'original_dimensions', 'original_size_basis', 'dropbox_content_hash', 'media_file', 'media_sha256', 'export_status']
    csv_write(root / 'image-decisions-and-tags.csv', media_columns, media_rows)
    assets = [{'asset_id': r['item_id'], 'source_asset_ids': view.member_ids(r['item_id']), **r['data']} for r in view.reviews if r['kind'] == 'asset']
    csv_write(root / 'asset-tags.csv', ['asset_id', 'source_asset_ids', 'types', 'tags', 'collection', 'rights', 'notes'], assets)
    assignments = [{'product_id': r['product_id'], 'asset_id': r['item_id'], **r['data']} for r in reviews if r['kind'] == 'assignment']
    csv_write(root / 'image-assignment-changes.csv', ['product_id', 'asset_id', 'state', 'from_product_id', 'to_product_id', 'mode', 'operation_id', 'asset_ids'], assignments)
    duplicate_rows = [{'preferred_asset_id': g['canonical_id'], 'member_asset_ids': g['member_ids'], 'algorithm': g['algorithm'], 'hash': g['hash']} for g in getattr(catalogue, 'duplicate_groups', [])]
    csv_write(root / 'exact-byte-duplicates.csv', ['preferred_asset_id', 'member_asset_ids', 'algorithm', 'hash'], duplicate_rows)
    summary = {'id': export_id, 'products': len(product_rows), 'included': sum(p['listing_decision'] == 'include' for p in product_rows),
               'listing_ready': sum(p['ready_for_listing'] for p in product_rows), 'review_decisions': len(reviews),
               'image_decisions': sum(r['kind'] == 'image' for r in reviews), 'media_rows': len(media_rows),
               'media_included': include_media, 'path': str(root), 'download_url': '/api/exports/' + export_id + '.zip'}
    (root / 'summary.json').write_text(json.dumps(summary, indent=2))
    (root / 'READ-ME.txt').write_text(
        'BOLDSTONE REVIEW BUNDLE\n\nThis is a local review export, not a platform upload.\n'
        'listing-ready.csv includes only selected, completed product reviews with reviewed specification fields and a selected primary image.\n'
        'listing-drafts.csv retains included products with review blockers. Neither file is a certified platform-specific import schema.\n'
        'Markup pricing uses (manufacturing cost + separate labour) x (1 + markup / 100), rounded to pennies. Shared and component overrides are retained in manufacturing-costs.json. Fixed-price source values stay in the specification audit; omitted prices remain omitted.\n'
        'delivery-packages.csv contains saved single-parcel outer box dimensions and gross weights. Recalculate postage against the current tariff when quoting; these are package inputs, not a booked delivery or fixed shipping charge.\n'
        'An unrelated catalogue publication preserves a field review only when its retained source snapshot is identical, and an image review only when original hashes prove unchanged bytes. Missing proof or changed content still needs review.\n'
        'Primary readiness uses the same eligibility check as the app. Missing cached files keep their source links and do not interrupt other exported media.\n'
        'Product exclusions are distinct from image exclusions. Image exclusions apply to the named sculpture only.\n'
        'Shared tags and collections apply to the asset. Library selections use product_id __library__.\n'
        'Schema v2 adds image types, reversible assignment overlays and exact-byte duplicate groups. Original v1 reviews remain in reviews and the SQLite backup.\n'
        'Effective media/listing files contain one preferred image per exact byte group, preferring Dropbox. All source IDs remain in source_asset_ids.\n'
        'Moves remove only the source sculpture association. Target image uses need review. Conflicting duplicate choices are withheld until resolved.\n'
        'Image purposes may overlap: listing, advertising, social and reference. Creating this export does not move or delete originals.\n'
        'Separately confirmed Dropbox file deletions, if any, are recorded as kind=deletion reviews and audit events in the SQLite backup.\n'
        'Deleted or pending-verification display groups are withheld from effective media/listing output; cached bytes and historical source records remain for audit.\n'
        'Media folders contain copies of available local cached sources. Preview references stay in preview-references and are not upload originals.\n'
        'Image editing requests are instructions, not completed pixel edits. Rights fields are reviewer notes, not verification.\n'
        'Listing values do not append provenance labels. Certainty, qualifications and evidence remain in separate columns.\n'
        'Original specification qualifications remain in specification-decisions.csv and original values remain in review-decisions.json.\n')
    zip_path = root.with_suffix('.zip')
    with zipfile.ZipFile(zip_path.with_suffix('.tmp'), 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(root))
    zip_path.with_suffix('.tmp').replace(zip_path)
    return summary
