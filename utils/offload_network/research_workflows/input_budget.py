"""Conservative logical input accounting before producers run.

Count every declared mount/alias, even when content identities share a physical
copy. Artifact ports are bounded by their producer's full output allowance.
Run automatically at workflow admission and available as a planning diagnostic.
It does not replace native resolved-input,
archive/file verification, free-space or Docker-volume admission checks.
"""
from .spec import RESOURCE_KEYS


def preflight(workflow, object_expanded_bytes, runtime_limits):
    jobs = {job['id']: job for job in workflow['jobs']}
    if len(jobs) != len(workflow['jobs']):
        raise ValueError('unique job identities required')
    if any(set(job.get('resources', {})) - RESOURCE_KEYS for job in jobs.values()):
        raise ValueError('unsupported job resource override; input cap belongs to the runtime profile')

    def positive_bytes(value):
        if type(value) is not int or value < 0:
            raise ValueError('explicit nonnegative integer object byte count required')
        return value

    def limit(job, key):
        approved = runtime_limits[job['runtime']][key]
        value = approved if key == 'max_input_mb' else job.get('resources', {}).get(key, approved)
        if type(value) is not int or value <= 0:
            raise ValueError('positive explicit runtime resource limit required')
        if type(approved) is not int or approved <= 0 or value > approved:
            raise ValueError('job resource exceeds approved runtime profile')
        return value * (1 << 20)

    rows = []
    for job in jobs.values():
        known, produced, identities, inputs = 0, 0, set(), []
        capsule = job['capsule']
        size = positive_bytes(object_expanded_bytes[capsule])
        known += size; identities.add(capsule)
        inputs.append({'name': 'capsule', 'kind': 'known_object', 'object_sha256': capsule, 'bytes': size})
        for name, value in job['inputs'].items():
            if value['mode'] in ('bundle', 'dataset_ref', 'data_ref'):
                ident = value['object_sha256']; size = positive_bytes(object_expanded_bytes[ident])
                known += size; identities.add(ident)
                inputs.append({'name': name, 'kind': 'known_object', 'object_sha256': ident, 'bytes': size})
            elif value['mode'] == 'artifact_ref':
                parent = jobs[value['job']]
                if value['output'] not in parent['outputs']:
                    raise ValueError('artifact input must name a declared producer output')
                size = limit(parent, 'max_output_mb'); produced += size
                inputs.append({'name': name, 'kind': 'producer_output_upper_bound',
                    'producer': parent['id'], 'port': value['output'], 'bytes': size})
            else:
                raise ValueError('this diagnostic requires resolved immutable input sizes; no unknown size may be assumed zero')
        cap = limit(job, 'max_input_mb'); upper = known + produced
        status = ('DEFINITE_INPUT_BUDGET_REJECTION' if known > cap else
                  'UPPER_BOUND_WITHIN_CAP' if upper <= cap else 'UNRESOLVED_ARTIFACT_UPPER_BOUND')
        rows.append({'job': job['id'], 'known_logical_input_bytes': known,
            'artifact_logical_upper_bound_bytes': produced, 'logical_input_upper_bound_bytes': upper,
            'known_unique_physical_object_bytes': sum(object_expanded_bytes[k] for k in identities),
            'input_limit_bytes': cap, 'status': status, 'inputs': inputs})
    return {'schema': 'marketmaker.logical_input_budget_preflight.v1', 'jobs': rows,
        'scope': 'Logical alias accounting only. An artifact upper bound above the cap is unresolved, not proof that actual outputs cannot fit. Physical cache copies, work, output collection and free-space reserves require separate native checks.',
        'scientific_preflight': 'NOT_RUN', 'performance_qualification': 'NOT_ESTABLISHED'}
