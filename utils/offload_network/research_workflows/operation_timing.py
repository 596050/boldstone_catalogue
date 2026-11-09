"""Opt-in bounded control-plane timing; never part of a scientific identity.

Collection is local to the current execution context. No clock reads or retained
rows are added when disabled. Nested durations overlap and must not be summed.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import json
from pathlib import Path
import sys
from time import monotonic as _clock

from .common import sync_directory

_active = ContextVar('offload_operation_timing', default=None)
_parent = ContextVar('offload_operation_timing_parent', default=None)


@contextmanager
def collect(*, max_phases=10000):
    if type(max_phases) is not int or not 1 <= max_phases <= 100000:
        raise ValueError('max_phases must be an integer from 1 to 100000')
    report = {'schema': 'marketmaker.offload_operation_timing.v1',
        'clock': 'time.monotonic', 'status': 'RUNNING', 'phases': [],
        'max_phases': max_phases, 'dropped_phases': 0,
        'interpretation': 'Nested intervals overlap; do not sum them. This measures this caller, not remote job computation or physical disk latency.',
        'performance_qualification': 'NOT_ESTABLISHED'}
    token, parent = _active.set(report), _parent.set(None)
    started = _clock()
    try:
        yield report
    except BaseException as error:
        report.update(status='FAILED', exception_type=type(error).__name__)
        raise
    else:
        report['status'] = 'COMPLETED'
    finally:
        report['elapsed_seconds'] = _clock() - started
        _parent.reset(parent)
        _active.reset(token)


@contextmanager
def phase(name, **details):
    report = _active.get()
    if report is None:
        yield {}
        return
    if len(report['phases']) >= report['max_phases']:
        report['dropped_phases'] += 1
        yield {}
        return
    row = {'index': len(report['phases']), 'parent_index': _parent.get(),
           'phase': name, 'details': details, 'status': 'RUNNING'}
    report['phases'].append(row)
    token = _parent.set(row['index'])
    started = _clock()
    try:
        yield row['details']
    except BaseException as error:
        row.update(status='FAILED', exception_type=type(error).__name__)
        raise
    else:
        row['status'] = 'COMPLETED'
    finally:
        row['elapsed_seconds'] = _clock() - started
        _parent.reset(token)


@contextmanager
def record_to(path, operation):
    """Retain success or handled failure separately, refusing existing output.

Exclusive creation also catches a file appearing during the operation. A process
death or failed write can leave an incomplete diagnostic, never a valid success
receipt. Filesystem errors do not replace an original operation exception.
"""
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError('preserve existing operation timing report: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    failure = None
    try:
        with collect() as report:
            with phase(operation):
                yield report
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            payload = json.dumps(report, sort_keys=True, allow_nan=False) + '\n'
            with path.open('x', encoding='utf-8') as stream:
                stream.write(payload)
                stream.flush()
                import os
                os.fsync(stream.fileno())
            sync_directory(path.parent)
        except Exception as error:
            if failure is None:
                raise RuntimeError('operation completed but timing report could not be saved; inspect the original result before retrying') from error
            # Warning filters and a closed stderr must not replace the original
            # operation failure with a secondary diagnostic-write exception.
            try:
                print('operation timing report could not be saved: ' + type(error).__name__, file=sys.stderr)
            except Exception:
                pass
