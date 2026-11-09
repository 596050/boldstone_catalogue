"""Pytest fixtures for the utils/offload_network test suite.

Tests run against an isolated $FLEET_DIR so they never touch the real
~/.fleet/state.json.
"""
import os
import pathlib
import sys

import pytest

# Make fleet/ + lib/ importable as top-level packages during tests
_HERE = pathlib.Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


@pytest.fixture
def isolated_fleet_dir(tmp_path, monkeypatch):
    """Redirect $FLEET_DIR + $FAMOUS_MODEL_DATA_ROOT to fresh tmpdirs.

    Reimports fleet.state so it picks up the patched env vars. Caller can
    write to the returned dir directly to seed state.json.
    """
    fleet_dir = tmp_path / ".fleet"
    fleet_dir.mkdir()
    data_root = tmp_path / "offload_data"
    data_root.mkdir()
    monkeypatch.setenv("FLEET_DIR", str(fleet_dir))
    monkeypatch.setenv("FAMOUS_MODEL_DATA_ROOT", str(data_root))
    # No module reload needed: fleet/state.py and fleet/paths.py resolve
    # $FLEET_DIR + $FAMOUS_MODEL_DATA_ROOT lazily via state_path()/data_root()
    return fleet_dir
