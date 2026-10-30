#!/usr/bin/env python3
"""Local Boldstone review application: python server.py --open."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import argparse
import json
import mimetypes
import secrets
import threading
import webbrowser
import subprocess
import hashlib

from catalogue import Catalogue
from exports import create_export, image_type
from store import Conflict, ReviewStore, validate
from projection import Projection
from media import TYPES
from deletions import Deletions
from review_coverage import coverage
from live_review import SourceConflict
from dropbox_sync import DropboxSync
from similarity import Similarity
from component_links import payload as component_payload
from component_reviews import save_components
from background_jobs import BackgroundJobs
from filename_overlay import apply_filename_overlay
from specifications import specification_overview
from deletion_reviews import DeletionReviews
from family_inventory import family_inventory, belongs_to_family
from component_overview import component_overview
from source_refresh import refresh_source

HERE = Path(__file__).resolve().parent


class Application:
    def __init__(self, project, data_dir, auto_sync=True):
        self.store = ReviewStore(data_dir)
        self.catalogue_lock = threading.RLock()
        self.catalogue = Catalogue(project, self.store.root)
        # Keep already-open local tabs able to save across a server upgrade.
        token_path = self.store.root / 'server-token'
        if not token_path.exists():
            with token_path.open('x') as stream:
                token_path.chmod(0o600)
                stream.write(secrets.token_urlsafe(32))
        self.token = token_path.read_text().strip()
        if len(self.token) < 32:
            raise ValueError('The local review token is invalid.')
        self.export_lock = threading.Lock()
        self.original_lock = threading.Lock()
        self.deletions = Deletions(self.catalogue, self.store)
        self.sync = DropboxSync(self, enabled=auto_sync)
        self.similarity = Similarity(self.store.root)
        apply_filename_overlay(self.catalogue, self.store.root)
        self.jobs = BackgroundJobs(self)
        self.deletion_reviews = DeletionReviews(self)
        self.deletions.refresh_source = self.refresh_source

    def refresh_source(self):
        return refresh_source(self)

    def projection(self):
        return Projection(self.catalogue, self.store.all())

    def bootstrap(self):
        view = self.projection()
        reviews = view.reviews
        products = []
        lookup = {(r['kind'], r['product_id'], r['item_id']): r for r in reviews}
        for pid, p in self.catalogue.products.items():
            images = view.edges[pid]
            reviewed = sum(('image', pid, aid) in lookup and lookup[('image', pid, aid)]['data'].get('decision') != 'pending' for aid in images)
            state = lookup.get(('product', pid, ''), {'version': 0, 'data': {}})
            name_edit = lookup.get(('field', pid, 'Name'), {}).get('data', {})
            name = name_edit.get('value') if name_edit.get('decision') == 'edit' else p['name']
            products.append({'id': pid, 'name': name, 'original_name': p['name'], 'family': p['family'],
                             'image_count': len(images), 'reviewed_images': reviewed,
                             'primary_id': None if view.cid(p['primary_id']) in view.deleted else p['primary_id'], 'review': state})
        inventory = family_inventory(self.catalogue, view.deleted)
        return {'products': sorted(products, key=lambda x: (x['family'], x['name'])),
                'families': sorted(set(self.catalogue.families) | {f['name'] for f in inventory['image_only_folders']}),
                'family_inventory': inventory,
                'source': self.catalogue.source, 'csrf_token': self.token, 'saved_decisions': len(reviews),
                'data_directory': str(self.store.root), 'history': self.store.history(15), 'image_types': TYPES,
                'assignments': [r for r in reviews if r['kind'] == 'assignment'], 'operations': self.store.operations(),
                'deletions': self.deletions.history(), 'coverage': coverage(view), 'dropbox_sync': self.sync.snapshot()}

    def product(self, pid):
        if pid not in self.catalogue.products:
            if pid in getattr(self.catalogue, 'retired_product_ids', set()):
                raise KeyError('This sculpture has been removed from the active catalogue. Choose another sculpture from the left panel.')
            raise KeyError('Unknown sculpture')
        view = self.projection()
        reviews = view.reviews
        name_edit = view.decision('field', pid, 'Name')
        p = self.catalogue.products[pid]
        if view.cid(p.get('primary_id')) in view.deleted:
            p = {**p, 'original_primary_id': p.get('primary_id'), 'primary_id': None, 'image_url': ''}
        return {**p, 'original_name': p['name'], 'name': name_edit.get('value') if name_edit.get('decision') == 'edit' else p['name'],
                'images': view.images(pid, include_removed=True),
                'reviews': [r for r in reviews if r['product_id'] == pid or r['kind'] == 'asset'],
                'source_hash': self.catalogue.source['register_sha256']}

    def library(self, family=''):
        view = self.projection()
        images = view.library()
        if family:
            inventory = family_inventory(self.catalogue, view.deleted)
            images = [a for a in images if any(belongs_to_family(self.catalogue.assets[member], family, inventory)
                                             for member in view.member_ids(a['id']))]
        ids = {a['id'] for a in images}
        return {'images': images, 'family': family,
                'reviews': [r for r in view.reviews if r['kind'] in ('asset', 'image', 'assignment') and r['item_id'] in ids],
                'dedupe': self.catalogue.source['dedupe']}

    def assign(self, body):
        view = self.projection()
        cat = self.catalogue
        source, target, mode = body.get('from_product_id'), body.get('to_product_id'), body.get('mode')
        ids, versions = body.get('asset_ids'), body.get('versions')
        if mode not in ('move', 'copy', 'remove', 'restore') or not isinstance(ids, list) or not 1 <= len(ids) <= 200:
            raise ValueError('Choose up to 200 images and a valid transfer action.')
        if any(not isinstance(aid, str) or aid not in cat.assets or view.cid(aid) != aid for aid in ids) or len(set(ids)) != len(ids):
            raise ValueError('Unknown or duplicate image IDs.')
        if any(aid in view.deleted for aid in ids):
            raise ValueError('A deleted or pending-deletion image cannot be transferred.')
        if source != '__library__' and source not in cat.products:
            raise ValueError('Choose a source sculpture.')
        if mode in ('move', 'copy') and (target not in cat.products or target == source):
            raise ValueError('Choose a different destination sculpture.')
        if source == '__library__' and mode != 'copy':
            raise ValueError('Library images can be added to a sculpture.')
        if not isinstance(versions, dict):
            raise ValueError('Assignment versions are required; reload the page.')
        changes = []
        for aid in ids:
            if source != '__library__' and aid not in view.edges[source] and not (mode == 'restore' and aid in view.removed[source]):
                raise ValueError('The image is no longer attached to the source sculpture. Reload it.')
            ends = [(target, 'attached')] if mode == 'copy' else [(source, 'removed'), (target, 'attached')] if mode == 'move' else [(source, 'removed' if mode == 'remove' else 'attached')]
            for pid, state in ends:
                version = versions.get(pid, {}).get(aid)
                if type(version) is not int or version < 0:
                    raise ValueError('An assignment version is missing.')
                changes.append({'product_id': pid, 'asset_id': aid, 'version': version,
                                'data': {'state': state, 'from_product_id': source, 'to_product_id': target or '',
                                         'mode': mode, 'asset_ids': view.member_ids(aid)},
                                'original': {'source_product_id': source, 'target_product_id': target,
                                             'source_association': view.edges[source].get(aid), 'source_asset_ids': view.member_ids(aid)}})
        description = mode.capitalize() + ' ' + str(len(ids)) + ' image(s)'
        if source in cat.products:
            description += ' from ' + cat.products[source]['name']
        if target in cat.products:
            description += ' to ' + cat.products[target]['name']
        return self.store.assign(changes, cat.source['register_sha256'], description)

    def original(self, body):
        aid = body.get('asset_id')
        if not self.original_lock.acquire(blocking=False):
            raise Conflict('Another original is being fetched. Try again after it finishes.')
        try:
            with self.catalogue_lock:
                self.refresh_source()
                asset = self.catalogue.assets.get(aid, {})
                native = dict(asset.get('original', {}))
                if asset.get('source') != 'Dropbox' or not native.get('dropbox_content_hash') or not native.get('bytes'):
                    raise ValueError('A Dropbox original with recorded size and content hash is required.')
                if 'expected_content_hash' in body and body['expected_content_hash'] != native['dropbox_content_hash']:
                    raise Conflict('This image changed since you opened it. Reload its photos before fetching the original.')
                view = self.projection()
                if view.cid(aid) in view.deleted:
                    raise Conflict('This original is deleted or awaiting deletion verification; check deletion history.')
                if view.cid(aid) != aid:
                    raise Conflict('This image group changed. Reload its photos before fetching the original.')
                project = self.catalogue.project
            python = project / 'application/.venv/bin/python'
            if not python.is_file():
                raise ValueError('The existing Dropbox runtime is unavailable on this Mac.')
            command = [str(python), str(HERE / 'fetch_original.py'), '--project', str(project),
                       '--data-dir', str(self.store.root), '--file-id', aid,
                       '--content-hash', native['dropbox_content_hash'], '--bytes', str(native['bytes'])]
            # The helper pins the file ID, hash and size and verifies the bytes.
            # Network work must not hold the catalogue lock used by navigation,
            # saved reviews, source refreshes and background-file operations.
            result = subprocess.run(command, capture_output=True, text=True, timeout=100, check=False)
            try:
                info = json.loads(result.stdout)
            except ValueError:
                raise ValueError('The original could not be fetched; saved reviews are unchanged.') from None
            if not isinstance(info, dict):
                raise ValueError('The original download receipt was invalid; saved reviews are unchanged.')
            if result.returncode or info.get('error'):
                raise ValueError(info.get('error', 'Original lookup failed.'))
            if (info.get('file_id') != aid or info.get('dropbox_content_hash') != native['dropbox_content_hash'] or
                    info.get('bytes') != native['bytes'] or not isinstance(info.get('sha256'), str) or
                    len(info['sha256']) != 64 or not isinstance(info.get('checked_utc'), str) or
                    not isinstance(info.get('path'), str) or 'dimensions' not in info):
                raise ValueError('The original download failed receipt verification; saved reviews are unchanged.')
            with self.catalogue_lock:
                self.refresh_source()
                cat = self.catalogue
                current = cat.assets.get(aid, {})
                current_native = current.get('original', {})
                if (current.get('source') != 'Dropbox' or current_native.get('dropbox_content_hash') != native['dropbox_content_hash'] or
                        current_native.get('bytes') != native['bytes']):
                    raise Conflict('This image changed or was removed while its original was downloading. Reload its photos.')
                view = self.projection()
                if view.cid(aid) in view.deleted:
                    raise Conflict('This original was deleted or is awaiting deletion verification. The downloaded preview was not attached.')
                if view.cid(aid) != aid:
                    raise Conflict('This image group changed while downloading. Reload its photos before using the original.')
                for member in cat.duplicate_members.get(aid, [aid]):
                    a = cat.assets.get(member, {})
                    other = a.get('original', {})
                    if (a.get('source') != 'Dropbox' or other.get('dropbox_content_hash') != native['dropbox_content_hash'] or
                            other.get('bytes') != native['bytes']):
                        continue
                    other.update(dimensions=info['dimensions'], bytes=info['bytes'], sha256=info['sha256'],
                                 locally_verified=True, dimension_basis='Dropbox original downloaded and byte-verified on ' + info['checked_utc'][:10])
                    cat.paths[member] = (Path(info['path']), 'verified Dropbox original')
                    a.update(local_preview=True, representation='verified Dropbox original', cached_file=info)
                cat.source['dedupe']['original_dimensions_known'] = sum(bool(a.get('original', {}).get('dimensions')) for a in cat.assets.values())
                return {'asset': self.projection().asset(aid)}
        except subprocess.TimeoutExpired:
            raise ValueError('Original download timed out. Try again; saved reviews are unchanged.') from None
        finally:
            self.original_lock.release()

    def save(self, body):
        kind, pid, item = body.get('kind'), body.get('product_id', ''), body.get('item_id', '')
        submitted = body.get('data')
        if isinstance(submitted, dict):
            submitted = submitted.copy()
            if kind == 'image':
                # Quick/bulk saves echo the last response, including this
                # server-owned provenance field. Recompute it below rather
                # than accepting a client value or rejecting the next click.
                submitted.pop('reviewed_content_hash', None)
        data = validate(kind, submitted)
        if type(body.get('version')) is not int or body['version'] < 0:
            raise ValueError('A review version is required.')
        cat = self.catalogue
        view = self.projection()
        if kind in ('image', 'asset') and 'expected_content_hash' in body:
            native = cat.assets.get(item, {}).get('original', {})
            if body['expected_content_hash'] != (native.get('dropbox_content_hash') or native.get('sha256')):
                raise Conflict('This image changed since you opened it. Reload its photos before saving.')
        if kind == 'product':
            if pid not in cat.products or item:
                raise ValueError('Unknown sculpture')
            original = {k: cat.products[pid][k] for k in ('id', 'name', 'family')}
        elif kind == 'field':
            if pid not in cat.products or item not in cat.fields(pid):
                raise ValueError('Unknown specification')
            original = cat.fields(pid)[item]
        elif kind == 'image':
            if item not in cat.assets or view.cid(item) != item or (pid != '__library__' and item not in view.edges.get(pid, {})):
                raise ValueError('This image has no retained association with that sculpture.')
            if pid == '__library__' and ('listing' in data.get('uses', []) or data.get('primary')):
                raise ValueError('Choose a sculpture before assigning a listing image.')
            original = {'asset': cat.assets[item], 'association': view.edges.get(pid, {}).get(item)}
        elif kind == 'asset':
            if pid or item not in cat.assets or view.cid(item) != item:
                raise ValueError('Unknown image')
            original = cat.assets[item]
        else:
            raise ValueError('Unknown review type')
        if kind in ('image', 'asset') and view.cid(item) in view.deleted:
            raise Conflict('This original is deleted or awaiting deletion verification; check deletion history.')
        if kind == 'image' and cat.assets[item].get('live_synced'):
            data['reviewed_content_hash'] = cat.assets[item].get('original', {}).get('dropbox_content_hash')
        versions = None
        if kind in ('image', 'asset'):
            versions = body.get('member_versions') or {aid: 0 for aid in view.member_ids(item)}
            if set(versions) != set(view.member_ids(item)) or any(type(v) is not int or v < 0 for v in versions.values()):
                raise ValueError('Duplicate review versions are invalid; reload this image.')
            versions[item] = body['version']
        self.store.save(kind, pid, item, data, body['version'], cat.source['register_sha256'], original, versions)
        return self.projection().record(kind, pid, item)


class Handler(BaseHTTPRequestHandler):
    server_version = 'BoldstoneReview/2.14.12'

    @property
    def app(self):
        return self.server.app

    def log_message(self, format, *args):
        if len(args)>1 and str(args[1]) in ('200', '304'):
            return
        try:
            super().log_message(format, *args)
        except Exception:
            pass  # Logging must not discard an already committed response.

    @staticmethod
    def log_exception():
        import traceback
        try:
            traceback.print_exc()
        except Exception:
            pass

    def headers_ok(self, write=False):
        host = self.headers.get('Host', '')
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        if host not in allowed:
            return False
        if write:
            origin = self.headers.get('Origin')
            if origin and origin not in {'http://' + x for x in allowed}:
                return False
            if not secrets.compare_digest(self.headers.get('X-Review-Token', ''), self.app.token):
                return False
        return True

    def send(self, payload, status=200, mime='application/json', disposition=None):
        data = json.dumps(payload, ensure_ascii=False).encode() if mime == 'application/json' else payload
        self.send_response(status)
        self.send_header('Content-Type', mime + ('; charset=utf-8' if mime.startswith('text/') else ''))
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store' if not mime.startswith('image/') else 'private, max-age=600')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' https://images.squarespace-cdn.com https://cdn.shopify.com data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        if disposition:
            self.send_header('Content-Disposition', disposition)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        with self.app.catalogue_lock:
            self.get_response()

    def get_response(self):
        if not self.headers_ok():
            return self.send({'error': 'Local access only'}, 403)
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            if (path in ('/api/bootstrap', '/api/dropbox-sync', '/api/library', '/api/specifications', '/api/coverage', '/api/image-components')
                or path.startswith(('/api/products/', '/api/component-overview/'))) and hasattr(self.app, 'refresh_source'):
                self.app.refresh_source()
            if path == '/api/bootstrap':
                return self.send(self.app.bootstrap())
            if path == '/api/dropbox-sync':
                return self.send(self.app.sync.snapshot())
            if path == '/api/jobs':
                return self.send(self.app.jobs.snapshot(include_dismissed=parse_qs(parsed.query).get('include_dismissed') == ['1']))
            if path == '/api/deletions/history':
                return self.send(self.app.deletions.history())
            if path.startswith('/api/products/'):
                return self.send(self.app.product(path.split('/')[-1]))
            if path == '/api/library':
                return self.send(self.app.library(parse_qs(parsed.query).get('family', [''])[0]))
            if path == '/api/specifications':
                view = self.app.projection()
                photos = {pid: p['photos'] for pid, p in coverage(view, include_photos=True)['products'].items()}
                result = specification_overview(self.app.catalogue, view.reviews, photos)
                result['family_inventory'] = family_inventory(self.app.catalogue)
                result['revision'] = hashlib.sha256((result['revision'] + json.dumps(
                    result['family_inventory'], sort_keys=True)).encode()).hexdigest()
                return self.send(result)
            if path.startswith('/api/component-overview/'):
                return self.send(component_overview(self.app.projection(), path.split('/')[-1]))
            if path.startswith('/api/deletion-reviews/'):
                return self.send(self.app.deletion_reviews.get(path.split('/')[-1], plans=True))
            if path == '/api/image-components':
                return self.send(component_payload(self.app.projection(), parse_qs(parsed.query).get('id', [''])[0]))
            if path.startswith('/api/similarity/'):
                return self.send(self.app.similarity.status(path.split('/')[-1]))
            if path == '/api/coverage':
                return self.send(coverage(self.app.projection()))
            if path == '/api/history':
                return self.send(self.app.store.history())
            if path == '/api/health':
                return self.send({'status': 'ok', 'application': 'boldstone-review', 'version': '2.14.12', 'products': len(self.app.catalogue.products)})
            if path == '/api/image':
                aid = parse_qs(parsed.query).get('id', [''])[0]
                if aid not in self.app.catalogue.paths:
                    return self.send({'error': 'No local preview. Use the source link.'}, 404)
                file, representation = self.app.catalogue.paths[aid]
                if parse_qs(parsed.query).get('size') == ['thumb']:
                    file = self.app.catalogue.preview_paths.get(aid, file)
                mime, ext = image_type(file)
                if mime == 'application/octet-stream':
                    return self.send({'error': 'This cached file is not a browser image.'}, 415)
                return self.send(file.read_bytes(), mime=mime)
            if path.startswith('/api/exports/'):
                name = path.split('/')[-1]
                import re
                if not re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{8}\.zip', name):
                    raise KeyError('Unknown export')
                target = self.app.store.root / 'exports' / name
                return self.send(target.read_bytes(), mime='application/zip', disposition='attachment; filename="Boldstone-review-' + name + '"')
            if path in ('/', '/index.html', '/app.js', '/image-tools.js', '/delete-tools.js', '/bulk-delete.js', '/family-tools.js', '/sync-tools.js', '/sort-core.js', '/sort-tools.js', '/component-tools.js', '/component-overview.js', '/jobs.js', '/specifications.js', '/style.css'):
                target = HERE / 'static' / ('index.html' if path == '/' else path[1:])
                return self.send(target.read_bytes(), mime=mimetypes.guess_type(target)[0] or 'text/plain')
            raise KeyError('Not found')
        except SourceConflict as e:
            self.send({'error': str(e)}, 409)
        except ValueError as e:
            self.send({'error': str(e)}, 400)
        except (KeyError, FileNotFoundError) as e:
            self.send({'error': str(e)}, 404)
        except Exception:
            self.log_exception()
            self.send({'error': 'Current app data is temporarily unavailable. Please try again.',
                       'retryable': True}, 503)

    def do_POST(self):
        # Native inspections and explicit recovery may wait on Dropbox. They
        # must not freeze gallery reads or unrelated saved review choices.
        if self.path in ('/api/deletions/prepare', '/api/deletions/check', '/api/jobs/check', '/api/jobs/resume-rename', '/api/original'):
            return self.post_response()
        with self.app.catalogue_lock:
            self.post_response()

    def post_response(self):
        if not self.headers_ok(write=True):
            return self.send({'error': 'Invalid local review session. Reload the page.'}, 403)
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('JSON is required')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length < 512_000:
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Invalid request')
            if self.path not in ('/api/deletions/check', '/api/jobs/check', '/api/jobs/cancel', '/api/jobs/dismiss', '/api/jobs/restore', '/api/jobs/clear-finished', '/api/original') and hasattr(self.app, 'refresh_source'):
                self.app.refresh_source()
            if self.path in ('/api/jobs/dismiss', '/api/jobs/restore'):
                return self.send(self.app.jobs.dismiss(body.get('job_id'), body.get('updated_at'), restore=self.path.endswith('/restore')))
            if self.path == '/api/jobs/clear-finished':
                return self.send(self.app.jobs.clear_finished())
            if self.path == '/api/similarity':
                return self.send(self.app.similarity.start(body, self.app.projection()))
            if self.path == '/api/image-components':
                return self.send(save_components(self.app, body))
            if self.path == '/api/reviews':
                return self.send(self.app.save(body))
            if self.path == '/api/dropbox-sync':
                return self.send(self.app.sync.request())
            if self.path == '/api/assignments':
                return self.send(self.app.assign(body))
            if self.path == '/api/assignments/undo':
                return self.send(self.app.store.undo_assignment(body.get('operation_id'), self.app.catalogue.source['register_sha256']))
            if self.path == '/api/original':
                return self.send(self.app.original(body))
            if self.path == '/api/deletions/prepare':
                return self.send(self.app.deletions.prepare(body))
            if self.path == '/api/deletion-reviews':
                return self.send(self.app.deletion_reviews.start_review(body), 202)
            if self.path == '/api/deletion-reviews/retry':
                return self.send(self.app.deletion_reviews.retry(body.get('review_id')), 202)
            if self.path == '/api/deletion-reviews/plan':
                return self.send(self.app.deletion_reviews.plan(body.get('review_id')))
            if self.path == '/api/deletion-reviews/cancel':
                return self.send(self.app.deletion_reviews.cancel(body.get('review_id')))
            if self.path == '/api/deletions/prepare-batch':
                return self.send(self.app.deletions.prepare_batch(body))
            if self.path == '/api/deletions/execute-batch':
                job = self.app.jobs.enqueue_deletion(body, batch=True)
                if hasattr(self.app, 'deletion_reviews'):
                    self.app.deletion_reviews.submitted(body.get('batch_id'))
                return self.send(job, 202)
            if self.path == '/api/deletions/batch-status':
                return self.send(self.app.deletions.batch_status(body))
            if self.path == '/api/deletions/execute':
                return self.send(self.app.jobs.enqueue_deletion(body), 202)
            if self.path == '/api/jobs/check':
                return self.send(self.app.jobs.check(body.get('job_id')))
            if self.path == '/api/jobs/review-remaining':
                return self.send(self.app.jobs.review_remaining(body.get('job_id')), 202)
            if self.path == '/api/jobs/cancel':
                return self.send(self.app.jobs.cancel(body.get('job_id')))
            if self.path == '/api/jobs/replan':
                return self.send(self.app.jobs.replan(body.get('job_id')), 202)
            if self.path == '/api/jobs/resume-rename':
                return self.send(self.app.jobs.resume_rename(body.get('job_id')), 202)
            if self.path == '/api/deletions/check':
                return self.send(self.app.jobs.check_deletion(body.get('operation_id')))
            if self.path == '/api/export':
                if not self.app.export_lock.acquire(blocking=False):
                    return self.send({'error': 'An export is already running.'}, 409)
                try:
                    return self.send(create_export(self.app.catalogue, self.app.store, body.get('include_media') is True))
                finally:
                    self.app.export_lock.release()
            self.send({'error': 'Not found'}, 404)
        except (Conflict, SourceConflict) as e:
            self.send({'error': str(e), **getattr(e, 'details', {})}, 409)
        except (ValueError, KeyError, TypeError) as e:
            self.send({'error': str(e)}, 400)
        except Exception:
            self.log_exception()
            message = ('The deletion result could not be confirmed. Open Deletion history and check status before any retry.'
                       if self.path.startswith('/api/deletions/') else
                       'The job response could not be confirmed. Open Jobs to check its saved status before retrying.'
                       if self.path.startswith(('/api/jobs/', '/api/deletion-reviews')) else
                       'Could not confirm the saved result. Reload the current item before retrying.')
            self.send({'error': message}, 500)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, default=HERE.parent)
    parser.add_argument('--data-dir', type=Path, default=Path.home() / 'Library/Application Support/BoldstoneReview')
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--open', action='store_true')
    parser.add_argument('--no-auto-sync', action='store_true', help='Disable Dropbox polling for isolated tests.')
    args = parser.parse_args()
    app = Application(args.project, args.data_dir, auto_sync=not args.no_auto_sync)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.daemon_threads = True
    server.app = app
    app.sync.start()
    app.jobs.start()
    app.deletion_reviews.start()
    url = f'http://127.0.0.1:{server.server_port}'
    print(json.dumps({'url': url, 'data_dir': str(app.store.root), **app.catalogue.source}), flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.sync.stop()
        app.jobs.stop()
        app.deletion_reviews.stop()
        server.server_close()


if __name__ == '__main__':
    main()
