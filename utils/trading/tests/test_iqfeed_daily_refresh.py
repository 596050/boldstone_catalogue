from __future__ import annotations

from pathlib import Path

import utils.iqfeed.daily_refresh as daily_refresh
from utils.iqfeed.daily_refresh import hdt_command, parse_daily_line, refresh, sync_192_from_sources


def _daily_file(path: Path, day: str, close: str = "100.0") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '"Date","Time","Open","High","Low","Close","Volume"\n'
        f"{day},0000,99.0,101.0,98.0,{close},1234\n"
    )


def test_hdt_command_is_full_range_oldest_to_newest() -> None:
    assert hdt_command(
        "AAPL", begin="19900101", end="20260709", request_id="D000001"
    ) == "HDT,AAPL,19900101,20260709,,1,D000001,5000"


def test_parse_iqfeed_protocol_62_daily_line() -> None:
    row = parse_daily_line(
        "D000001,LH,2026-07-09,316.5300,308.1600,310.5100,316.2200,48124490,0,",
        "D000001",
    )
    assert row == ("07/09/2026", "0000", "310.5100", "316.5300", "308.1600", "316.2200", "48124490")


def test_refresh_with_no_selected_files_fails_without_opening_socket(
    tmp_path, monkeypatch
) -> None:
    def fail_connect(*_args, **_kwargs):
        raise AssertionError("an empty refresh must fail before opening IQFeed")

    monkeypatch.setattr(daily_refresh.socket, "create_connection", fail_connect)
    report_path = tmp_path / "refresh.json"
    result = refresh(
        directories=(tmp_path / "empty",),
        report_path=report_path,
        end="20260805",
        symbols={"MISSING"},
    )

    assert result["ok"] is False
    assert result["selected_symbols"] == 0
    assert any(row["symbol"] == "MISSING" for row in result["errors"])
    assert report_path.exists()


def test_sync_192_requires_exact_current_source_universe(tmp_path) -> None:
    source_a = tmp_path / "a"
    source_b = tmp_path / "b"
    target = tmp_path / "target"
    _daily_file(source_a / "AAA.txt", "08/05/2026", "101.0")
    _daily_file(source_b / "BBB.txt", "08/05/2026", "102.0")
    _daily_file(target / "AAA.txt", "08/04/2026", "91.0")
    _daily_file(target / "BBB.txt", "08/04/2026", "92.0")

    result = sync_192_from_sources(
        source_directories=(source_a, source_b),
        target_directory=target,
        report_path=tmp_path / "sync.json",
        expected_end="20260805",
    )

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert result["synced"] == 2
    assert (target / "AAA.txt").read_text() == (source_a / "AAA.txt").read_text()
    assert (target / "BBB.txt").read_text() == (source_b / "BBB.txt").read_text()


def test_sync_192_stale_source_fails_closed_without_touching_targets(tmp_path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    _daily_file(source / "AAA.txt", "08/04/2026", "101.0")
    _daily_file(target / "AAA.txt", "08/03/2026", "91.0")
    before = (target / "AAA.txt").read_text()

    result = sync_192_from_sources(
        source_directories=(source,),
        target_directory=target,
        report_path=tmp_path / "sync.json",
        expected_end="20260805",
    )

    assert result["ok"] is False
    assert result["synced"] == 0
    assert "latest=08/04/2026" in str(result["errors"])
    assert (target / "AAA.txt").read_text() == before


def test_sync_192_duplicate_source_symbol_fails_closed(tmp_path) -> None:
    source_a = tmp_path / "a"
    source_b = tmp_path / "b"
    target = tmp_path / "target"
    _daily_file(source_a / "AAA.txt", "08/05/2026", "101.0")
    _daily_file(source_b / "AAA.txt", "08/05/2026", "102.0")
    _daily_file(target / "AAA.txt", "08/04/2026", "91.0")
    before = (target / "AAA.txt").read_text()

    result = sync_192_from_sources(
        source_directories=(source_a, source_b),
        target_directory=target,
        report_path=tmp_path / "sync.json",
        expected_end="20260805",
    )

    assert result["ok"] is False
    assert "duplicate source files" in str(result["errors"])
    assert (target / "AAA.txt").read_text() == before


def test_sync_192_rolls_back_targets_if_a_replacement_fails(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    _daily_file(source / "AAA.txt", "08/05/2026", "101.0")
    _daily_file(source / "BBB.txt", "08/05/2026", "102.0")
    _daily_file(target / "AAA.txt", "08/04/2026", "91.0")
    _daily_file(target / "BBB.txt", "08/04/2026", "92.0")
    before = {path.name: path.read_text() for path in target.glob("*.txt")}
    original_replace = Path.replace

    def fail_second_target_replace(self, destination):
        destination = Path(destination)
        if destination == target / "BBB.txt":
            raise OSError("simulated replacement failure")
        return original_replace(self, destination)

    monkeypatch.setattr(Path, "replace", fail_second_target_replace)
    result = sync_192_from_sources(
        source_directories=(source,),
        target_directory=target,
        report_path=tmp_path / "sync.json",
        expected_end="20260805",
    )

    assert result["ok"] is False
    assert result["synced"] == 0
    assert {path.name: path.read_text() for path in target.glob("*.txt")} == before


def test_main_does_not_sync_192_after_failed_refresh(monkeypatch) -> None:
    monkeypatch.setattr(
        daily_refresh,
        "refresh",
        lambda **_kwargs: {"ok": False, "symbols": [], "errors": [{"error": "failed"}]},
    )

    def fail_sync(**_kwargs):
        raise AssertionError("sync must not run after a failed source refresh")

    monkeypatch.setattr(daily_refresh, "sync_192_from_sources", fail_sync)
    assert daily_refresh.main([]) == 1
