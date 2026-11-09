"""Atomic-write races must not fail live resource monitors or weaken seals."""

import os
from pathlib import Path

import pytest

from lib.live_files import live_tree_bytes


def test_live_accounting_tolerates_disappearing_temporary_file(tmp_path, monkeypatch):
    (tmp_path / "kept").write_bytes(b"1234")
    (tmp_path / "transient.tmp").write_bytes(b"temporary")
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        if path.name == "transient.tmp":
            raise FileNotFoundError(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)
    assert live_tree_bytes(tmp_path) == 4


def test_live_accounting_does_not_hide_permission_or_root_errors(tmp_path, monkeypatch):
    (tmp_path / "denied").write_bytes(b"1234")
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        if path.name == "denied":
            raise PermissionError(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(PermissionError):
        live_tree_bytes(tmp_path)
    with pytest.raises(FileNotFoundError):
        live_tree_bytes(tmp_path / "absent")


def test_input_exclusion_cannot_hide_artifacts_named_blobs(tmp_path):
    (tmp_path / "blobs").mkdir()
    (tmp_path / "blobs/input").write_bytes(b"input")
    (tmp_path / "artifacts/blobs").mkdir(parents=True)
    (tmp_path / "artifacts/blobs/payload").write_bytes(b"payload")
    assert live_tree_bytes(tmp_path, exclude_root_dirs={"blobs"}) == 7
    assert live_tree_bytes(tmp_path) == 12


@pytest.mark.skipif(os.name == "nt", reason="symlink creation may require privileges")
def test_live_accounting_never_follows_symlinks(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "value").write_bytes(b"1234")
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "linked-file").symlink_to(source / "value")
    (tree / "linked-directory").symlink_to(source, target_is_directory=True)
    assert live_tree_bytes(tree) == 0
