"""Separate retained execution facts from current, authenticated observations."""
from copy import deepcopy


TERMINAL = {'succeeded', 'failed', 'cancelled', 'interrupted', 'skipped', 'blocked_dependency'}


def job_view(node, *, stale, source, worker_available=None):
    """Never promote a last-known active state into a current running count.

    Terminal delivered facts remain useful when their worker has been retired.
    No durable workflow/job record is changed by this display projection.
    """
    result = deepcopy(node)
    result.update(stale=stale, observation_source=source)
    if stale and result.get('state') not in TERMINAL:
        result['last_known_state'] = result.get('state')
        result['state'] = 'unobserved'
        reason = 'worker_unavailable' if worker_available is False else 'fresh_observation_required'
        result['wait_reasons'] = list(dict.fromkeys([reason, *result.get('wait_reasons', [])]))
    return result
