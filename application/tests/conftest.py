from __future__ import annotations

import csv
import io
import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from boldstone.config import initialize_config
from boldstone.fake_adapter import FakeDropbox
from boldstone.hashing import dropbox_content_hash
from boldstone.historical_bootstrap import primary_ids
from boldstone.root import RootScope, confirm_root
from boldstone.state import State
from boldstone.util import canonical, digest, file_sha256, utc_now


def image_bytes(format="JPEG", *, mode="RGB", size=(20, 13)):
    stream = io.BytesIO()
    Image.new(mode, size, "white" if mode in ("RGB", "RGBA") else 128).save(stream, format=format)
    return stream.getvalue()


def metadata(asset_id, path, data=None, *, folder=False, revision="123456789"):
    value = {
        ".tag": "folder" if folder else "file",
        "id": asset_id,
        "path_display": path,
        "path_lower": path.lower(),
        "name": path.rsplit("/", 1)[1],
    }
    if not folder:
        value.update(
            rev=revision,
            size=len(data or b""),
            content_hash=dropbox_content_hash(io.BytesIO(data or b"")),
        )
    return value


@pytest.fixture
def local_state(tmp_path):
    tmp_path = tmp_path.resolve()
    pack = tmp_path / "pack"
    pack.mkdir()
    config = initialize_config(pack, tmp_path / "runtime").with_dropbox(
        app_key="public-test-key",
        expected_account_id="test-account",
        verified_namespace_id="111",
        verified_root_folder_id="id:ROOT",
        known_file_ids=["id:A", "id:a"],
    )
    config.save()
    from boldstone import state as state_module

    with sqlite3.connect(config.database) as conn:
        conn.executescript(Path(state_module.__file__).with_name("schema_v1.sql").read_text())
        conn.execute("INSERT INTO schema_meta VALUES ('version','1')")
    with State(config) as state, state.writer():
        state.migrate()
        yield state


@pytest.fixture
def fake():
    jpeg, bmp = image_bytes(), image_bytes("BMP")
    records = [
        metadata("id:ROOT", "/Library", folder=True),
        metadata("id:FOLDER", "/Library/Family", folder=True),
        metadata("id:A", "/Library/Family/family__dsc-001.jpg", jpeg),
        metadata("id:a", "/Library/Family/family__dsc-002.jpg", jpeg),
        metadata("id:BMP", "/Library/Family/family__source.bmp", bmp),
    ]
    contents = {
        ("id:A", "123456789"): jpeg,
        ("id:a", "123456789"): jpeg,
        ("id:BMP", "123456789"): bmp,
    }
    return FakeDropbox(records, contents)


@pytest.fixture
def scoped(local_state, fake):
    with local_state.run() as run:
        confirm_root(local_state, run, fake, local_state.config, acknowledgement="id:ROOT")
        yield local_state, run, RootScope(local_state, run, fake), fake
    assert fake.backend["writes"] == []


def add_batch(state, name, rows, *, saved="Planned"):
    path = state.config.pack / "plan/batches" / (name + ".csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    relative = path.relative_to(state.config.pack).as_posix()
    with state.conn:
        state.conn.execute(
            "INSERT INTO sources VALUES (?,?,?,?,?,?)",
            (
                relative,
                file_sha256(path),
                path.stat().st_size,
                utc_now(),
                ".csv",
                "synthetic_test_input",
            ),
        )
        state.conn.execute(
            """INSERT INTO batches(batch_id,workstream,family_or_scope,item_count,unit,
            manifest_path,manifest_sha256,saved_status,imported_row_json) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                name,
                "synthetic read-only review",
                "Family",
                len(rows),
                "IDs",
                relative,
                file_sha256(path),
                saved,
                "{}",
            ),
        )
        for n, row in enumerate(rows, 1):
            first, second = primary_ids(row)
            state.conn.execute(
                "INSERT INTO batch_members VALUES (?,?,?,?,?,?)",
                (name, n, first, second, digest(row), canonical(row)),
            )
