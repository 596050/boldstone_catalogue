import json

import pytest

from boldstone.cli import main
from boldstone.config import initialize_config, sync_roots
from boldstone.errors import Blocked, BoldstoneError


@pytest.mark.parametrize(
    "data",
    [[], None, {"local_paths": [], "dropbox": {}, "read_policy": {}}, {"local_paths": {}}],
)
def test_malformed_configuration_fails_cleanly(tmp_path, capsys, data):
    path = tmp_path.resolve() / "config.json"
    path.write_text(json.dumps(data))
    assert main(["--config", str(path), "doctor", "--read-only", "--offline"]) == 2
    result = json.loads(capsys.readouterr().err)
    assert result["objective_outcome"] == "FAILED"


def test_malformed_sync_root_metadata_blocks_configuration(tmp_path, monkeypatch):
    directory = tmp_path / ".dropbox"
    directory.mkdir()
    (directory / "info.json").write_text("[]")
    monkeypatch.setattr("boldstone.config.Path.home", lambda: tmp_path)
    with pytest.raises(Blocked, match="Cannot establish"):
        sync_roots()


@pytest.mark.parametrize(
    "field,value",
    [("max_attempts", 0), ("max_attempts", True), ("max_attempts", "4"),
     ("max_download_bytes", 0), ("max_frames", -1),
     ("max_retry_wait_seconds", -1), ("max_retry_wait_seconds", float("nan"))],
)
def test_invalid_read_policy_is_rejected_before_runtime_use(tmp_path, field, value):
    pack = tmp_path.resolve() / "pack"
    pack.mkdir()
    config = initialize_config(pack, tmp_path.resolve() / "runtime")
    config.data["read_policy"][field] = value
    with pytest.raises(BoldstoneError, match="read_policy"):
        config.validate()


def test_missing_handover_path_does_not_create_a_misleading_runtime(tmp_path):
    runtime = tmp_path.resolve() / "runtime"
    with pytest.raises(BoldstoneError, match="historical pack directory"):
        initialize_config(tmp_path.resolve() / "missing-pack", runtime)
    assert not runtime.exists()
