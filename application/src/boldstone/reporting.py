from __future__ import annotations

import csv
import html
import io
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote, urlencode

from .errors import IntegrityError
from .util import (
    atomic_write,
    canonical,
    check_no_symlinks,
    file_sha256,
    json_write,
    new_id,
    utc_now,
)


def spreadsheet_literal(value):
    value = str(value) if value is not None else ""
    return (
        "'" + value
        if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))
        else value
    )


def _metadata_links(metadata, expected_id, label):
    """Link only a named native object observed for the expected stable ID."""
    if not isinstance(metadata, dict) or not isinstance(expected_id, str):
        return None
    kind = metadata.get(".tag")
    path = metadata.get("path_display")
    name = metadata.get("name")
    if (
        kind not in ("file", "folder")
        or not expected_id.startswith("id:")
        or len(expected_id) <= 3
        or metadata.get("id") != expected_id
        or not isinstance(path, str)
        or not path.startswith("/")
        or "\\" in path
        or any(part in ("", ".", "..") for part in path.split("/")[1:])
        or any(ord(char) < 32 for char in path)
        or not isinstance(name, str)
        or path.rsplit("/", 1)[-1] != name
    ):
        return None
    base = "https://www.dropbox.com/home"
    if kind == "folder":
        links = f'<a href="{html.escape(base + quote(path, safe="/"), quote=True)}">Open folder</a>'
    else:
        parent = path.rsplit("/", 1)[0] or "/"
        folder_url = base + quote(parent, safe="/")
        file_url = folder_url + "?" + urlencode({"preview": name}, quote_via=quote)
        links = (
            f'<a href="{html.escape(file_url, quote=True)}">Open file</a> · '
            f'<a href="{html.escape(folder_url, quote=True)}">Containing folder</a>'
        )
    return (
        (expected_id, path, kind),
        f"<li>{html.escape(label)}: {html.escape(name)} — {links}</li>",
    )


def _review_navigation(row):
    seen, primary, descendants = set(), [], []

    def add(metadata, asset_id, label, destination):
        item = _metadata_links(metadata, asset_id, label)
        if item is not None and item[0] not in seen:
            seen.add(item[0])
            destination.append(item[1])

    asset_id = row.get("asset_id")
    for key, expected, label in (
        ("metadata", asset_id, "Asset"),
        ("folder", asset_id, "Folder"),
        ("target", asset_id, "Target"),
        ("keeper", row.get("keeper_id"), "Keeper"),
    ):
        add(row.get(key), expected, label, primary)
    binary = row.get("binary")
    if isinstance(binary, dict) and binary.get("checks", {}).get("post_read") == "pass":
        add(binary.get("independent_post_read"), asset_id, "Post-read file", primary)
    children = row.get("descendants")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                add(child, child.get("id"), "Descendant", descendants)
    content = "<ul>" + "".join(primary) + "</ul>" if primary else ""
    if descendants:
        content += (
            f"<details><summary>Observed descendant links ({len(descendants)})</summary><ul>"
            + "".join(descendants)
            + "</ul></details>"
        )
    return '<nav aria-label="Recorded Dropbox references">' + content + "</nav>" if content else ""


def save_review_report(state, result):
    stem = f"{result['batch_id']}-{result['attempt_id']}"
    directory = state.config.directory("reports")
    json_path = directory / (stem + ".json")
    json_write(json_path, result)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["row", "asset_id", "outcome", "details_json_literal"])
    for n, row in enumerate(result["results"], 1):
        writer.writerow(
            [
                n,
                spreadsheet_literal(row.get("asset_id")),
                spreadsheet_literal(row["outcome"]),
                spreadsheet_literal(canonical(row)),
            ]
        )
    csv_path = directory / (stem + ".csv")
    atomic_write(csv_path, output.getvalue())
    content = "<!doctype html><meta charset='utf-8'><title>Boldstone review</title>"
    content += "<style>body{font:16px system-ui;max-width:1100px;margin:3rem auto;padding:1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #ddd;padding:1rem 0}</style>"
    content += f"<h1>{html.escape(result['batch_id'])}</h1><p>{html.escape(result['objective_outcome'])}</p>"
    content += (
        "<p>Read-only review. Proposed changes applied: 0. Historical results are preserved.</p>"
        "<p>File and folder links use the metadata recorded for this review.</p>"
    )
    for n, row in enumerate(result["results"], 1):
        content += (
            f"<article><h2>Row {n}: {html.escape(row['outcome'])}</h2>"
            + _review_navigation(row)
            + f"<pre>{html.escape(json.dumps(row, indent=2, ensure_ascii=False))}</pre></article>"
        )
    html_path = directory / (stem + ".html")
    atomic_write(html_path, content)
    return {"json": str(json_path), "csv": str(csv_path), "html": str(html_path)}


def report_all(state, *, batch_id=None):
    batches = [
        dict(r)
        for r in state.conn.execute(
            "SELECT batch_id,original_order,workstream,family_or_scope,item_count,saved_status,local_objective_state FROM batches ORDER BY original_order"
        )
        if batch_id is None or r["batch_id"] == batch_id
    ]
    attempts = [
        dict(r)
        for r in state.conn.execute("SELECT * FROM attempts ORDER BY started_utc")
        if batch_id is None or r["batch_id"] == batch_id
    ]
    planned = [
        r
        for r in batches
        if r["saved_status"] == "Planned" and r["local_objective_state"] == "HISTORICAL_ONLY"
    ]
    result = {
        "created_utc": utc_now(),
        "report_operation_outcome": "REPORT_WRITTEN",
        "cleanup_objective_outcome": "INCOMPLETE_READ_ONLY_MILESTONE",
        "batches": batches,
        "attempts": attempts,
        "next_untouched_batch": planned[0]["batch_id"] if planned else None,
        "active_holds": [dict(r) for r in state.conn.execute("SELECT * FROM holds WHERE active=1")],
        "remote_mutations_by_this_version": 0,
        "native_live_tests": "NOT_RUN_UNLESS_SEPARATELY_RECORDED",
        "historical_claims_are_not_fresh_verification": True,
    }
    path = state.config.directory("reports") / (new_id("state-report") + ".json")
    json_write(path, result)
    return {
        "objective_outcome": "REPORT_WRITTEN",
        "cleanup_objective_outcome": result["cleanup_objective_outcome"],
        "report_path": str(path),
        "next_untouched_batch": result["next_untouched_batch"],
    }


def checkpoint(state):
    state.validate_events()
    destination = state.config.directory("backup") / (new_id("checkpoint") + ".zip")
    with tempfile.TemporaryDirectory(prefix=".checkpoint-", dir=destination.parent) as temporary:
        tmp = Path(temporary)
        database = state.backup(tmp / "state.sqlite3")
        with sqlite3.connect(database) as snapshot:
            snapshot.row_factory = sqlite3.Row
            ledger = "".join(
                canonical(dict(r)) + "\n"
                for r in snapshot.execute("SELECT * FROM events ORDER BY sequence")
            )
            inputs = [
                dict(r)
                for r in snapshot.execute(
                    "SELECT source_path,sha256,byte_size,evidence_level FROM sources"
                )
            ]
            evidence_rows = list(
                snapshot.execute(
                    "SELECT DISTINCT raw_evidence_path,raw_evidence_sha256 FROM observations WHERE raw_evidence_path IS NOT NULL"
                )
            )
        files = {
            "state.sqlite3": database.read_bytes(),
            "events.jsonl": ledger.encode(),
            "configuration.json": (canonical(state.config.data) + "\n").encode(),
            "historical_input_references.json": (canonical(inputs) + "\n").encode(),
        }
        for row in evidence_rows:
            path = check_no_symlinks(Path(row["raw_evidence_path"]))
            if (
                not path.is_relative_to(state.config.directory("evidence"))
                or file_sha256(path) != row["raw_evidence_sha256"]
            ):
                raise IntegrityError(
                    "Evidence file escaped storage or failed its recorded checksum"
                )
            files["evidence/" + path.name] = path.read_bytes()
        import hashlib

        manifest = {
            "created_utc": utc_now(),
            "state_authority": "SQLite; JSONL is derived from this backup",
            "historical_inputs_included": False,
            "original_image_backups_included": False,
            "independent_backup_location_verified": False,
            "files": {
                name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in files.items()
            },
        }
        files["manifest.json"] = (canonical(manifest) + "\n").encode()
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, data in files.items():
                bundle.writestr(name, data)
        atomic_write(destination, archive.getvalue())
    # Read the saved artifact, not merely its in-memory preview.
    with zipfile.ZipFile(destination) as saved:
        if saved.testzip() is not None:
            raise IntegrityError("Saved checkpoint ZIP failed CRC verification")
        for name, entry in manifest["files"].items():
            if hashlib.sha256(saved.read(name)).hexdigest() != entry["sha256"]:
                raise IntegrityError("Saved checkpoint entry failed checksum verification")
    with state.conn:
        state.event(
            "checkpoint",
            destination.name,
            "consistent_checkpoint_written",
            {"path": str(destination), "sha256": file_sha256(destination)},
        )
    return {
        "objective_outcome": "CONSISTENT_LOCAL_CHECKPOINT_VERIFIED",
        "path": str(destination),
        "sha256": file_sha256(destination),
        "files": len(manifest["files"]),
        "independent_original_file_backup_verified": False,
    }
