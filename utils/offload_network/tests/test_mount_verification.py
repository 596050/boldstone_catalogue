"""Alias ports share one read per boundary; no verification crosses boundaries."""

import pytest

from tests.test_research_workflows import worker


def test_identical_aliases_are_verified_once_per_boundary(tmp_path, worker, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "value").write_bytes(b"unchanged")
    identity = worker.workflows.objects.ingest(data)
    payload = {"workflow_mounts": [
        {"object_sha256": identity, "target": "inputs/left"},
        {"object_sha256": identity, "target": "inputs/right"},
    ]}
    original = worker.workflows.objects.get
    calls = []

    def checked(ident):
        calls.append(ident)
        return original(ident)

    monkeypatch.setattr(worker.workflows.objects, "get", checked)
    mounts = list(worker._checked_mounts(payload))
    assert calls == [identity]
    assert [target for _, target in mounts] == ["inputs/left", "inputs/right"]
    assert mounts[0][0] == mounts[1][0]
    worker.verify_extra_inputs(payload)
    assert calls == [identity, identity]
    (mounts[0][0] / "value").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="inventory|manifest"):
        worker.verify_extra_inputs(payload)
    assert calls == [identity, identity, identity]
