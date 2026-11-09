"""Restore the paused remounter with only its backing-image path translated."""
import json
import os
from pathlib import Path
import subprocess
from organize import HERE, REPO, MOUNT, atomic_json, utc, validate_volume


def main():
    validate_volume()
    config = json.loads((REPO / 'data_paths.json').read_text())
    if config.get('organization', {}).get('state') != 'COMPLETE_RECONCILED':
        raise RuntimeError('Restore supervision only after the organization is reconciled and published')
    profile = REPO / 'utils/offload_network/.source-state/testing-reliability-20260913-v1/worker-guard.json'
    old_bytes = (HERE / 'BEFORE_SERVICE_worker-guard.json').read_bytes()
    original = json.loads(old_bytes)
    from build_plan import route
    index = {old: {'target': new} for old, new in config['path_relocations'].items()}
    relative = str(Path(original['image']).relative_to(MOUNT))
    replacement = dict(original, image=str(MOUNT / route(relative, index)[0]))
    if not Path(replacement['image']).is_dir():
        raise RuntimeError('Preserved backing image is missing')
    if profile.read_bytes() != old_bytes and json.loads(profile.read_text()) != replacement:
        raise RuntimeError('Worker guard profile changed concurrently; do not overwrite it')
    atomic_json(profile, replacement)
    plist = Path('/Users/tprice/Library/LaunchAgents/com.marketmaker.worker-guard.math-loop-20260911-v1.plist')
    if plist.read_bytes() != (HERE / ('BEFORE_SERVICE_' + plist.name)).read_bytes():
        raise RuntimeError('Worker guard LaunchAgent changed concurrently')
    target = f'gui/{os.getuid()}/com.marketmaker.worker-guard.math-loop-20260911-v1'
    exists = subprocess.run(['launchctl', 'print', target], capture_output=True)
    if exists.returncode == 0:
        outcome = {'action': 'already_loaded', 'returncode': 0}
    else:
        restored = subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(plist)],
                                  capture_output=True, text=True, timeout=20)
        outcome = {'action': 'bootstrap', 'returncode': restored.returncode,
                   'stdout': restored.stdout, 'stderr': restored.stderr}
    outcome.update(at_utc=utc(), original_image=original['image'], preserved_image=replacement['image'],
                   changed_profile_fields=['image'], worker_execution_status='NOT_ASSERTED_BY_SUPERVISOR_RESTORE')
    atomic_json(HERE / 'WORKER_GUARD_RESTORED.json', outcome)
    print(json.dumps(outcome, indent=2))
    if outcome['returncode']:
        raise SystemExit(outcome['returncode'])


if __name__ == '__main__': main()
