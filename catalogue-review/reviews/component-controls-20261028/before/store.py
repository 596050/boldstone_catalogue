"""Durable, versioned review decisions. No writes to source catalogue or assets."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import uuid
from media import TYPES


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(Exception):
    pass


class ReviewStore:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self.path = self.root / 'reviews.sqlite3'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS reviews(
                    kind TEXT NOT NULL, product_id TEXT NOT NULL, item_id TEXT NOT NULL,
                    version INTEGER NOT NULL, data TEXT NOT NULL, source_hash TEXT NOT NULL,
                    original TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(kind,product_id,item_id));
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                    kind TEXT NOT NULL, product_id TEXT NOT NULL, item_id TEXT NOT NULL,
                    before_json TEXT, after_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS operations(
                    id TEXT PRIMARY KEY, at TEXT NOT NULL, details TEXT NOT NULL,
                    undone INTEGER NOT NULL DEFAULT 0);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def unpack(row):
        if not row:
            return {'version': 0, 'data': {}}
        out = dict(row)
        out['data'] = json.loads(out['data'])
        out['original'] = json.loads(out['original'])
        return out

    def get(self, kind, pid='', item=''):
        with self.connect() as db:
            return self.unpack(db.execute('SELECT * FROM reviews WHERE kind=? AND product_id=? AND item_id=?', (kind, pid, item)).fetchone())

    def all(self):
        with self.connect() as db:
            return [self.unpack(x) for x in db.execute('SELECT * FROM reviews ORDER BY updated_at')]

    def snapshot(self):
        """One committed view, including the event cutoff and transfer provenance."""
        with self.connect() as db:
            db.execute('BEGIN')
            cutoff = db.execute('SELECT COALESCE(MAX(id), 0) FROM events').fetchone()[0]
            reviews = [self.unpack(x) for x in db.execute(
                'SELECT * FROM reviews ORDER BY updated_at,kind,product_id,item_id')]
            operations = [{**dict(r), 'details': json.loads(r['details']), 'undone': bool(r['undone'])}
                          for r in db.execute('SELECT * FROM operations ORDER BY at,id')]
        return {'database': str(self.path), 'event_cutoff': cutoff,
                'reviews': reviews, 'operations': operations}

    def save(self, kind, pid, item, data, expected_version, source_hash, original, member_versions=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT * FROM reviews WHERE kind=? AND product_id=? AND item_id=?', (kind, pid, item)).fetchone()
            before = self.unpack(previous)
            if before['version'] != expected_version:
                raise Conflict('This item changed in another tab. Reload it before saving your changes.')
            members = member_versions or {item: expected_version}
            for aid, version in members.items():
                old = self.unpack(db.execute('SELECT * FROM reviews WHERE kind=? AND product_id=? AND item_id=?', (kind, pid, aid)).fetchone())
                if old['version'] != version:
                    raise Conflict('An identical copy changed in another tab. Reload before saving.')
            # A primary image is unique per sculpture, and always a listing selection.
            if kind == 'image' and data.get('primary'):
                for row in db.execute("SELECT * FROM reviews WHERE kind='image' AND product_id=?", (pid,)).fetchall():
                    value = json.loads(row['data'])
                    if row['item_id'] not in members and value.get('primary'):
                        old = self.unpack(row)
                        value['primary'] = False
                        self._write(db, 'image', pid, row['item_id'], value, old['version'] + 1, source_hash, old['original'], old)
            self._write(db, kind, pid, item, data, before['version'] + 1, source_hash,
                        before.get('original', original), before if previous else None)
            # Updating the displayed image explicitly reconciles prior reviews on its
            # byte-identical aliases. Old values stay in the audit log and backups.
            for aid in members:
                if aid == item:
                    continue
                old = self.unpack(db.execute('SELECT * FROM reviews WHERE kind=? AND product_id=? AND item_id=?', (kind, pid, aid)).fetchone())
                if old['version']:
                    self._write(db, kind, pid, aid, data, old['version'] + 1, source_hash, old['original'], old)
        return self.get(kind, pid, item)

    def save_component_reviews(self, changes, source_hash):
        """All selected components save together; an alias conflict rolls all back."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prepared = []
            for change in changes:
                kind, pid, aid = change['kind'], change['product_id'], change['item_id']
                if kind not in ('image', 'assignment'):
                    raise ValueError('Invalid component review kind.')
                old_rows = {}
                for member, version in change['member_versions'].items():
                    old = self.unpack(db.execute('SELECT * FROM reviews WHERE kind=? AND product_id=? AND item_id=?',
                                                (kind, pid, member)).fetchone())
                    if old['version'] != version:
                        raise Conflict('A component or identical copy changed in another tab. Reopen the chooser.')
                    old_rows[member] = old
                if aid not in old_rows or old_rows[aid]['version'] != change['version']:
                    raise Conflict('The component review version changed.')
                prepared.append((change, old_rows))
            for change, old_rows in prepared:
                for member, old in old_rows.items():
                    if member != change['item_id'] and not old['version']:
                        continue
                    self._write(db, change['kind'], change['product_id'], member, change['data'], old['version'] + 1,
                                source_hash, old.get('original', change['original']), old if old['version'] else None)

    def assign(self, changes, source_hash, description):
        """Apply all ends of a move/copy atomically; never alter files or image uses."""
        operation_id = uuid.uuid4().hex
        receipt = []
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for change in changes:
                pid, aid = change['product_id'], change['asset_id']
                row = db.execute("SELECT * FROM reviews WHERE kind='assignment' AND product_id=? AND item_id=?", (pid, aid)).fetchone()
                old = self.unpack(row)
                if old['version'] != change['version']:
                    raise Conflict('An image assignment changed in another tab. Reload before moving it.')
                receipt.append({'product_id': pid, 'asset_id': aid, 'before': old,
                                'after_version': old['version'] + 1,
                                'after_data': {**change['data'], 'operation_id': operation_id}})
            for change, item in zip(changes, receipt):
                value = {**change['data'], 'operation_id': operation_id}
                self._write(db, 'assignment', change['product_id'], change['asset_id'], value, item['after_version'],
                            source_hash, item['before'].get('original', change.get('original', {})), item['before'])
            db.execute('INSERT INTO operations(id,at,details) VALUES(?,?,?)',
                       (operation_id, now(), json.dumps({'description': description, 'changes': receipt})))
        return {'operation_id': operation_id, 'description': description, 'changed_assignments': len(changes)}

    def undo_assignment(self, operation_id, source_hash):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM operations WHERE id=?', (operation_id,)).fetchone()
            if not row or row['undone']:
                raise ValueError('This transfer is unavailable or has already been undone.')
            details = json.loads(row['details'])
            for item in details['changes']:
                current = self.unpack(db.execute("SELECT * FROM reviews WHERE kind='assignment' AND product_id=? AND item_id=?", (item['product_id'], item['asset_id'])).fetchone())
                if current['version'] != item['after_version'] and current['data'] != item.get('after_data'):
                    raise Conflict('A later assignment changed one of these images. Undo that later change first.')
            for item in details['changes']:
                pid, aid = item['product_id'], item['asset_id']
                current = self.unpack(db.execute("SELECT * FROM reviews WHERE kind='assignment' AND product_id=? AND item_id=?", (pid, aid)).fetchone())
                value = item['before'].get('data') or {'state': 'source'}
                self._write(db, 'assignment', pid, aid, value, current['version'] + 1, source_hash, current['original'], current)
            db.execute('UPDATE operations SET undone=1 WHERE id=?', (operation_id,))
        return {'undone': operation_id}

    def operations(self):
        with self.connect() as db:
            return [{'id': r['id'], 'at': r['at'], 'undone': bool(r['undone']),
                     'description': json.loads(r['details'])['description']}
                    for r in db.execute('SELECT * FROM operations ORDER BY at DESC LIMIT 30')]

    def _write(self, db, kind, pid, item, data, version, source_hash, original, before):
        stamp = now()
        after = {'kind': kind, 'product_id': pid, 'item_id': item, 'data': data, 'version': version,
                 'source_hash': source_hash, 'original': original, 'updated_at': stamp}
        db.execute('INSERT OR REPLACE INTO reviews VALUES(?,?,?,?,?,?,?,?)',
                   (kind, pid, item, version, json.dumps(data), source_hash, json.dumps(original), stamp))
        db.execute('INSERT INTO events(at,kind,product_id,item_id,before_json,after_json) VALUES(?,?,?,?,?,?)',
                   (stamp, kind, pid, item, json.dumps(before) if before else None, json.dumps(after)))
        # Durable outbox: native organisation is queued in the same transaction
        # as the user's choice. No network call runs inside this transaction.
        hook = getattr(self, 'review_hook', None)
        if hook:
            hook(db, after, before or {}, db.execute('SELECT last_insert_rowid()').fetchone()[0])

    def backup(self, destination):
        with self.connect() as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)

    def history(self, limit=60):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT id,at,kind,product_id,item_id FROM events ORDER BY id DESC LIMIT ?', (limit,))]


def validate(kind, data):
    if not isinstance(data, dict):
        raise ValueError('A review must be an object.')
    allowed = {
        'product': {'decision', 'status', 'notes'},
        'field': {'decision', 'value', 'notes', 'evidence', 'certainty'},
        'image': {'decision', 'uses', 'primary', 'alt', 'caption', 'notes', 'edit_notes', 'order'},
        'asset': {'tags', 'types', 'notes', 'rights', 'collection'},
    }
    if kind not in allowed or set(data) - allowed[kind]:
        raise ValueError('Unknown review field.')
    for k, v in data.items():
        if k in ('uses', 'tags', 'types'):
            if not isinstance(v, list) or len(v) > 30 or any(not isinstance(x, str) or not x.strip() or len(x) > 80 for x in v):
                raise ValueError('Use up to 30 non-empty tags or uses.')
        elif k == 'primary':
            if not isinstance(v, bool):
                raise ValueError('Primary must be a boolean.')
        elif k == 'order':
            if type(v) is not int or not 0 <= v <= 10000:
                raise ValueError('Image order must be 0–10000.')
        elif not isinstance(v, str) or len(v) > 20000:
            raise ValueError('Review text is too long or invalid.')
    choices = {'product': {'decision': ['pending', 'include', 'exclude'], 'status': ['unreviewed', 'in_progress', 'reviewed']},
               'field': {'decision': ['pending', 'keep', 'edit', 'exclude'], 'certainty': ['retain', 'estimate', 'source_claim', 'confirmed']},
               'image': {'decision': ['pending', 'reviewed', 'exclude']},
               'asset': {'rights': ['unknown', 'owned', 'permission', 'restricted']}}
    for k, values in choices[kind].items():
        if k in data and data[k] not in values:
            raise ValueError('Invalid ' + k)
    if kind == 'field':
        if data.get('decision') == 'edit' and not data.get('value', '').strip():
            raise ValueError('Enter the replacement value before choosing Edited.')
        if data.get('certainty') == 'confirmed' and not data.get('evidence', '').strip():
            raise ValueError('Record the evidence before marking a specification confirmed.')
    if kind == 'image':
        uses = data.get('uses', [])
        if set(uses) - {'listing', 'advertising', 'social', 'reference'}:
            raise ValueError('Unknown image use.')
        if data.get('decision') == 'exclude':
            data['uses'] = []
            data['primary'] = False
        if data.get('primary') and ('listing' not in data.get('uses', []) or data.get('decision') != 'reviewed'):
            raise ValueError('A primary image must be reviewed and selected for the listing.')
    if kind == 'asset' and set(data.get('types', [])) - set(TYPES):
        raise ValueError('Unknown image type.')
    return data
