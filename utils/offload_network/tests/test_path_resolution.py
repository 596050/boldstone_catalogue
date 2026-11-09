"""Verifies external_base() resolution + env-var override."""
import pathlib
import pytest

from fleet.paths import (
    data_root, external_base, DEFAULT_INTO, VALID_INTO,
)


def test_default_data_root_when_no_env(monkeypatch):
    """No env → falls back to /Volumes/Untitled/offload_data."""
    monkeypatch.delenv("FAMOUS_MODEL_DATA_ROOT", raising=False)
    monkeypatch.delenv("EXTERNAL_DRIVE", raising=False)
    assert data_root() == pathlib.Path("/Volumes/Untitled/offload_data")


def test_env_override(monkeypatch, tmp_path):
    """FAMOUS_MODEL_DATA_ROOT overrides the default."""
    monkeypatch.setenv("FAMOUS_MODEL_DATA_ROOT", str(tmp_path))
    assert data_root() == tmp_path


def test_legacy_external_drive_env(monkeypatch, tmp_path):
    """EXTERNAL_DRIVE is honored as fallback (legacy compat)."""
    monkeypatch.delenv("FAMOUS_MODEL_DATA_ROOT", raising=False)
    monkeypatch.setenv("EXTERNAL_DRIVE", str(tmp_path))
    assert data_root() == tmp_path


def test_into_research_data(monkeypatch, tmp_path):
    """research_data resolves to research_data/c_emd/window_replays."""
    monkeypatch.setenv("FAMOUS_MODEL_DATA_ROOT", str(tmp_path))
    assert external_base("research_data") == tmp_path / "research_data" / "c_emd" / "window_replays"


def test_into_live_data_is_legacy_alias(monkeypatch, tmp_path):
    """live_data must resolve to the SAME path as research_data (post-reorg
    alias for back-compat with existing state.json entries)."""
    monkeypatch.setenv("FAMOUS_MODEL_DATA_ROOT", str(tmp_path))
    assert external_base("live_data") == external_base("research_data")


def test_into_external_legacy_path(monkeypatch, tmp_path):
    """external (legacy) → DATA_ROOT/c_emd/results."""
    monkeypatch.setenv("FAMOUS_MODEL_DATA_ROOT", str(tmp_path))
    assert external_base("external") == tmp_path / "c_emd" / "results"


def test_invalid_into_raises():
    """Unknown --into values must raise ValueError, not silently coerce."""
    with pytest.raises(ValueError, match="--into must be"):
        external_base("definitely-not-a-real-into-value")


def test_default_into_constant():
    """DEFAULT_INTO must be valid."""
    assert DEFAULT_INTO in VALID_INTO
