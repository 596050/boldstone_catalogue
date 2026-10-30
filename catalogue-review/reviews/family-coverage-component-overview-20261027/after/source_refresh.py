"""Replace a stale canonical source atomically; saved reviews and jobs stay put."""
from pathlib import Path
import json

from catalogue import Catalogue
from dropbox_sync import apply_inventory
from filename_overlay import apply_filename_overlay
from live_review import check_sources, SourceConflict


def identity(source):
    return (str(Path(source['register']).resolve()), source['register_sha256'],
            str(Path(source['gallery_database']).resolve()))


def published_identity(project):
    base = Path(project) / 'sculpture-catalogue'
    pointer = json.loads((base / 'current-master.json').read_text())
    return (str((base / pointer['register']).resolve()), pointer['register_sha256'],
            str(((base / pointer['current_published_gallery_projection']['path']).parent /
                 'complete-image-platform-register.sqlite').resolve()))


def refresh_source(app):
    with app.catalogue_lock:
        # Build and check everything before changing either the active catalogue
        # or the baseline used by the next Dropbox scan. Failed publications
        # cannot replace the working view or authorize a native mutation.
        try:
            if published_identity(app.catalogue.project) == identity(app.catalogue.source):
                return False
            base = Catalogue(app.catalogue.project, app.store.root)
            state = getattr(app.sync, 'inventory_state', None)
            cat = apply_inventory(base, state, app.store.root) if state else base
            apply_filename_overlay(cat, app.store.root, state['checked_utc'] if state else None)
            if getattr(app, 'jobs', None):
                app.jobs.overlay_locations(cat, state['checked_utc'] if state else None)
            check_sources(cat)
        except (ValueError, KeyError, OSError) as exc:
            raise SourceConflict('The new catalogue could not be verified yet. Saved reviews and jobs are retained; retry when publication finishes.') from exc
        app.sync.base = base
        app.catalogue = cat
        app.deletions.cat = cat
        return True
