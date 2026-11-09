"""Local scheduling and private state must keep their identity across working directories."""
import argparse
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from searchkit.cli import schedule
from searchkit.core import Profile, ToolkitError


@pytest.mark.parametrize("raw", ["[]", "null", '"old state"', "malformed"])
def test_malformed_remembered_state_fails_cleanly_and_is_preserved(profile, raw):
    profile.state_path.parent.mkdir(parents=True)
    profile.state_path.write_text(raw)
    with pytest.raises(ToolkitError, match="state"):
        profile.state()
    with pytest.raises(ToolkitError, match="state"):
        profile.save_state(ga4_property_id="456")
    assert profile.state_path.read_text() == raw


def test_relative_private_state_does_not_follow_later_cwd_changes(profile, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEARCHKIT_STATE_DIR", "private-state")
    loaded = Profile(profile.path)
    loaded.save_state(ga4_property_id="456")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert loaded.state_path.is_absolute()
    assert loaded.state()["ga4_property_id"] == "456"
    assert not (elsewhere / "private-state").exists()


def test_generated_cron_carries_source_import_path_and_absolute_private_state(
    profile, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEARCHKIT_STATE_DIR", "relative private-state")
    loaded = Profile(profile.path)
    args = argparse.Namespace(
        period="weekly", credential_store="file", reports_dir="reports", generated_dir="generated"
    )
    result = schedule(loaded, args)
    saved = plistlib.loads(Path(result["launchd_plist"]).read_bytes())
    environment = saved["EnvironmentVariables"]
    assert environment["SEARCHKIT_STATE_DIR"] == str(loaded.state_dir)
    assert Path(environment["SEARCHKIT_STATE_DIR"]).is_absolute()
    cron = (Path(result["launchd_plist"]).parent / "weekly-cron-command.txt").read_text()
    assert shlex.quote("PYTHONPATH=" + environment["PYTHONPATH"]) in cron
    assert shlex.quote("SEARCHKIT_STATE_DIR=" + str(loaded.state_dir)) in cron
    # The source checkout must be importable by the exact standalone child
    # environment written to cron; it need not be installed into that Python.
    process_env = {**os.environ, **environment}
    process = subprocess.run(
        [sys.executable, "-m", "searchkit", "--version"],
        cwd=tmp_path,
        env=process_env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert process.stdout.strip()
