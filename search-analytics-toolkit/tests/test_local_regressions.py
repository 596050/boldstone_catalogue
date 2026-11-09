import copy
import csv
import json
import subprocess
from pathlib import Path

import pytest

from searchkit import cli
from searchkit.artifacts import generate
from searchkit.core import Profile, ToolkitError, canonical_url, private_json
from searchkit.http import HTTP


@pytest.mark.parametrize("field,value", [("id", []), ("website", []), ("ga4", "invalid")])
def test_malformed_profile_returns_toolkit_error(profile, field, value):
    data = copy.deepcopy(profile.data)
    data[field] = value
    profile.path.write_text(json.dumps(data))
    with pytest.raises(ToolkitError):
        Profile(profile.path)


@pytest.mark.parametrize(
    "url", [None, 42, "https://example.com:invalid/", "https://exam\nple.com/", "https://[invalid/"]
)
def test_malformed_urls_have_actionable_errors(url):
    with pytest.raises(ToolkitError):
        canonical_url(url)


@pytest.mark.parametrize("flag,value", [("--id", "Invalid ID"), ("--name", " ")])
def test_init_validates_before_creating_any_profile(tmp_path, capsys, flag, value):
    path = tmp_path / "new-site.json"
    args = {
        "--url": "https://example.com/",
        "--name": "Example",
        "--id": "example",
        "--output": str(path),
    }
    args[flag] = value
    assert cli.main(["init", *(part for pair in args.items() for part in pair)]) == 1
    assert json.loads(capsys.readouterr().err)["status"] == "failed"
    assert not path.exists()


def test_profile_creation_never_overwrites_racing_file(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text("existing")
    with pytest.raises(FileExistsError):
        private_json(path, {"id": "replacement"}, exclusive=True)
    assert path.read_text() == "existing"


@pytest.mark.parametrize("failed_check", ["settings", "indexing"])
def test_report_does_not_claim_complete_with_missing_checks(
    profile, tmp_path, monkeypatch, capsys, failed_check
):
    profile.data["bing"]["enabled"] = False
    profile.path.write_text(json.dumps(profile.data))

    class ReportingGoogle:
        def __init__(self, *args):
            pass

        def search_report(self, *args):
            return {"rows": []}

        def ga4_report(self, start, end, dimensions, metrics, **kwargs):
            return {
                "rows": [],
                "request": {
                    "dimensions": [{"name": name} for name in dimensions],
                    "metrics": [{"name": name} for name in metrics],
                },
            }

        def request(self, method, url, **kwargs):
            if url.endswith("properties/456"):
                if failed_check == "settings":
                    raise ToolkitError("Property settings unavailable")
                return {"timeZone": "Europe/London", "currencyCode": "GBP"}
            return {}

        def site_url(self):
            return "sc-domain:example.com"

        def inspect_url(self, url):
            if failed_check == "indexing":
                raise ToolkitError("URL inspection unavailable")
            return {"inspectionResult": {"indexStatusResult": {"verdict": "PASS"}}}

    monkeypatch.setattr(cli, "Google", ReportingGoogle)
    monkeypatch.setattr(HTTP, "call", lambda *a, **kw: pytest.fail("Unexpected network call"))
    result = cli.main(
        ["--profile", str(profile.path), "--reports-dir", str(tmp_path / "reports"), "report"]
    )
    output = json.loads(capsys.readouterr().out)
    assert result == 2
    assert output["status"] == "partial"
    saved = json.loads(Path(output["receipt"]).read_text())
    assert saved["status"] == "partial"
    assert any(step["status"] == "unavailable" for step in saved["steps"])


def test_documented_launcher_runs_from_another_directory(tmp_path):
    project = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [str(project / "bin/searchctl"), "--profile", str(project / "profiles/example.json"), "plan"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["live_changes"] is False


@pytest.mark.parametrize("native", [False, True])
def test_regenerating_assets_removes_obsolete_tracking_loader(profile, tmp_path, native):
    profile.data["ga4"].update(native_installation=False, measurement_id="G-EXAMPLE")
    generate(profile, tmp_path / "generated")
    root = tmp_path / "generated" / profile.id
    assert (root / "ga4-consent-loader.html").is_file()
    profile.data["ga4"].update(native_installation=native, measurement_id=None)
    result = generate(profile, tmp_path / "generated")
    assert "ga4-consent-loader.html" not in result["files"]
    assert ("analytics-installation.txt" in result["files"]) is native


def test_regenerating_manual_loader_removes_native_installation_instructions(profile, tmp_path):
    profile.data["ga4"].update(native_installation=True, measurement_id="G-EXAMPLE")
    generate(profile, tmp_path / "generated")
    profile.data["ga4"]["native_installation"] = False
    result = generate(profile, tmp_path / "generated")
    assert "analytics-installation.txt" not in result["files"]
    assert "ga4-consent-loader.html" in result["files"]


def test_generated_aeo_csv_escapes_formula_text(profile, tmp_path):
    profile.data["aeo"] = {
        "prompts": [{"id": "@command", "text": "=HYPERLINK(\"https://example.com\")"}],
        "platforms": ["+command"],
    }
    generate(profile, tmp_path / "generated")
    with (tmp_path / "generated" / profile.id / "aeo-baseline-template.csv").open() as stream:
        row = next(csv.DictReader(stream))
    assert row["prompt_id"].startswith("'@")
    assert row["prompt"].startswith("'=")
    assert row["platform"].startswith("'+")
