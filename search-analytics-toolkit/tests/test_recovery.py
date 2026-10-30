import copy
import csv
import json
import urllib.parse
from pathlib import Path

import pytest
from conftest import DummyVault
from test_workflows import GA4Server

from searchkit.auth import Vault
from searchkit.cli import main, schedule
from searchkit.core import Profile, ToolkitError, private_json
from searchkit.google import Google
from searchkit.http import HTTP
from searchkit.reports import csv_rows
from searchkit.search import Cloudflare


def test_public_audit_archives_result_with_source_only_limits(
    profile, tmp_path, monkeypatch, capsys
):
    def public_response(self, method, url, **kwargs):
        body = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></urlset>'
        return {"http_status": 200, "text": body if url.endswith(".xml") else ""}

    monkeypatch.setattr(HTTP, "call", public_response)
    assert (
        main(["--profile", str(profile.path), "--reports-dir", str(tmp_path / "reports"), "audit"])
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    receipt_path = Path(output["receipt"])
    saved = json.loads((receipt_path.parent / "result.json").read_text())
    assert saved == output["result"]
    assert saved["source_only"] is True and saved["collection_or_consent_verified"] is False
    assert json.loads(receipt_path.read_text())["status"] == "complete"


def test_created_property_remembered_before_later_failure(profile, receipt):
    profile.data["ga4"].update(property_id=None, stream_id=None, create_property=True)
    server = GA4Server()
    server.streams.clear()
    created, failed = [], []

    def transport(method, url, body=None, **kwargs):
        path = urllib.parse.urlsplit(url).path
        if path == "/v1beta/properties" and method == "GET":
            return {"data": {"properties": []}}
        if path == "/v1beta/properties" and method == "POST":
            created.append(body)
            return {"data": copy.deepcopy(server.prop)}
        if path.endswith("/dataStreams") and method == "POST":
            if not failed:
                failed.append(True)
                raise ToolkitError("Unknown stream write outcome; inspect inventory")
            stream = {
                "name": "properties/456/dataStreams/789",
                "webStreamData": {"defaultUri": profile.url, "measurementId": "G-EXAMPLE"},
            }
            server.streams.append(stream)
            return {"data": copy.deepcopy(stream)}
        if path.endswith("/dataStreams/789"):
            return {"data": copy.deepcopy(server.streams[0])}
        return server(method, url, body, **kwargs)

    google = Google(profile, HTTP(transport=transport), DummyVault(profile), receipt)
    with pytest.raises(ToolkitError, match="Unknown"):
        google.setup_ga4()
    assert profile.state()["ga4_property_id"] == "456"
    google.setup_ga4()
    assert len(created) == 1


def test_config_rejects_duplicate_event_before_network(profile):
    profile.data["ga4"]["key_events"] *= 2
    profile.path.write_text(json.dumps(profile.data))
    with pytest.raises(ToolkitError, match="Duplicate"):
        Profile(profile.path)


def test_state_rejects_invalid_resource_id(profile):
    private_json(profile.state_path, {"website_url": profile.url, "ga4_property_id": "../other"})
    with pytest.raises(ToolkitError, match="remembered"):
        profile.state()


def test_dns_add_preserves_other_records_and_repeated_apply(profile, receipt):
    profile.data["cloudflare"]["zone_id"] = "a" * 32
    profile.save_state(
        google_verification={
            "verificationMethod": "DNS_TXT",
            "site": {"identifier": "example.com"},
            "token": "google-site-verification=TEST-PROOF",
        }
    )
    records = [{"id": "spf", "type": "TXT", "name": "example.com", "content": "v=spf1 -all"}]
    writes = []

    def transport(method, url, body=None, **kwargs):
        if "/dns_records" not in url:
            data = {"name": "example.com"}
        elif method == "POST":
            writes.append(method)
            records.append({"id": "google", **body})
            data = copy.deepcopy(records[-1])
        elif url.endswith("/google"):
            data = copy.deepcopy(records[-1])
        else:
            data = copy.deepcopy(records)
        return {"data": {"success": True, "result": data}}

    adapter = Cloudflare(profile, HTTP(transport=transport), DummyVault(profile), receipt)
    assert adapter.deploy_google_txt()["status"] == "verified"
    assert adapter.deploy_google_txt()["status"] == "already_present"
    assert writes == ["POST"] and records[0]["content"] == "v=spf1 -all"


def test_missing_credentials_is_unavailable_not_zero(profile, tmp_path, capsys):
    result = main(
        [
            "--profile",
            str(profile.path),
            "--credential-store",
            "file",
            "--reports-dir",
            str(tmp_path / "reports"),
            "report",
            "--period",
            "weekly",
        ]
    )
    assert result == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "partial" and out["result"]["gsc"] == {}
    assert all("Missing" in value for value in out["result"]["availability"].values())


def test_csv_formula_text_safe_and_numeric_values_preserved(tmp_path):
    path = tmp_path / "data.csv"
    csv_rows(path, [{"query": "=UNTRUSTED()", "change": "-12.5"}])
    row = next(csv.DictReader(path.open()))
    assert row["query"] == "'=UNTRUSTED()" and row["change"] == "-12.5"


def test_file_credentials_cannot_follow_symlink(profile, tmp_path):
    vault = Vault(profile, "file")
    vault.set("bing_api_key", {"value": "TEST-KEY"})
    path = vault._path("bing_api_key")
    elsewhere = tmp_path / "secret.json"
    elsewhere.write_text(path.read_text())
    elsewhere.chmod(0o600)
    path.unlink()
    path.symlink_to(elsewhere)
    with pytest.raises(ToolkitError, match="symlink"):
        vault.get("bing_api_key")


def test_schedule_retains_venv_interpreter_and_does_not_install(profile, tmp_path, monkeypatch):
    import argparse
    import plistlib
    from pathlib import Path

    monkeypatch.setattr("searchkit.cli.sys.executable", "/tmp/example/.venv/bin/python")
    args = argparse.Namespace(
        period="weekly",
        credential_store="file",
        reports_dir=str(tmp_path / "reports"),
        generated_dir=str(tmp_path / "generated"),
    )
    result = schedule(profile, args)
    plist = plistlib.loads(Path(result["launchd_plist"]).read_bytes())
    assert plist["ProgramArguments"][0] == "/tmp/example/.venv/bin/python"
    assert result["installed"] is False
