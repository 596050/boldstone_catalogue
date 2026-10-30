import copy
import datetime as dt
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request

import pytest
from conftest import DummyVault

from searchkit.artifacts import campaign_url, generate
from searchkit.auth import SCOPES, GoogleToken, Vault, authorize_google
from searchkit.cli import audit, main
from searchkit.core import ToolkitError, redact
from searchkit.google import Google, lead_audience
from searchkit.http import HTTP, APIError, NoRedirects
from searchkit.reports import gsc_summary, periods
from searchkit.search import Bing, Cloudflare, IndexNow
from searchkit.yandex import Yandex


class GA4Server:
    def __init__(self):
        self.prop = {
            "name": "properties/456",
            "account": "accounts/123",
            "displayName": "Example",
            "timeZone": "Europe/London",
            "currencyCode": "GBP",
        }
        self.streams = [
            {
                "name": "properties/456/dataStreams/789",
                "webStreamData": {
                    "defaultUri": "https://example.com/",
                    "measurementId": "G-EXAMPLE",
                },
            }
        ]
        self.retention = {"eventDataRetention": "TWO_MONTHS"}
        self.events = []
        self.dimensions = []
        self.calls = []

    def __call__(self, method, url, body=None, **kwargs):
        self.calls.append((method, url, copy.deepcopy(body)))
        path = urllib.parse.urlsplit(url).path
        if path == "/v1beta/properties/456":
            if method == "PATCH":
                self.prop.update(body)
            return {"data": copy.deepcopy(self.prop), "http_status": 200}
        if path.endswith("/dataStreams"):
            return {"data": {"dataStreams": copy.deepcopy(self.streams)}, "http_status": 200}
        if path.endswith("/dataRetentionSettings"):
            if method == "PATCH":
                self.retention.update(body)
            return {"data": copy.deepcopy(self.retention), "http_status": 200}
        for suffix, field, collection in [
            ("keyEvents", "keyEvents", self.events),
            ("customDimensions", "customDimensions", self.dimensions),
        ]:
            if path.endswith("/" + suffix):
                if method == "POST":
                    item = {
                        "name": "properties/456/" + suffix + "/" + str(len(collection) + 1),
                        **body,
                    }
                    collection.append(item)
                    return {"data": copy.deepcopy(item), "http_status": 200}
                return {"data": {field: copy.deepcopy(collection)}, "http_status": 200}
            for item in collection:
                if path.endswith("/" + item["name"]):
                    return {"data": copy.deepcopy(item), "http_status": 200}
        raise AssertionError((method, url, body))


def test_ga4_setup_repeated_apply_does_not_duplicate(profile, receipt):
    server = GA4Server()
    google = Google(profile, HTTP(transport=server), DummyVault(profile), receipt)
    google.setup_ga4()
    writes = [c for c in server.calls if c[0] in ["POST", "PATCH"]]
    assert len(server.events) == 1 and len(server.dimensions) == 1
    assert server.events[0]["countingMethod"] == "ONCE_PER_EVENT"
    assert server.retention["eventDataRetention"] == "FOURTEEN_MONTHS"
    server.calls.clear()
    google.setup_ga4()
    assert not [c for c in server.calls if c[0] in ["POST", "PATCH", "PUT"]]
    assert writes and profile.state()["ga4_measurement_id"] == "G-EXAMPLE"
    assert any(s["status"] == "verified" for s in receipt.data["steps"])


@pytest.mark.parametrize(
    "change,reason",
    [
        ("account", "identity mismatch"),
        ("host", "does not match"),
        ("timezone", "timezone/currency differ"),
        ("duplicate", "Pinned GA4 stream"),
    ],
)
def test_ga4_rejects_wrong_target_before_mutation(profile, receipt, change, reason):
    server = GA4Server()
    if change == "account":
        server.prop["account"] = "accounts/999"
    elif change == "host":
        server.streams[0]["webStreamData"]["defaultUri"] = "https://elsewhere.example/"
    elif change == "timezone":
        server.prop["timeZone"] = "Etc/GMT"
    else:
        server.streams.append(copy.deepcopy(server.streams[0]))
    with pytest.raises(ToolkitError, match=reason):
        Google(profile, HTTP(transport=server), DummyVault(profile), receipt).setup_ga4()
    assert not [c for c in server.calls if c[0] != "GET"]


def test_readonly_grant_cannot_write(profile, receipt):
    vault = DummyVault(profile)
    vault.values["google"]["scopes"] = SCOPES["report"]
    server = GA4Server()
    with pytest.raises(ToolkitError, match="lacks"):
        Google(profile, HTTP(transport=server), vault, receipt).setup_ga4()
    assert not [c for c in server.calls if c[0] != "GET"]


def test_dimension_conflicting_scope_is_rejected(profile, receipt):
    server = GA4Server()
    server.retention["eventDataRetention"] = "FOURTEEN_MONTHS"
    server.events = [{"name": "properties/456/keyEvents/1", **profile.data["ga4"]["key_events"][0]}]
    server.dimensions = [{"parameterName": "form_name", "scope": "USER"}]
    with pytest.raises(ToolkitError, match="conflicting scope"):
        Google(profile, HTTP(transport=server), DummyVault(profile), receipt).setup_ga4()
    assert not [c for c in server.calls if c[0] != "GET"]


def test_admin_pagination_and_repeated_cursor_failure(profile, receipt):
    def transport(method, url, **kwargs):
        return {
            "data": {
                "things": [1] if "pageToken" not in url else [2],
                **({"nextPageToken": "second"} if "pageToken" not in url else {}),
            }
        }

    google = Google(profile, HTTP(transport=transport), DummyVault(profile), receipt)
    assert google.pages("https://analyticsadmin.googleapis.com/v1beta/things", "things") == [1, 2]
    google.http.transport = lambda *a, **k: {"data": {"things": [], "nextPageToken": "same"}}
    with pytest.raises(ToolkitError, match="repeated"):
        google.pages("https://analyticsadmin.googleapis.com/v1beta/things", "things")


def test_data_report_paginates_with_public_hostname(profile, receipt):
    calls = []

    def transport(method, url, body=None, **kwargs):
        calls.append(body)
        offset = int(body["offset"])
        return {
            "data": {
                "rowCount": 3,
                "rows": [
                    {"metricValues": [{"value": str(x)}]} for x in ([1, 2] if not offset else [3])
                ],
            }
        }

    result = Google(profile, HTTP(transport=transport), DummyVault(profile), receipt).ga4_report(
        "2026-09-01", "2026-09-30", [], ["sessions"]
    )
    assert result["rowCount"] == 3 and [c["offset"] for c in calls] == ["0", "2"]
    assert (
        calls[0]["dimensionFilter"]["andGroup"]["expressions"][0]["filter"]["stringFilter"]["value"]
        == "example.com"
    )


def test_gsc_url_encoding_and_incomplete_owner_blocks_sitemap(profile, receipt):
    calls = []

    def transport(method, url, **kwargs):
        calls.append((method, url))
        return {
            "data": {
                "siteEntry": [
                    {"siteUrl": "sc-domain:example.com", "permissionLevel": "siteUnverifiedUser"}
                ]
            }
        }

    with pytest.raises(ToolkitError, match="ownership"):
        Google(profile, HTTP(transport=transport), DummyVault(profile), receipt).setup_gsc()
    assert "%3Aexample.com" in calls[0][1]
    assert not any("sitemaps" in c[1] for c in calls)


def test_gsc_top_row_pagination(profile, receipt):
    offsets = []

    def transport(method, url, body=None, **kwargs):
        offsets.append(body["startRow"])
        return {"data": {"rows": [{"clicks": 1}] * (25000 if body["startRow"] == 0 else 1)}}

    result = Google(profile, HTTP(transport=transport), DummyVault(profile), receipt).search_report(
        "2026-09-01", "2026-09-30", ["query"]
    )
    assert offsets == [0, 25000] and len(result["rows"]) == 25001
    assert "anonymized" in result["completeness"]


def test_audience_same_event_scope_has_and_of_ors():
    audience = lead_audience("example.com")
    clause = audience["filterClauses"][0]["simpleFilter"]
    assert clause["scope"] == "AUDIENCE_FILTER_SCOPE_WITHIN_SAME_EVENT"
    groups = clause["filterExpression"]["andGroup"]["filterExpressions"]
    assert len(groups) == 2 and all("orGroup" in x for x in groups)


def test_bing_add_verify_sitemap_workflow_is_idempotent(profile, receipt):
    sites, feeds, writes = [], [], []

    def transport(method, url, body=None, **kwargs):
        name = urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]
        if name == "GetUserSites":
            data = copy.deepcopy(sites)
        elif name == "AddSite":
            writes.append(name)
            sites.append(
                {"Url": profile.url, "IsVerified": False, "AuthenticationCode": "TEST-CODE"}
            )
            data = None
        elif name == "VerifySite":
            sites[0]["IsVerified"] = True
            data = True
        elif name == "GetFeeds":
            data = copy.deepcopy(feeds)
        elif name == "SubmitFeed":
            writes.append(name)
            feeds.append({"Url": body["feedUrl"], "Status": "Pending"})
            data = None
        else:
            raise AssertionError(name)
        return {"data": {"d": data}}

    adapter = Bing(profile, HTTP(transport=transport), DummyVault(profile), receipt)
    with pytest.raises(ToolkitError, match="ownership"):
        adapter.setup()
    adapter.prepare_verification()
    adapter.confirm_verification()
    adapter.setup()
    adapter.setup()
    assert writes == ["AddSite", "SubmitFeed"]
    assert feeds[0]["Status"] == "Pending"  # Submission acceptance is not crawl success.


def test_indexnow_rejects_foreign_host_before_fetch(profile, receipt):
    profile.save_state(indexnow_key="a" * 32)
    http = HTTP(transport=lambda *a, **k: pytest.fail("No network request expected"))
    with pytest.raises(ToolkitError, match="outside"):
        IndexNow(profile, http, receipt).submit(["https://elsewhere.example/page"])


@pytest.mark.parametrize("proof,accepted", [("wrong", False), ("a" * 32, True)])
def test_indexnow_key_check_and_202_pending(profile, receipt, proof, accepted):
    profile.save_state(indexnow_key="a" * 32)
    calls = []

    def transport(method, url, **kwargs):
        calls.append(method)
        return (
            {"text": proof, "http_status": 200}
            if method == "GET"
            else {"text": "", "http_status": 202}
        )

    adapter = IndexNow(profile, HTTP(transport=transport), receipt)
    if accepted:
        result = adapter.submit([profile.url + "new", profile.url + "new"])
        assert (
            result["http_status"] == 202
            and result["submitted_urls"] == 1
            and result["indexed"] == "not established"
        )
    else:
        with pytest.raises(ToolkitError, match="contents"):
            adapter.submit([profile.url])
        assert calls == ["GET"]


def test_wrong_cloudflare_zone_cannot_change_dns(profile, receipt):
    profile.data["cloudflare"]["zone_id"] = "a" * 32
    calls = []

    def transport(method, url, **kwargs):
        calls.append(method)
        return {"data": {"success": True, "result": {"name": "wrong.example"}}}

    with pytest.raises(ToolkitError, match="mismatch"):
        Cloudflare(
            profile, HTTP(transport=transport), DummyVault(profile), receipt
        ).deploy_google_txt()
    assert calls == ["GET"]


def test_private_credentials_refuse_world_readable_file(profile):
    vault = Vault(profile, "file")
    vault.set("google", {"access_token": "TEST-PRIVATE"})
    path = vault._path("google")
    assert path.stat().st_mode & 0o777 == 0o600
    os.chmod(path, 0o644)
    with pytest.raises(ToolkitError, match="accessible"):
        vault.get("google")


def test_scopes_refreshed_without_expanding_grant(profile):
    vault = DummyVault(profile)
    vault.values["google"].update(
        expires_at=0, refresh_token="TEST-REFRESH", client_id="test", client_secret="TEST-SECRET"
    )
    calls = []

    def transport(method, url, form=None, **kwargs):
        calls.append(form)
        return {"data": {"access_token": "TEST-NEW", "expires_in": 3600}}

    headers = GoogleToken(vault, HTTP(transport=transport)).headers(SCOPES["setup"][3])
    assert headers["Authorization"] == "Bearer TEST-NEW"
    assert calls[0]["grant_type"] == "refresh_token" and "scope" not in calls[0]


def test_error_redaction_and_redirect_do_not_forward_credentials():
    http = HTTP()
    http.secrets.append("TEST-PRIVATE")

    class Broken:
        def open(self, *args, **kwargs):
            raise urllib.error.HTTPError(
                "https://api.example/?apikey=TEST-PRIVATE",
                403,
                "Denied",
                {},
                io.BytesIO(b"request failed with TEST-PRIVATE"),
            )

    http.opener = Broken()
    with pytest.raises(APIError) as caught:
        http.call("GET", "https://api.example/?apikey=TEST-PRIVATE")
    assert "TEST-PRIVATE" not in str(caught.value)
    with pytest.raises(ToolkitError, match="redirect"):
        NoRedirects().redirect_request(
            urllib.request.Request("https://api.example/"),
            None,
            302,
            "",
            {},
            "https://other.example/",
        )
    assert redact({"refresh_token": "TEST-PRIVATE"})["refresh_token"] == "[REDACTED]"


@pytest.mark.parametrize("actual_email", ["owner@example.com", "wrong@example.com"])
def test_oauth_pkce_state_and_identity_before_save(
    profile, tmp_path, monkeypatch, capsys, actual_email
):
    client = tmp_path / "desktop.json"
    client.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "TEST.apps.googleusercontent.com",
                    "client_secret": "TEST-CLIENT-SECRET",
                }
            }
        )
    )
    profile.data["google"]["expected_email"] = "owner@example.com"
    vault = DummyVault(profile)
    vault.values.pop("google")
    captured = {}
    import threading

    def browser(url):
        args = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        captured.update(args)

        def callback():
            bad = args["redirect_uri"][0] + "?state=wrong&code=TEST-CODE"
            with pytest.raises(urllib.error.HTTPError):
                urllib.request.urlopen(bad)
            good = (
                args["redirect_uri"][0]
                + "?"
                + urllib.parse.urlencode({"state": args["state"][0], "code": "TEST-CODE"})
            )
            urllib.request.urlopen(good).close()

        threading.Thread(target=callback, daemon=True).start()

    monkeypatch.setattr("searchkit.auth.webbrowser.open", browser)

    def transport(method, url, form=None, **kwargs):
        if url.endswith("/token"):
            assert form["code_verifier"] not in capsys.readouterr().out
            import base64
            import hashlib

            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest())
                .decode()
                .rstrip("=")
            )
            assert challenge == captured["code_challenge"][0]
            return {
                "data": {
                    "access_token": "TEST-ACCESS",
                    "refresh_token": "TEST-REFRESH",
                    "scope": " ".join(SCOPES["setup"]),
                }
            }
        return {"data": {"email": actual_email, "email_verified": True}}

    if actual_email != "owner@example.com":
        with pytest.raises(ToolkitError, match="identity"):
            authorize_google(profile, vault, HTTP(transport=transport), client, "setup", timeout=3)
        assert "google" not in vault.values
        return
    result = authorize_google(profile, vault, HTTP(transport=transport), client, "setup", timeout=3)
    assert (
        result["email"] == "owner@example.com"
        and vault.values["google"]["refresh_token"] == "TEST-REFRESH"
    )


def test_profile_id_cannot_retarget_existing_state(profile):
    profile.save_state(ga4_property_id="456")
    profile.url = "https://elsewhere.example/"
    with pytest.raises(ToolkitError, match="different website"):
        profile.state()


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("weekly", (("2026-10-05", "2026-10-11"), ("2026-09-28", "2026-10-04"))),
        ("monthly", (("2026-09-01", "2026-09-30"), ("2026-08-01", "2026-08-31"))),
    ],
)
def test_completed_reporting_periods(mode, expected):
    assert periods(mode, dt.date(2026, 10, 15)) == expected


def test_summary_uses_impressions_not_mean_of_row_ctr():
    totals = gsc_summary(
        [
            {"clicks": 1, "impressions": 1, "position": 1},
            {"clicks": 1, "impressions": 99, "position": 9},
        ]
    )
    assert totals["ctr"] == 0.02 and totals["position"] == 8.92


def test_generate_does_not_duplicate_native_ga4_and_escapes_jsonld(profile, tmp_path):
    profile.data["ga4"].update(native_installation=True, measurement_id="G-EXAMPLE")
    profile.data["organization"]["name"] = "Example </script>"
    result = generate(profile, tmp_path / "generated")
    root = tmp_path / "generated" / profile.id
    assert "ga4-consent-loader.html" not in result["files"]
    assert (
        "</script>"
        not in (root / "organization-schema.html").read_text().split("\n", 1)[1].rsplit("\n", 2)[0]
    )
    assert not result["published"]


def test_campaign_links_preserve_existing_query():
    url = campaign_url("https://example.com/?product=1", "Instagram", "Studio_News")
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert query["product"] == ["1"] and query["utm_source"] == ["instagram"]


def test_audit_distinguishes_page_urls_from_image_locations(profile):
    xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"><url><loc>https://example.com/</loc><image:image><image:loc>https://example.com/image.jpg</image:loc></image:image></url></urlset>'

    def transport(method, url, **kwargs):
        return {"http_status": 200, "text": xml if url.endswith(".xml") else ""}

    result = audit(profile, HTTP(transport=transport))
    sitemap = result["checks"][profile.url + "sitemap.xml"]
    assert sitemap["page_url_count"] == 1 and sitemap["all_xml_location_count"] == 2
    assert not result["collection_or_consent_verified"]


def test_setup_is_no_network_without_apply(profile, monkeypatch, capsys):
    monkeypatch.setattr(HTTP, "call", lambda *a, **k: pytest.fail("Preview cannot access network"))
    assert main(["--profile", str(profile.path), "setup"]) == 0
    assert json.loads(capsys.readouterr().out)["live_changes"] is False


def test_yandex_pending_verification_does_not_claim_success(profile, receipt):
    def transport(method, url, **kwargs):
        if url.endswith("/user"):
            data = {"user_id": 7}
        elif url.endswith("/hosts"):
            data = {
                "hosts": [
                    {
                        "host_id": "https:example.com:443",
                        "ascii_host_url": profile.url,
                        "verified": False,
                    }
                ]
            }
        else:
            data = {"verification_state": "IN_PROGRESS"}
        return {"data": data}

    adapter = Yandex(profile, HTTP(transport=transport), DummyVault(profile), receipt)
    result = adapter.confirm_verification()
    assert not result["verified"] and result["verification_state"] == "IN_PROGRESS"


def test_receipt_keeps_write_intent_on_unknown_outcome(profile, receipt):
    def transport(*args, **kwargs):
        raise ToolkitError("Network outcome unknown")

    google = Google(profile, HTTP(transport=transport), DummyVault(profile), receipt)
    with pytest.raises(ToolkitError):
        google.write(
            "POST",
            "https://analyticsadmin.googleapis.com/v1beta/properties/456/customDimensions",
            {},
            "dimension",
        )
    saved = json.loads(receipt.path.read_text())
    assert saved["steps"][0]["status"] == "attempting"
    assert all(s["status"] != "accepted" for s in saved["steps"])
