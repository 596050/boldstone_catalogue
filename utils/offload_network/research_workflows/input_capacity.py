"""Provisional Docker-volume capacity before a durable execution claim.

Object declarations are sizing evidence only. The original before/after byte
verification and the final staging reservation remain mandatory.
"""
import json
from dataclasses import dataclass

from lib.live_files import live_tree_bytes

MIB = 1 << 20


def identities(payload):
    if payload.get('workflow_input_transport') != 'docker-volume':
        return set()
    return {mount['object_sha256'] for mount in payload.get('workflow_mounts', [])}


@dataclass(frozen=True)
class Snapshot:
    sizes: dict
    live_bytes: int

    def copies(self, payload):
        refs = identities(payload)
        if not refs:
            return 0
        # A new job can arrive after the filesystem snapshot. Its approved
        # logical bound is a conservative fallback until the next observation.
        if not refs <= self.sizes.keys():
            return payload['template']['max_input_mb'] * MIB
        return sum(self.sizes[identity] for identity in refs)

    def allows(self, worker, db, payload, free_bytes):
        active = [json.loads(row[0]) for row in db.execute("SELECT payload FROM jobs WHERE state='running'")]
        jobs = [*active, payload]
        copied = sum(self.copies(job) for job in jobs)
        growth = sum(worker._execution_storage_bytes(job) for job in jobs)
        # Existing work may already have consumed some of its allowance. Keep
        # the full allowance, as the base worker does, rather than infer future
        # growth from an empty or partly written workspace.
        return (free_bytes >= worker.min_free_mb * MIB + growth + copied
                and self.live_bytes + growth + copied <= worker.max_store_mb * MIB)


def observe(worker):
    """Read committed size declarations and the filesystem outside the DB lock."""
    with worker.db_lock:
        payloads = [json.loads(row[0]) for row in worker.db.execute(
            "SELECT payload FROM jobs WHERE state IN ('queued','running')")]
    references = set().union(*(identities(p) for p in payloads))
    if not references:
        return None
    sizes = {}
    for identity in references:
        try:
            sizes[identity] = worker.workflows.objects.declared_size(identity)
        except (KeyError, ValueError, OSError):
            # Sizing never excuses a damaged/missing object. Use the approved
            # upper bound; actual execution still fails its independent check.
            continue
    return Snapshot(sizes, live_tree_bytes(worker.root))
