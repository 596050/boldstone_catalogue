import pytest
from conftest import DummyVault
from test_workflows import GA4Server

from searchkit.core import ToolkitError
from searchkit.google import Google
from searchkit.http import HTTP


def test_matching_stream_does_not_authorize_other_website_settings(profile, receipt):
    server = GA4Server()
    server.streams.append(
        {
            "name": "properties/456/dataStreams/999",
            "webStreamData": {
                "defaultUri": "https://another.example/",
                "measurementId": "G-ANOTHER",
            },
        }
    )
    google = Google(profile, HTTP(transport=server), DummyVault(profile), receipt)
    with pytest.raises(ToolkitError, match="another site"):
        google.setup_ga4()
    assert not [c for c in server.calls if c[0] != "GET"]
    profile.data["ga4"]["allow_shared_property"] = True
    google.setup_ga4()
    before = next(s for s in receipt.data["steps"] if s["action"] == "ga4.before_retention")
    assert before["details"]["eventDataRetention"] == "TWO_MONTHS"
