"""Verifies the *_chunks/ exclusion filter used by fleet collect rsync.

The filter pattern is duplicated across:
  - fleet.py:565 (PowerShell-side manifest filter)
  - clean_kenne_chunks.py (cleanup target identification)
  - migrate_*.sh (rsync --exclude flags)

This test pins the regex behaviour so refactors don't subtly change it.
"""
import re

# The canonical exclude pattern (post-2026-06-03 fix for verify-vs-rsync mismatch)
CHUNKS_PATTERN = re.compile(r"[\\/](?:[A-Za-z0-9_]+_chunks|\.rsync-partial)([\\/]|$)")


def _excluded(path: str) -> bool:
    """Mimics the fleet.py:565 filter — True means rsync skips this path."""
    return bool(CHUNKS_PATTERN.search(path))


def test_chunks_dir_excluded():
    assert _excluded("c_emd/results/random_windows_x/aapl_rw0_chunks/chunk_0.mat")


def test_chunks_dir_at_root_excluded():
    assert _excluded("/aapl_rw0_chunks/")


def test_rsync_partial_excluded():
    assert _excluded("c_emd/results/random_windows_x/.rsync-partial/")


def test_final_mat_NOT_excluded():
    """The actual per-window .mat must NOT be filtered."""
    assert not _excluded("c_emd/results/random_windows_x/aapl_rw0_99_106.mat")


def test_summary_json_NOT_excluded():
    assert not _excluded("c_emd/results/random_windows_x/summary.json")


def test_batch_log_NOT_excluded():
    assert not _excluded("c_emd/results/random_windows_x/batch0.log")


def test_chunks_substring_in_filename_NOT_excluded():
    """A FILENAME containing 'chunks' (not a dir) must not be excluded."""
    assert not _excluded("c_emd/results/something_chunks_summary.json")


def test_chunks_dir_with_complex_name():
    """Real chunks dirs have names like '<inst>_rw<N>_<start>_<end>_chunks'."""
    assert _excluded("c_emd/results/random_windows_x/v_csv_uoa_rw4_364_371_chunks/")
    assert _excluded("c_emd/results/random_windows_x/v_csv_uoa_rw4_364_371_chunks/chunk_0001.mat")


def test_windows_path_separator():
    """Filter must also work for Windows backslash paths."""
    assert _excluded("c_emd\\results\\random_windows_x\\aapl_rw0_chunks\\chunk.mat")
    assert _excluded("c_emd\\results\\random_windows_x\\.rsync-partial\\")
