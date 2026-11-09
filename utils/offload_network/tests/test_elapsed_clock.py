"""Elapsed accounting must not change when the wall clock steps."""
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import sys
import tarfile

import pytest

from v2 import runner, submit
from v2.drivers import cache_stage, generic, random_windows
from v2.manifest import HostSpec, ResultSpec, SealError, SealedBlob, SealedManifest
from v2.seal import build_seal, extract_seal


class Clock:
    def __init__(self, jump):
        self.wall = 100.0
        self.elapsed = 0.0
        self.jump = jump

    def time(self):
        return self.wall

    def monotonic(self):
        return self.elapsed

    def advance(self, seconds, *, jump=False):
        self.elapsed += seconds
        self.wall += seconds + (self.jump if jump else 0)

    def sleep(self, seconds):
        self.advance(seconds)

    def utc(self):
        return datetime.fromtimestamp(self.wall, timezone.utc).isoformat(timespec='seconds')


def program(outcome):
    code = "from pathlib import Path\nPath('outputs').mkdir(exist_ok=True)\nPath('outputs/value.json').write_text('{\"value\":7}')\n"
    if outcome == 'exit':
        code += 'raise SystemExit(7)\n'
    elif outcome == 'exception':
        code += "raise RuntimeError('synthetic entrypoint failure')\n"
    return code


def manifest_for(tmp_path, outcome='normal'):
    entry = tmp_path / 'entry.py'
    entry.write_text(program(outcome))
    return SealedManifest(job_id='elapsed-clock-fixture',
        host=HostSpec('synthetic', '/srv/offload', platform='linux'),
        blobs=[SealedBlob('entrypoint', str(entry), 'code/entry.py')],
        entrypoint_rel='code/entry.py', result=ResultSpec(local_dir=str(tmp_path / 'returned')))


@pytest.mark.parametrize('jump', [-120.0, 120.0])
@pytest.mark.parametrize('outcome', ['normal', 'exit', 'exception', 'pack_failure'])
def test_runner_elapsed_and_archived_status_preserve_outcomes_and_utc(tmp_path, monkeypatch, jump, outcome):
    manifest = manifest_for(tmp_path, outcome)
    seal = build_seal(manifest, out_dir=tmp_path / 'seals')
    work = tmp_path / 'work'
    extract_seal(seal, work)
    clock = Clock(jump)
    start_utc = clock.utc()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'path', list(sys.path))
    monkeypatch.setattr(runner, 'time', clock)
    monkeypatch.setattr(runner, '_now', clock.utc)
    # Keep pytest's capture descriptors. Blob verification, actual entrypoint
    # execution, status writing and result packing remain the real runner path.
    monkeypatch.setattr(runner, '_redirect_stdio_to_runlog', lambda work: None)
    original = runpy.run_path

    def execute(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        finally:
            clock.advance(2.4, jump=True)

    monkeypatch.setattr(runpy, 'run_path', execute)
    if outcome == 'pack_failure':
        def fail_pack(*args):
            raise OSError('synthetic result pack failure')
        monkeypatch.setattr(runner, '_pack_result', fail_pack)
    result = runner.main(str(work / 'manifest.json'))
    status = json.loads((work / 'status.json').read_text())
    assert status['elapsed_s'] == 2.4
    assert status['elapsed_clock'] == 'time.monotonic'
    assert status['started_at'] == start_utc and status['run_started_at'] == start_utc
    assert status['run_finished_at'] == clock.utc() and status['finished_at'] == clock.utc()
    expected = {'normal': 0, 'exit': 7, 'exception': 73, 'pack_failure': 74}[outcome]
    assert result == expected
    assert json.loads((work / 'outputs/value.json').read_text()) == {'value': 7}
    if outcome == 'pack_failure':
        assert status['phase'] == 'exited_pack_failed' and 'synthetic result pack failure' in status['pack_error']
        assert status['exit_code'] == 0
    else:
        assert status['phase'] == 'exited' and status['exit_code'] == expected
        with tarfile.open(status['result_archive'], 'r:gz') as archive:
            execution = json.load(archive.extractfile('status.json'))
            assert execution['elapsed_s'] == status['elapsed_s']
            assert execution['elapsed_clock'] == status['elapsed_clock']
            assert execution['run_finished_at'] == status['run_finished_at']
            assert json.load(archive.extractfile('outputs/value.json')) == {'value': 7}


@pytest.fixture
def isolated_driver_process(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'path', list(sys.path))
    monkeypatch.setattr(sys, 'argv', list(sys.argv))
    existing = {name: value for name, value in sys.modules.items()
                if name == 'c_emd' or name.startswith('c_emd.') or name == 'elapsed_probe'}
    for name in existing:
        del sys.modules[name]
    try:
        yield
    finally:
        for name in list(sys.modules):
            if name == 'c_emd' or name.startswith('c_emd.') or name == 'elapsed_probe':
                del sys.modules[name]
        sys.modules.update(existing)


@pytest.mark.parametrize('jump', [-120.0, 120.0])
@pytest.mark.parametrize('outcome', ['normal', 'exit', 'exception'])
@pytest.mark.parametrize('kind', ['generic_script', 'generic_module', 'random_windows'])
def test_driver_elapsed_ignores_wall_steps_and_keeps_exit_status(
    tmp_path, monkeypatch, isolated_driver_process, jump, outcome, kind
):
    code = tmp_path / 'blobs/code'
    code.mkdir(parents=True)
    clock = Clock(jump)
    module = random_windows if kind == 'random_windows' else generic
    monkeypatch.setattr(module, 'time', clock)
    monkeypatch.setattr(module, '_HOST_REPO_CANDIDATES', [])
    if kind == 'random_windows':
        package = code / 'c_emd/python'
        package.mkdir(parents=True)
        (code / 'c_emd/__init__.py').write_text('')
        (package / '__init__.py').write_text('')
        (package / 'random_windows_pipeline.py').write_text(program(outcome))
        sys.argv = ['random_windows', '--cohort', 'synthetic', '--out-dir', 'outputs']
    elif kind == 'generic_module':
        (code / 'elapsed_probe.py').write_text(program(outcome))
        sys.argv = ['generic', '--module', 'elapsed_probe', '--out-dir', 'outputs']
    else:
        (code / 'probe.py').write_text(program(outcome))
        sys.argv = ['generic', '--script', 'probe.py', '--out-dir', 'outputs']
    call = 'run_path' if kind == 'generic_script' else 'run_module'
    original = getattr(runpy, call)

    def execute(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        finally:
            clock.advance(2.4, jump=True)

    monkeypatch.setattr(runpy, call, execute)
    result = module.main()
    report = json.loads((tmp_path / 'outputs/report.json').read_text())
    assert report['elapsed_s'] == 2.4
    assert report['elapsed_clock'] == 'time.monotonic'
    assert result == report['rc'] == {'normal': 0, 'exit': 7, 'exception': 3}[outcome]
    assert json.loads((tmp_path / 'outputs/value.json').read_text()) == {'value': 7}


@pytest.mark.parametrize('jump', [-120.0, 120.0])
def test_cache_copy_elapsed_keeps_exact_bytes_and_source_mtime(tmp_path, monkeypatch, jump):
    source = tmp_path / 'source.mat'
    source.write_bytes(b'synthetic immutable cache bytes')
    original_mtime = source.stat().st_mtime_ns
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['cache_stage', '--src-cache', str(source), '--instrument-id', 'synthetic'])
    clock = Clock(jump)
    monkeypatch.setattr(cache_stage, 'time', clock)
    original = cache_stage.shutil.copy2

    def copy(*args, **kwargs):
        result = original(*args, **kwargs)
        clock.advance(2.4, jump=True)
        return result

    monkeypatch.setattr(cache_stage.shutil, 'copy2', copy)
    assert cache_stage.main() == 0
    report = json.loads((tmp_path / 'report.json').read_text())
    assert report['copy_elapsed_s'] == 2.4 and report['copy_elapsed_clock'] == 'time.monotonic'
    assert Path(report['dst']).read_bytes() == source.read_bytes()
    assert Path(report['dst']).stat().st_mtime_ns == original_mtime
    assert json.loads((tmp_path / 'outputs/report.json').read_text()) == report


def mocked_submission(tmp_path, monkeypatch, clock, terminal):
    manifest = manifest_for(tmp_path)
    removals = []

    def build(*args, **kwargs):
        clock.advance(1, jump=True)
        return tmp_path / 'sealed.tar.gz'

    def push(**kwargs):
        clock.advance(1)
        return '/srv/offload/sealed.tar.gz'

    def launch(*args, **kwargs):
        clock.advance(1)
        return {'workdir': '/srv/offload/job', 'status_path': '/srv/offload/job/status.json'}

    def status(*args, **kwargs):
        clock.advance(1)
        return terminal

    def fetch(*args, **kwargs):
        clock.advance(1)
        return {'verified': True}

    def remove(**kwargs):
        clock.advance(1)
        removals.append(kwargs['remote_path'])

    monkeypatch.setattr(submit, 'time', clock)
    for name, method in [('build_seal', build), ('push_seal', push), ('launch', launch),
                         ('read_remote_status', status), ('fetch_and_unpack', fetch), ('remote_remove', remove)]:
        monkeypatch.setattr(submit, name, method)
    return manifest, removals


@pytest.mark.parametrize('jump', [-120.0, 120.0])
@pytest.mark.parametrize('remote_clock', [None, 'time.monotonic'])
def test_submit_keeps_local_durations_separate_from_remote_clock(tmp_path, monkeypatch, jump, remote_clock):
    clock = Clock(jump)
    terminal = {'phase': 'exited', 'exit_code': 0, 'elapsed_s': .75}
    if remote_clock is not None:
        terminal['elapsed_clock'] = remote_clock
    manifest, removed = mocked_submission(tmp_path, monkeypatch, clock, terminal)
    result = submit.submit_one(manifest, bundle_out_dir=tmp_path / 'bundles', poll_interval_s=1, deadline_s=20)
    times = result['timings']
    assert times['started_at'] == 100.0
    assert {key: times[key] for key in ('build_s', 'push_s', 'launch_s', 'poll_s', 'pull_s')} == {
        'build_s': 1.0, 'push_s': 1.0, 'launch_s': 1.0, 'poll_s': 1.0, 'pull_s': 1.0}
    assert times['total_s'] == 5.0 and times['cleanup_s'] == 2.0
    assert times['elapsed_clock'] == 'time.monotonic'
    assert times['remote_elapsed_s'] == .75 and times['remote_elapsed_clock'] == remote_clock
    assert result['status'] == terminal and len(removed) == 2


@pytest.mark.parametrize('jump', [-120.0, 120.0])
def test_submit_deadline_uses_elapsed_time_and_preserves_remote_work(tmp_path, monkeypatch, jump):
    clock = Clock(jump)
    manifest, removed = mocked_submission(tmp_path, monkeypatch, clock, None)
    calls = []

    def status(*args, **kwargs):
        calls.append(True)
        if len(calls) > 2:
            raise AssertionError('submit escaped its declared elapsed deadline')
        clock.advance(2)
        return None

    monkeypatch.setattr(submit, 'read_remote_status', status)
    with pytest.raises(SealError, match='exceeded deadline'):
        submit.submit_one(manifest, bundle_out_dir=tmp_path / 'bundles', poll_interval_s=1, deadline_s=5)
    assert len(calls) == 1 and clock.monotonic() == 6.0
    assert removed == []
