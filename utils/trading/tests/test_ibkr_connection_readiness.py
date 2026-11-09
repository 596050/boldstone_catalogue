import socket

from utils.ibkr.connection_readiness import DEFAULT_PORTS, SCHEMA, build_connection_readiness_report, probe_socket


class _DummySocket:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_probe_socket_reports_reachable(monkeypatch) -> None:
    def fake_create_connection(address, timeout):
        assert address == ("127.0.0.1", 4002)
        assert timeout == 0.25
        return _DummySocket()

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)

    result = probe_socket("127.0.0.1", 4002, timeout_seconds=0.25)

    assert result["reachable"] is True
    assert result["error_type"] is None


def test_probe_socket_reports_refused(monkeypatch) -> None:
    def fake_create_connection(address, timeout):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)

    result = probe_socket("127.0.0.1", 4002, timeout_seconds=0.25)

    assert result["reachable"] is False
    assert result["error_type"] == "ConnectionRefusedError"


def test_connection_readiness_blocks_when_no_socket_reachable(monkeypatch) -> None:
    def fake_create_connection(address, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)

    report = build_connection_readiness_report(
        host="127.0.0.1",
        ports=(4002, 7497, 4001),
        timeout_seconds=0.25,
        generated_at_utc="2026-06-29T12:00:00Z",
        jts_launcher_log=None,
        include_process_snapshot=False,
    )

    assert report["schema"] == SCHEMA
    assert report["any_api_socket_reachable"] is False
    assert report["paper_api_socket_reachable"] is False
    assert "ibkr_any_api_socket_not_reachable" in report["promotion_blockers"]
    assert "ibkr_paper_api_socket_not_reachable" in report["promotion_blockers"]


def test_connection_readiness_requires_paper_socket_for_paper_validation(monkeypatch) -> None:
    def fake_create_connection(address, timeout):
        if address[1] == 4001:
            return _DummySocket()
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)

    report = build_connection_readiness_report(
        host="127.0.0.1",
        ports=(4002, 7497, 4001),
        timeout_seconds=0.25,
        generated_at_utc="2026-06-29T12:00:00Z",
        jts_launcher_log=None,
        include_process_snapshot=False,
    )

    assert report["any_api_socket_reachable"] is True
    assert report["paper_api_socket_reachable"] is False
    assert report["connection_ready_for_capture"] is True
    assert "ibkr_any_api_socket_not_reachable" not in report["promotion_blockers"]
    assert "ibkr_paper_api_socket_not_reachable" in report["promotion_blockers"]


def test_connection_readiness_clears_when_paper_socket_reachable(monkeypatch) -> None:
    def fake_create_connection(address, timeout):
        if address[1] == 4002:
            return _DummySocket()
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)

    report = build_connection_readiness_report(
        host="127.0.0.1",
        ports=(4002, 7497, 4001),
        timeout_seconds=0.25,
        generated_at_utc="2026-06-29T12:00:00Z",
        jts_launcher_log=None,
        include_process_snapshot=False,
    )

    assert report["any_api_socket_reachable"] is True
    assert report["paper_api_socket_reachable"] is True
    assert report["promotion_blockers"] == []


def test_default_ports_include_tws_live_port() -> None:
    assert DEFAULT_PORTS == (4002, 7497, 4001, 7496)


def test_connection_readiness_records_recent_auth_failure(monkeypatch, tmp_path) -> None:
    def fake_create_connection(address, timeout):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    log = tmp_path / "launcher.log"
    log.write_text(
        "\n".join(
            [
                "2026-06-30 00:53:00.000 INFO harmless",
                "2026-06-30 00:54:40.123 ERROR Authorization failed: Invalid username or password",
            ]
        )
    )

    report = build_connection_readiness_report(
        host="127.0.0.1",
        ports=(4002,),
        timeout_seconds=0.25,
        generated_at_utc="2026-06-29T12:00:00Z",
        jts_launcher_log=log,
        include_process_snapshot=False,
    )

    assert "ibkr_gateway_recent_auth_failure" in report["promotion_blockers"]
    assert report["recent_gateway_auth_failure_blocking"] is True
    assert report["recent_gateway_auth_failures"][0]["timestamp"] == "2026-06-30 00:54:40.123"


def test_connection_readiness_auth_failure_is_diagnostic_after_socket_recovers(
    monkeypatch, tmp_path
) -> None:
    def fake_create_connection(address, timeout):
        if address[1] == 4002:
            return _DummySocket()
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    log = tmp_path / "launcher.log"
    log.write_text(
        "2026-06-30 00:54:40.123 ERROR Authorization failed: Invalid username or password\n"
    )

    report = build_connection_readiness_report(
        host="127.0.0.1",
        ports=(4002,),
        timeout_seconds=0.25,
        generated_at_utc="2026-06-29T12:00:00Z",
        jts_launcher_log=log,
        include_process_snapshot=False,
    )

    assert report["any_api_socket_reachable"] is True
    assert report["paper_api_socket_reachable"] is True
    assert report["connection_ready_for_capture"] is True
    assert report["recent_gateway_auth_failures"][0]["timestamp"] == "2026-06-30 00:54:40.123"
    assert report["recent_gateway_auth_failure_blocking"] is False
    assert "ibkr_gateway_recent_auth_failure" not in report["promotion_blockers"]


def test_connection_readiness_records_process_with_closed_listener(monkeypatch) -> None:
    def fake_create_connection(address, timeout):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)

    def fake_collect_processes():
        return [{"pid": 123, "elapsed": "01:00", "command": "IB Gateway"}]

    monkeypatch.setattr(
        "utils.ibkr.connection_readiness._collect_ibkr_processes",
        fake_collect_processes,
    )

    report = build_connection_readiness_report(
        host="127.0.0.1",
        ports=(4002,),
        timeout_seconds=0.25,
        generated_at_utc="2026-06-29T12:00:00Z",
        jts_launcher_log=None,
    )

    assert report["ibkr_process_count"] == 1
    assert "ibkr_process_present_but_api_listener_closed" in report["promotion_blockers"]
