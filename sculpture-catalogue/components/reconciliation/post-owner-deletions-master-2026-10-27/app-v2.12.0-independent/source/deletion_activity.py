"""Per-original deletion reservations, including the keepers of pending jobs."""
import json

from store import Conflict


class DeletionBusy(Conflict):
    def __init__(self, items, message='These files already have a deletion job or are being retained as keepers. Check Jobs.'):
        super().__init__(message)
        self.details = {'busy_files': items}


def activity(db, catalogue):
    jobs = {r['id']: {**dict(r), 'payload': json.loads(r['payload'])}
            for r in db.execute('SELECT * FROM deletion_jobs')}
    active = {}
    keepers = {}

    def reserve(job, parent_id, state):
        fid, p = job['file_id'], job['payload']
        active[fid] = {'file_id': fid, 'job_id': parent_id, 'operation_id': job['id'],
                       'state': state, 'kind': 'delete', 'name': p['file']['name']}
        keeper = p.get('keeper_binding')
        if keeper and state not in ('deleted', 'already_absent'):
            keepers[keeper['id']] = {'file_id': keeper['id'], 'job_id': parent_id,
                                    'state': 'keeper_reserved', 'kind': 'keeper',
                                    'name': (p.get('keeper') or {}).get('name', keeper['id'])}

    for row in db.execute("SELECT * FROM background_jobs WHERE kind IN ('delete','delete_batch') AND state IN ('queued','running','uncertain')"):
        p = json.loads(row['payload'])
        if row['kind'] == 'delete':
            ids = [p['body']['operation_id']]
        else:
            batch = db.execute('SELECT payload FROM deletion_batches WHERE id=?', (p['body']['batch_id'],)).fetchone()
            ids = json.loads(batch['payload'])['operation_ids'] if batch else []
        for oid in ids:
            job = jobs[oid]
            # A stopped/interrupted batch never automatically resumes its
            # untouched members. Only their actual per-file state can block.
            if job['state'] == 'prepared' and row['state'] in ('queued', 'running'):
                reserve(job, row['id'], row['state'])
            elif job['state'] in ('executing', 'uncertain'):
                reserve(job, row['id'], job['state'])
    for job in jobs.values():
        if job['state'] in ('executing', 'uncertain', 'deleted', 'already_absent'):
            reserve(job, active.get(job['file_id'], {}).get('job_id'), job['state'])
    result = {**keepers, **active}
    # A displayed exact-byte group is withheld by a member deletion. Surface
    # that same reservation for all aliases, without deleting any extra file.
    canonical = getattr(catalogue, 'canonical_assets', {})
    members = getattr(catalogue, 'duplicate_members', {})
    for fid, item in list(result.items()):
        cid = canonical.get(fid, fid)
        for alias in [cid, *members.get(cid, [])]:
            result.setdefault(alias, item)
    return result
