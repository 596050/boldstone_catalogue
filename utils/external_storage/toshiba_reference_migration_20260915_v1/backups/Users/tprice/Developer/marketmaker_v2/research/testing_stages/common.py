"""Small shared IO primitives; no model, price archive or broker mutations."""
from __future__ import annotations

import contextlib
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
import plistlib
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import numpy as np
from research import resolve_research_path, LEGACY_ROOT

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RETIRED = ROOT / 'research/archive/testing_stages_consolidation_20260908/previous_layout'
FLOOR = resolve_research_path(ROOT / 'research/equity_full_minute_price_policy_20260905_v1/POLICY.json')
FIELDS = ('open', 'high', 'low', 'close', 'volume')


def input_path(value):
    """Locate inputs, including unchanged evidence from the archived runners.

    This is an explicit read-path lookup, never an output redirect or import
    hook. Historical file references keep their original content hashes.
    """
    from research.testing_stages.stage_00_contracts.retired_inputs import require_path
    require_path(value)
    path = resolve_research_path(value)
    require_path(path)
    if path.exists():
        return path
    try:
        relative = path.absolute().relative_to(HERE)
        archived = RETIRED / relative
        if archived.exists():
            return archived
    except ValueError:
        pass
    old = ('stage1_model_parallel_20260907_v1', 'stage1_relocated_paths_20260907_v1',
           'stage1_replay_recovery_20260907_v1', 'frozen_ig_pair_comparison_repair_20260907_v1',
           'frozen_ig_pair_full_stages_20260907_v1')
    for name in old:
        try:
            relative = path.relative_to(HERE.parent / name)
        except ValueError:
            continue
        archived = resolve_research_path(ROOT / 'research/archive/stage1_consolidation_20260907_v1/previous_layout' / name / relative)
        if archived.exists():
            return archived
    return path


def sha(path):
    from research.testing_stages.runtime.verified_hashes import lookup
    return lookup(input_path(path), _sha_bytes)


def _sha_bytes(path):
    import time
    from research.testing_stages.runtime import timing
    started = time.perf_counter(); size = 0
    h = hashlib.sha256()
    with input_path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 << 20), b''):
            size += len(block)
            h.update(block)
    timing.record('file_hashing', time.perf_counter() - started, size)
    value = h.hexdigest()
    from research.testing_stages.stage_00_contracts.retired_inputs import require_hash
    require_hash(value)
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def array_digest(value):
    a = np.ascontiguousarray(value)
    return hashlib.sha256(str((a.dtype.str, a.shape)).encode() + a.tobytes()).hexdigest()


def safe_output(path):
    path = Path(path).absolute()
    resolved = path.resolve()
    protected = ROOT / 'frozen_models_running'
    if resolved == protected or protected in resolved.parents:
        raise ValueError('Output must be outside frozen_models_running')
    # Never allow an output argument to overwrite the source archive.
    if '/iqfeed_archive/' in str(resolved) or resolved.name == 'iqfeed_archive':
        raise ValueError('Output must be outside the price archive')
    if path.is_symlink():
        raise ValueError('Output may not be a symlink')
    return path


def storage_snapshot(path):
    path = Path(path).resolve()
    if str(path).startswith('/Volumes/'):
        volume = Path('/Volumes') / path.parts[2]
        if not os.path.ismount(volume):
            raise ValueError('external output volume is not mounted: ' + str(volume))
        if volume.name == 'Toshiba 2TB':
            info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(volume)]))
            usb = subprocess.check_output(['ioreg', '-p', 'IOUSB', '-l', '-w', '0'], text=True)
            if (info.get('VolumeUUID') != '087E2AA1-5151-322D-8C09-9852ECD979B5'
                    or '"USB Serial Number" = "20251128012837F"' not in usb):
                raise ValueError('expected Toshiba volume UUID or USB serial is absent')
        else:
            info = {}
        return {'volume': str(volume), 'device': volume.stat().st_dev,
                'volume_uuid': info.get('VolumeUUID'), 'free_bytes': shutil.disk_usage(volume).free}
    return {'volume': None, 'free_bytes': shutil.disk_usage(path if path.exists() else path.parent).free}


def save_arrays(path, *, array=None, **arrays):
    path = safe_output(path)
    if path.exists():
        raise FileExistsError('preserve bound action/mark artifact: ' + str(path))
    tmp = path.with_name('.' + path.name + '.tmp')
    try:
        with tmp.open('xb') as f:
            if array is not None:
                np.save(f, array, allow_pickle=False)
            else:
                np.savez_compressed(f, **arrays)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_json(path, value, *, replace=False):
    path = safe_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.' + str(os.getpid()) + '.' + uuid.uuid4().hex + '.tmp')
    try:
        # Bound streaming memory while reducing small writes on remote/bind
        # filesystems. Keep JSON bytes, flush/fsync and publication unchanged.
        with tmp.open('x', buffering=1 << 20) as f:
            json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        if replace:
            os.replace(tmp, path)
        else:
            try:
                os.link(tmp, path)  # Atomic no-clobber where hard links are supported.
            except OSError as error:
                if error.errno not in (errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS, errno.EPERM):
                    raise
                # Some mounted data volumes support rename but neither hard links
                # nor exclusive rename. Serialize their publishers, then atomically
                # expose the fully fsynced file. The OS releases this short lock on
                # exit; the persistent guard inode must not be deleted by a writer.
                with (path.parent / '.atomic_json.lock').open('a+b') as guard:
                    fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
                    try:
                        if os.path.lexists(path):
                            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(path))
                        os.replace(tmp, path)
                    finally:
                        fcntl.flock(guard.fileno(), fcntl.LOCK_UN)
    finally:
        tmp.unlink(missing_ok=True)


@contextlib.contextmanager
def lock(directory):
    directory = safe_output(directory)
    if str(directory).startswith('/Volumes/'):
        storage_snapshot(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'RUN.lock').open('a+') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise ValueError('Another process owns ' + str(directory)) from e
        yield


def load_module(path, name=None):
    path = input_path(path).resolve()
    sys.dont_write_bytecode = True
    name = name or 'stage1_plugin_' + sha(path)[:20]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if sys.modules.get(name) is module:
            del sys.modules[name]
        raise
    return module


def code_bindings():
    paths = sorted(HERE.glob('*.py')) + [FLOOR,
        HERE / 'recorded_rosters.json', HERE / 'configs/CONTRACTS.json',
        HERE / 'inputs/frozen_ig_pair_20260907/PROTOCOL.md',
        ROOT / 'research/__init__.py',
        ROOT / 'data_paths.json',
        ROOT / 'research/utility/research_paths_v1/reporting.py',
        ROOT / 'research/all_research_candidates_not_harness_frameworks/research_storage/research_root_cleanup_20260907_v2/PATHS.json',
        ROOT / 'research/us_equity_session_close_clock_20260905_v2/session_clock.py',
        ROOT / 'research/us_equity_session_close_clock_20260905_v1/calendar.py',
        ROOT / 'research/utility/us_equity_daily_calendar_v1/calendar.py',
        ROOT / 'research/conjectures/frozen_ig_pair_50pct_v1/CONJECTURE.json',
        ROOT / 'research/conjectures/frozen_ig_pair_50pct_v1/thresholds.py']
    paths.append(LEGACY_ROOT / 'research/__init__.py')
    result = {}
    for p in paths:
        resolved = input_path(p)
        key = str(resolved.relative_to(ROOT)) if ROOT in resolved.parents else str(resolved)
        result[key] = sha(resolved)
    return result
