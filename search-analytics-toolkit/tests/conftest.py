import json

import pytest

from searchkit.core import Profile, Receipt, template


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCHKIT_STATE_DIR", str(tmp_path / "private-state"))
    data = template("https://example.com/", "Example", "test-site")
    data["ga4"].update(account_id="123", property_id="456", stream_id="789")
    data["ga4"]["custom_dimensions"] = [
        {
            "parameterName": "form_name",
            "displayName": "Form name",
            "description": "Successful enquiry route.",
            "scope": "EVENT",
        }
    ]
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(data))
    return Profile(p)


@pytest.fixture
def receipt(profile, tmp_path):
    return Receipt(profile, "test", tmp_path / "receipts")


class DummyVault:
    backend = "test"

    def __init__(self, profile, credential=None):
        import time

        from searchkit.auth import SCOPES

        self.profile = profile
        self.values = {
            "google": credential
            or {
                "access_token": "TEST-TOKEN",
                "expires_at": time.time() + 3600,
                "email": "owner@example.com",
                "scopes": SCOPES["setup"],
            },
            "bing_api_key": {"value": "TEST-BING-KEY"},
            "cloudflare_api_token": {"value": "TEST-CF-TOKEN"},
            "yandex_oauth_token": {"value": "TEST-YANDEX-TOKEN"},
        }

    def get(self, name, required=True):
        return self.values[name]

    def set(self, name, value):
        self.values[name] = value
