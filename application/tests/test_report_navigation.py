from __future__ import annotations

import json
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from conftest import add_batch, metadata

from boldstone.reporting import save_review_report
from boldstone.reviews import run_batch
from boldstone.util import new_id


class Navigation(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.links = []
        self.tags = []
        self.feed(Path(path).read_text())

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "a":
            self.links.append(dict(attrs)["href"])


def report(state, rows):
    result = {
        "batch_id": "M-DEMO",
        "attempt_id": new_id("navigation"),
        "objective_outcome": "REVIEW",
        "results": rows,
    }
    original = deepcopy(result)
    paths = save_review_report(state, result)
    assert result == original
    assert json.loads(Path(paths["json"]).read_text()) == original
    return Navigation(paths["html"])


def test_fake_metadata_review_links_observed_path_instead_of_proposed_name(scoped):
    state, run, scope, fake = scoped
    add_batch(
        state,
        "M-DEMO",
        [{"Dropbox file ID": "id:A", "Earlier detailed path": "/Old/proposed-new-name.jpg"}],
    )
    result = run_batch(state, run, "M-DEMO", scope=scope)
    before = deepcopy(result)
    paths = save_review_report(state, result)
    links = Navigation(paths["html"]).links
    assert result == before
    assert links == [
        "https://www.dropbox.com/home/Library/Family?preview=family__dsc-001.jpg",
        "https://www.dropbox.com/home/Library/Family",
    ]
    assert json.loads(Path(paths["json"]).read_text()) == before
    assert fake.backend["writes"] == []


def test_reserved_filename_characters_roundtrip_without_html_or_url_injection(local_state):
    name = 'café + ?&#% "<img src=x onerror=alert(1)>.jpg'
    parent = "/Library/Gold & Pewter"
    native = metadata("id:PHOTO", parent + "/" + name)
    parsed = report(
        local_state, [{"asset_id": "id:PHOTO", "outcome": "REVIEW", "metadata": native}]
    )
    assert len(parsed.links) == 2
    file_url, folder_url = map(urlsplit, parsed.links)
    assert file_url.scheme == folder_url.scheme == "https"
    assert file_url.netloc == folder_url.netloc == "www.dropbox.com"
    assert unquote(file_url.path) == unquote(folder_url.path) == "/home" + parent
    assert parse_qs(file_url.query) == {"preview": [name]}
    assert not file_url.fragment and not folder_url.query
    assert "img" not in parsed.tags and "script" not in parsed.tags


def test_pair_folder_and_descendant_links_remain_separate_and_deduplicated(local_state):
    target = metadata("id:TARGET", "/Library/Target/one.jpg")
    keeper = metadata("id:KEEPER", "/Library/Keeper/two.jpg")
    folder = metadata("id:FOLDER", "/Library/Family", folder=True)
    child = metadata("id:CHILD", "/Library/Family/three.jpg")
    rows = [
        {
            "asset_id": "id:TARGET",
            "keeper_id": "id:KEEPER",
            "outcome": "HELD",
            "target": target,
            "keeper": keeper,
        },
        {
            "asset_id": "id:FOLDER",
            "outcome": "PENDING",
            "metadata": folder,
            "descendants": [folder, child, child],
        },
    ]
    parsed = report(local_state, rows)
    assert len(parsed.links) == 7
    assert "https://www.dropbox.com/home/Library/Target?preview=one.jpg" in parsed.links
    assert "https://www.dropbox.com/home/Library/Keeper?preview=two.jpg" in parsed.links
    assert parsed.links.count("https://www.dropbox.com/home/Library/Family?preview=three.jpg") == 1
    assert "details" in parsed.tags


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "id:OTHER"},
        {".tag": "deleted"},
        {"path_display": "ns:111//Library/one.jpg"},
        {"path_display": "//example.invalid/one.jpg"},
        {"path_display": "/Library/../one.jpg"},
        {"path_display": "/Library\\else/one.jpg"},
        {"name": "different.jpg"},
    ],
)
def test_historical_or_inconsistent_metadata_does_not_create_a_navigation_link(
    local_state, changes
):
    native = metadata("id:PHOTO", "/Library/one.jpg")
    native.update(changes)
    parsed = report(
        local_state, [{"asset_id": "id:PHOTO", "outcome": "UNRESOLVED", "metadata": native}]
    )
    assert parsed.links == []


def test_binary_links_use_successful_independent_post_read_not_mismatched_download(local_state):
    native = metadata("id:PHOTO", "/Library/one.jpg")
    row = {
        "asset_id": "id:PHOTO",
        "outcome": "INTEGRITY_FAILED",
        "binary": {
            "checks": {"post_read": "fail"},
            "independent_post_read": native,
            "returned_metadata": metadata("id:OTHER", "/Other/two.jpg"),
        },
    }
    assert report(local_state, [row]).links == []
    row["binary"]["checks"]["post_read"] = "pass"
    assert report(local_state, [row]).links == [
        "https://www.dropbox.com/home/Library?preview=one.jpg",
        "https://www.dropbox.com/home/Library",
    ]
