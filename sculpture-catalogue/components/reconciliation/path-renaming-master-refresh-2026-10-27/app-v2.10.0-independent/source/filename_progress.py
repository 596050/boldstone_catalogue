"""Read-only progress for the external filename writer, from its existing journals.

Never contacts Dropbox, launches a worker, changes the writer reservation or
counts a submitted move as verified. Large inventory counts are cached by file
identity; each status request only refreshes small receipts and elapsed times.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import time

IMMUTABLE = ('id', 'parent_id', 'size', 'content_hash', 'client_modified',
             'has_explicit_shared_members', 'sharing_info_present', 'read_only',
             'parent_shared_folder_id', 'file_lock_present')


def read(path):
    return json.loads(path.read_text()) if path.is_file() else None


def stamp(path):
    stat = path.stat()
    return str(path), stat.st_mtime_ns, stat.st_size


def seconds_since(value, clock):
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return max(0, int(clock - date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp()))
    except (ValueError, TypeError):
        return None


class FilenameProgress:
    def __init__(self, runtime):
        self.runtime = Path(runtime)
        self.count_key = self.counts = None

    def read(self, clock=None):
        try:
            reservation = read(self.runtime / 'native-writer-reservation.json')
            if not reservation or reservation.get('label') != 'Dropbox filename renaming' or not reservation.get('root'):
                return None
            return self.snapshot(reservation, time.time() if clock is None else clock)
        except (OSError, ValueError, KeyError, TypeError):
            return {'state': 'unavailable', 'stage': 'Progress temporarily unavailable',
                    'message': 'The saved progress could not be read. The existing filename job and queue are unchanged.'}

    def count(self, manifest_path, inventory_path=None, expected_hash=None):
        key = (stamp(manifest_path), stamp(inventory_path) if inventory_path else None, expected_hash)
        if key == self.count_key:
            return dict(self.counts)
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
        digest = hashlib.sha256(raw).hexdigest()
        groups = manifest['groups']
        total = sum(len(g['files']) for g in groups)
        if total != manifest['counts']['files']:
            raise ValueError('Manifest file count differs')
        correct = deferred = deferred_files = 0
        checked_at = manifest['created_at']
        if inventory_path:
            raw = inventory_path.read_bytes()
            if expected_hash and hashlib.sha256(raw).hexdigest() != expected_hash:
                raise ValueError('Inventory receipt does not match')
            inventory = json.loads(raw)
            if not all(inventory[k].get('pagination_exhausted') for k in ('wall', 'workshop')):
                raise ValueError('Incomplete inventory')
            checked_at = inventory['recorded_utc']
            rows = inventory['wall']['entries'] + inventory['workshop']['entries']
            current = {r['id']: r for r in rows}
            parents = {}
            for row in rows:
                if row['kind'] == 'file':
                    parents.setdefault(row['parent_id'], {})[row['id']] = row
            for group in groups:
                parent, expected = group['parent'], group['files']
                folder = current.get(parent['id'])
                actual = parents.get(parent['id'], {})
                same_folder = folder and folder['path'].casefold() == parent['path'].casefold() and folder['name'] == parent['name']
                unchanged = same_folder and set(actual) == {r['id'] for r in expected}
                if unchanged:
                    for old in expected:
                        new = actual[old['id']]
                        allowed = {p.casefold() for p in (old['path'], old['new_path'], old.get('temporary_path')) if p}
                        if any(old.get(k) != new.get(k) for k in IMMUTABLE) or new['path'].casefold() not in allowed:
                            unchanged = False
                            break
                if not unchanged:
                    deferred += 1; deferred_files += len(expected)
                    continue
                correct += sum(actual[r['id']]['name'] == r['new_name'] and
                               actual[r['id']]['path'].casefold() == r['new_path'].casefold() for r in expected)
        else:
            correct = sum(r['name'] == r['new_name'] and r['path'].casefold() == r['new_path'].casefold()
                          for g in groups for r in g['files'])
        self.count_key = key
        self.counts = {'correct': correct, 'total': total, 'deferred_folders': deferred,
                       'deferred_files': deferred_files, 'checked_at': checked_at,
                       'manifest_sha256': digest, 'planned_renames': manifest['counts']['renames']}
        return dict(self.counts)

    def snapshot(self, reservation, clock):
        root = Path(reservation['root'])
        passes = [root] + sorted(p for p in root.glob('followup-*') if p.is_dir() and (p / 'manifest.json').exists())
        current = passes[-1]
        batches = sorted(p for p in (current / 'bulk-operations').glob('*') if p.is_dir() and p.name.isdigit())
        latest = batches[-1] if batches else None
        intent = read(latest / 'intent.json') if latest else None
        submission = read(latest / 'submission.json') if latest else None
        terminal = read(latest / 'terminal.json') if latest else None
        verified = read(latest / 'verified.json') if latest else None
        snapshots = []
        for batch in batches:
            before, after = batch / 'before.json', batch / 'after.json'
            if before.exists():
                bound = read(batch / 'intent.json') or {}
                snapshots.append((before, bound.get('before_sha256')))
            proof = read(batch / 'verified.json')
            if after.exists() and proof:
                snapshots.append((after, proof.get('after_sha256')))
        inventory, digest = max(snapshots, key=lambda item: item[0].stat().st_mtime_ns) if snapshots else (None, None)
        counts = self.count(current / 'manifest.json', inventory, digest)
        for receipt in (intent, verified):
            if receipt and receipt.get('manifest_sha256') != counts['manifest_sha256']:
                raise ValueError('Receipt is for another manifest')
        out = {**counts, 'pass_name': 'Original pass' if current == root else 'Follow-up ' + str(int(current.name.split('-')[-1])),
               'state': 'running', 'stage': 'Preparing the next batch',
               'batch_number': int(latest.name) if latest else None,
               'batch_files': len(intent['moves']) if intent else 0,
               'batch_state': 'verified' if verified else 'checking' if terminal else 'processing' if submission and submission.get('async_job_id') else 'submitting',
               'batch_started_at': (submission or intent or {}).get('at'),
               'message': 'Counts advance after Dropbox finishes a batch and its filenames are checked.'}
        if intent and not verified:
            if terminal:
                out['stage'] = 'Checking the completed batch'
            elif submission and submission.get('async_job_id'):
                out['stage'] = 'Dropbox is processing the current batch'
            elif submission and submission.get('error_type'):
                out.update(state='needs_review', stage='Batch submission needs checking')
            else:
                out['stage'] = 'Waiting for the batch submission result'
        if (current / 'batch-pass-complete.json').exists() or counts['planned_renames'] == 0:
            out['stage'] = 'Checking remaining folders and final filenames'
        proof_path = root / 'verification.json'
        pointer = read(root / 'verification-current.json')
        if pointer:
            proof_path = Path(pointer['path'])
            if not proof_path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Verification receipt is outside this job')
            raw = proof_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != pointer['sha256']:
                raise ValueError('Verification receipt does not match')
            proof = json.loads(raw)
        else:
            proof = read(proof_path)
        completion = read(root / 'completion.json')
        out['final_checks'] = 'pending'
        if proof and proof.get('status') == 'PASS':
            out.update(correct=proof['current_files'], total=proof['current_files'], checked_at=proof['at'],
                       deferred_folders=0, deferred_files=0, stage='Refreshing the app with verified filenames',
                       pass_name='Final verification', batch_number=None, batch_files=0, batch_started_at=None,
                       final_checks='passed')
        if completion and proof and proof.get('status') == 'PASS' and not reservation.get('active'):
            if completion.get('verification') and Path(completion['verification']).resolve() != proof_path.resolve():
                raise ValueError('Completion belongs to another verification')
            if completion.get('verification_sha256') and hashlib.sha256(proof_path.read_bytes()).hexdigest() != completion['verification_sha256']:
                raise ValueError('Completion verification has changed')
            out.update(state='completed', stage='Filename renaming complete', completed_at=completion['at'],
                       message='All retained filenames were verified and the app refreshed. Queued file jobs can now run.')
        error = read(root / 'completion-error-current.json') or read(root / 'completion-error.json')
        if error and error.get('at', '') >= reservation.get('updated_at', ''):
            out.update(state='needs_review', stage='Filename pass needs checking',
                       message='The filename worker stopped for review. Queued file changes remain held.')
        if proof and proof.get('status') == 'FAIL' and (out['state'] == 'needs_review' or proof.get('at', '') >= reservation.get('updated_at', '')):
            failures = {}
            for item in proof.get('errors', []):
                name = item.get('check', 'unknown')
                failures[name] = failures.get(name, 0) + 1
            out.update(state='needs_review', stage='Final filename checks need review', final_checks='failed',
                       verification_errors=[{'check': name, 'count': count} for name, count in sorted(failures.items())])
        log = root / 'completion-driver.log'
        heartbeat = datetime.fromtimestamp(log.stat().st_mtime, timezone.utc).isoformat() if log.exists() else reservation.get('updated_at')
        out.update(percent=round(100 * out['correct'] / out['total'], 1) if out['total'] else 0,
                   batch_elapsed_seconds=seconds_since(out['batch_started_at'], clock),
                   heartbeat_at=heartbeat, heartbeat_age_seconds=seconds_since(heartbeat, clock))
        out['heartbeat_stale'] = out['state'] == 'running' and (out['heartbeat_age_seconds'] is None or out['heartbeat_age_seconds'] > 180)
        out.pop('manifest_sha256', None)
        return out
