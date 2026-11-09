"""Publish only verified physical locations; retain historical source identities."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from organize import HERE, REPO, MOUNT, atomic_json, utc, validate_volume
from build_plan import route

CONFIG = REPO / 'data_paths.json'
ORIGINAL = HERE / 'BEFORE_data_paths.json'
STATE = HERE / 'REGISTRY_STATE.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_write(payload):
    expected = json.loads(STATE.read_text())['published_sha256'] if STATE.exists() else sha(ORIGINAL)
    if sha(CONFIG) != expected:
        raise RuntimeError('Registry was changed by another writer; retain and reconcile before publication')
    atomic_json(CONFIG, payload)
    atomic_json(STATE, {'published_sha256': sha(CONFIG), 'at_utc': utc(),
                        'organization': payload['organization']})


def verified_actions(plan):
    verified = {}
    for action in plan['actions']:
        ident = hashlib.sha256((action['source'] + '\0' + action['target']).encode()).hexdigest()[:24]
        receipt_path = HERE / 'execution/moves' / ident / 'RECEIPT.json'
        if not receipt_path.exists():
            continue
        receipt = json.loads(receipt_path.read_text())
        if receipt['action'] != action:
            raise RuntimeError('Move plan and receipt disagree')
        if receipt['status'] == 'VERIFIED':
            if (MOUNT / action['source']).exists() or not (MOUNT / action['target']).exists():
                raise RuntimeError('Verified move paths changed: ' + action['source'])
            verified[action['source']] = action
        elif receipt['status'] not in {'PREPARED'}:
            raise RuntimeError('Unverified renamed data requires reconciliation: ' + action['source'])
    return verified


def build_registry(original, plan, verified):
    payload = copy.deepcopy(original)
    ibkr_done = 'marketmaker/data/ibkr' in verified
    root = 'raw_price_data' if ibkr_done else 'marketmaker/data'
    payload['data_root'] = str(MOUNT / root)
    payload['external_storage']['data_root_relative'] = root
    payload['external_storage']['identity_file'] = 'raw_price_data/.marketmaker-storage-identity.json'
    mappings = {}
    for action in plan['actions']:
        source = action['source']
        if source.startswith('marketmaker/data/'):
            # Pending child moves keep their old location until their parent can move.
            mappings[source.removeprefix('marketmaker/')] = verified.get(source, action)['target'] if source in verified else source
    payload['physical_locations'] = dict(sorted(mappings.items()))
    payload['path_relocations'] = dict(sorted((k, v['target']) for k, v in verified.items()))
    for entry in payload.get('source_locations', {}).values():
        if 'mount_relative' in entry:
            entry['mount_relative'] = route(entry['mount_relative'], verified)[0]
    payload['path_policy']['configured_paths_must_be_below_data_root'] = False
    payload['path_policy']['configured_paths_must_be_below_verified_mount'] = True
    payload['organization'] = {
        'state': 'RELOCATED_PENDING_RECONCILIATION' if len(verified) == len(plan['actions']) else 'PARTIAL_WITH_EXPLICIT_OLD_LOCATIONS',
        'published_at_utc': utc(), 'verified_actions': len(verified), 'planned_actions': len(plan['actions']),
        'plan_sha256': sha(HERE / 'PLAN.json'),
        'record_directory': str(HERE.relative_to(REPO)),
        'historical_receipts': 'Original bytes retained; resolve_relocated_path translates their original paths',
    }
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['begin', 'prepare', 'publish'])
    args = parser.parse_args()
    validate_volume()
    original = json.loads(ORIGINAL.read_text())
    plan = json.loads((HERE / 'PLAN.json').read_text())
    if args.command == 'begin':
        current = json.loads(CONFIG.read_text())
        current['organization'] = {'state': 'MIGRATING', 'started_at_utc': utc(),
                                   'record_directory': str(HERE.relative_to(REPO))}
        checked_write(current)
        print('New registry-based data access paused during verified moves', flush=True)
        return
    verified = {a['source']: a for a in plan['actions']} if args.command == 'prepare' else verified_actions(plan)
    payload = build_registry(original, plan, verified)
    if args.command == 'prepare':
        payload['organization']['state'] = 'PROPOSED_ONLY_NOT_EXECUTED'
        payload['organization']['verified_actions'] = 0
    elif (HERE / 'DELETION_READINESS.json').exists() and (HERE / 'reconciliation/RESULT.json').exists():
        ready = json.loads((HERE / 'DELETION_READINESS.json').read_text())
        audit = json.loads((HERE / 'reconciliation/RESULT.json').read_text())
        if (len(verified) == len(plan['actions']) and audit['status'] == 'PASS'
                and ready['marketmaker_removed'] and audit['plan_sha256'] == sha(HERE / 'PLAN.json')):
            payload['organization']['state'] = 'COMPLETE_RECONCILED'
            payload['organization']['marketmaker_removed'] = True
            payload['organization']['marketmaker_v2_root_retained'] = True
            payload['organization']['marketmaker_v2_ready_for_removal'] = ready['marketmaker_v2_ready_for_empty_directory_removal']
    atomic_json(HERE / ('PROPOSED_data_paths.json' if args.command == 'prepare' else 'ACTUAL_data_paths.json'), payload)
    if args.command == 'publish':
        storage = payload['external_storage']
        marker = {key: storage[key] for key in ['data_root_relative', 'identity_token', 'volume_uuid', 'usb_serial']}
        marker['schema'] = 'marketmaker_external_data_volume.v1'
        atomic_json(MOUNT / storage['identity_file'], marker)
        checked_write(payload)
    print(json.dumps(payload['organization'], indent=2), flush=True)


if __name__ == '__main__':
    main()
