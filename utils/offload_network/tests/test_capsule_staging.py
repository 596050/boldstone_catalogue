"""Fast capsule scratch preserves sealed bytes and never relocates bulk inputs."""
from copy import deepcopy
from pathlib import Path

import pytest

from research_workflows.common import load, sha
from research_workflows import planner


def request(tmp_path):
    code, data = tmp_path / 'code', tmp_path / 'data'
    code.mkdir(); data.mkdir()
    (code / 'main.py').write_text("raise RuntimeError('must not execute during packaging')\n")
    (data / 'prices.bin').write_bytes(bytes(range(256)) * 16)
    return {'schema': 'marketmaker.research_offload_workflow.v1', 'submission_id': 'scratch-test',
        'jobs': [{'id': 'test', 'kind': 'report', 'runtime': 'python',
            'capsule': {'source': str(code)}, 'entrypoint': 'main.py',
            'inputs': {'data': {'mode': 'bundle', 'source': str(data)}},
            'outputs': {'report': {'type': 'json', 'path': 'artifacts/report.json'}}}]}


def test_capsule_staging_preserves_objects_and_keeps_data_on_destination(tmp_path, monkeypatch):
    spec = request(tmp_path); before = deepcopy(spec)
    normal, moved, scratch = tmp_path / 'normal', tmp_path / 'moved', tmp_path / 'scratch'
    scratch.mkdir()
    original = planner.plan(spec, normal)
    captures, archives = [], []
    snapshot, pack = planner.snapshot, planner.pack

    def observed_snapshot(source, destination, **kwargs):
        captures.append((Path(source).name, Path(destination)))
        return snapshot(source, destination, **kwargs)

    def observed_pack(source, archive, **kwargs):
        archives.append(Path(archive))
        return pack(source, archive, **kwargs)

    monkeypatch.setattr(planner, 'snapshot', observed_snapshot)
    monkeypatch.setattr(planner, 'pack', observed_pack)
    changed = planner.plan(spec, moved, capsule_staging_directory=scratch)
    assert spec == before
    assert changed['workflow_sha256'] == original['workflow_sha256']
    assert load(normal / 'WORKFLOW.json') == load(moved / 'WORKFLOW.json')
    assert {p.name: sha(p) for p in (normal/'objects').iterdir()} == {p.name: sha(p) for p in (moved/'objects').iterdir()}
    assert captures[0][0] == 'code' and captures[0][1].is_relative_to(scratch)
    assert captures[1][0] == 'data' and captures[1][1].is_relative_to(moved)
    assert all(p.is_relative_to(moved) for p in archives)  # no cross-device rename needed
    assert not list(scratch.iterdir())
    assert changed['capsule_staging']['directory'] == str(scratch)


@pytest.mark.parametrize('inside', ['code', 'data'])
def test_staging_inside_any_source_fails_before_copy(tmp_path, monkeypatch, inside):
    spec = request(tmp_path); output = tmp_path/'plan'
    def forbidden(*args, **kwargs):
        pytest.fail('known invalid staging must fail before taking any snapshot')
    monkeypatch.setattr(planner, 'snapshot', forbidden)
    with pytest.raises(ValueError, match='inside a packaged source'):
        planner.plan(spec, output, capsule_staging_directory=tmp_path/inside)
    assert not output.exists()


def test_missing_staging_directory_is_not_created_implicitly(tmp_path):
    spec = request(tmp_path); scratch = tmp_path/'absent'
    with pytest.raises(ValueError, match='existing directory'):
        planner.plan(spec, tmp_path/'plan', capsule_staging_directory=scratch)
    assert not scratch.exists() and not (tmp_path/'plan').exists()


def test_capsule_source_change_still_fails_with_separate_scratch(tmp_path, monkeypatch):
    spec = request(tmp_path); scratch = tmp_path/'scratch'; scratch.mkdir()
    import research_workflows.capsule as capsule
    copy = capsule.shutil.copyfile
    def changed(source, destination, *args, **kwargs):
        value = copy(source, destination, *args, **kwargs)
        if Path(source).name == 'main.py':
            Path(source).write_text('changed source\n')
        return value
    monkeypatch.setattr(capsule.shutil, 'copyfile', changed)
    with pytest.raises(ValueError, match='source changed'):
        planner.plan(spec, tmp_path/'plan', capsule_staging_directory=scratch)
    assert not list(scratch.iterdir())


def test_cli_forwards_explicit_capsule_staging(tmp_path):
    import json
    from research_workflows.cli import main
    spec = request(tmp_path); path = tmp_path/'REQUEST.json'
    path.write_text(json.dumps(spec))
    scratch = tmp_path/'scratch'; scratch.mkdir()
    assert main(['plan', '--request', str(path), '--out', str(tmp_path/'plan'),
                 '--capsule-staging-directory', str(scratch)]) == 0
    assert load(tmp_path/'plan/PLAN_RECEIPT.json')['capsule_staging']['directory'] == str(scratch)
    assert not list(scratch.iterdir())
