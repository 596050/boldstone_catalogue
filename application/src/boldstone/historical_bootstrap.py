#!/usr/bin/env python3
"""Offline verifier and historical-state importer for the Boldstone handover.

Standard library only. No network calls, Dropbox SDK, credentials or remote writes.
This is NOT the cleanup executor specified in the runbook.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
csv.field_size_limit(16 * 1024 * 1024)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_member(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise ValueError(f"Absolute package path rejected: {relative}")
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Package path traversal rejected: {relative}")
    return result


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"Empty or duplicate CSV header: {path.name}")
        records = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in records):
        raise ValueError(f"Malformed CSV row width: {path.name}")
    return records


def load_index(root: Path) -> list[dict[str, Any]]:
    index = json.loads((root / "blueprint/batch_index.json").read_text(encoding="utf-8"))
    if len(index) != 350 or len({row["batch_id"] for row in index}) != 350:
        raise ValueError("Expected exactly 350 unique fixed batches")
    if [row["order"] for row in index] != list(range(1, 351)):
        raise ValueError("Fixed batch ordering changed")
    for row in index:
        path = safe_member(root, row["manifest"])
        if sha256_file(path) != row["manifest_sha256"]:
            raise ValueError(f"Changed batch scope: {row['batch_id']}")
        if len(read_csv(path)) != row["item_count"]:
            raise ValueError(f"Changed item count: {row['batch_id']}")
    return index


def verify_package(root: Path) -> dict[str, Any]:
    manifest_path = root / "PACKAGE_SHA256.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest["files"]
    seen: set[str] = set()
    for item in entries:
        rel = item["path"]
        if rel in seen:
            raise ValueError(f"Duplicate checksum entry: {rel}")
        seen.add(rel)
        path = safe_member(root, rel)
        if not path.is_file():
            raise ValueError(f"Missing package file: {rel}")
        if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"Package checksum mismatch: {rel}")
    index = load_index(root)
    return {
        "outcome": "verified_offline_package",
        "checksum_files": len(entries),
        "fixed_batches": len(index),
        "batch_rows": sum(row["item_count"] for row in index),
        "remote_calls": 0,
        "boundary": "Checksums validate this package; no current Dropbox checks were made.",
    }


def primary_ids(row: dict[str, str]) -> tuple[str | None, str | None]:
    primary_keys = (
        "Target file ID",
        "Delete file ID",
        "Original Dropbox ID",
        "Dropbox file ID",
        "Dropbox folder ID",
        "Dropbox ID",
        "Approved Dropbox ID",
    )
    secondary_keys = ("Designated keeper ID", "Keep file ID", "Related original BMP ID")
    first = next((row[k] for k in primary_keys if row.get(k)), None)
    second = next((row[k] for k in secondary_keys if row.get(k)), None)
    return first, second


def init_state(root: Path, database: Path) -> dict[str, Any]:
    verified = verify_package(root)
    index = load_index(root)
    database = database.expanduser().resolve()
    for protected_directory in (
        "plan",
        "checkpoint",
        "source_archives",
        "supplemental_identity",
        "blueprint",
        "instructions",
    ):
        if database.is_relative_to((root / protected_directory).resolve()):
            raise ValueError("State database may not overwrite an immutable input directory")
    database.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidentally replacing an established local state DB.
    descriptor = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    connection = sqlite3.connect(database)
    timestamp = utc_now()
    imported_csv_rows = 0
    try:
        connection.executescript(
            Path(__file__).with_name("schema_v1.sql").read_text(encoding="utf-8")
        )
        with connection:
            connection.execute("INSERT INTO schema_meta VALUES (?,?)", ("version", "1"))
            connection.execute("INSERT INTO schema_meta VALUES (?,?)", ("imported_utc", timestamp))
            connection.execute(
                "INSERT INTO schema_meta VALUES (?,?)",
                ("remote_verification", "none_offline_import_only"),
            )
            for folder in ("plan", "checkpoint", "source_archives", "supplemental_identity"):
                for path in sorted((root / folder).rglob("*")):
                    if not path.is_file():
                        continue
                    relative = path.relative_to(root).as_posix()
                    level = (
                        "supplemental_historical_source_transcription"
                        if folder == "supplemental_identity"
                        else "preserved_historical_input"
                    )
                    connection.execute(
                        "INSERT INTO sources VALUES (?,?,?,?,?,?)",
                        (
                            relative,
                            sha256_file(path),
                            path.stat().st_size,
                            timestamp,
                            path.suffix.lower(),
                            level,
                        ),
                    )
                    if path.suffix.lower() == ".csv":
                        records = read_csv(path)
                        connection.executemany(
                            "INSERT INTO source_rows VALUES (?,?,?,?)",
                            (
                                (
                                    relative,
                                    number,
                                    hashlib.sha256(canonical(row).encode()).hexdigest(),
                                    canonical(row),
                                )
                                for number, row in enumerate(records, 1)
                            ),
                        )
                        imported_csv_rows += len(records)
            reg_path = root / "checkpoint/Boldstone_Batch_Register_Updated_First10.csv"
            saved_register = {r["Batch ID"]: r for r in read_csv(reg_path)}
            for item in index:
                saved = saved_register[item["batch_id"]]
                connection.execute(
                    """INSERT INTO batches(batch_id,original_order,workstream,family_or_scope,item_count,
                    unit,manifest_path,manifest_sha256,saved_status,saved_completed_utc,original_plan_status,
                    imported_row_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        item["batch_id"],
                        item["order"],
                        item["workstream"],
                        item["family_or_scope"],
                        item["item_count"],
                        item["unit"],
                        item["manifest"],
                        item["manifest_sha256"],
                        saved["Status"],
                        saved.get("Completed UTC") or None,
                        item["original_plan_status"],
                        canonical(saved),
                    ),
                )
                for number, row in enumerate(read_csv(safe_member(root, item["manifest"])), 1):
                    first, second = primary_ids(row)
                    payload = canonical(row)
                    connection.execute(
                        "INSERT INTO batch_members VALUES (?,?,?,?,?,?)",
                        (
                            item["batch_id"],
                            number,
                            first,
                            second,
                            hashlib.sha256(payload.encode()).hexdigest(),
                            payload,
                        ),
                    )
            baseline_rel = "plan/source_registers/Boldstone_Original_8431_ID_Census_2026-10-14.csv"
            for n, row in enumerate(read_csv(root / baseline_rel), 1):
                connection.execute(
                    "INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,1)",
                    (
                        row["Original Dropbox ID"],
                        "file",
                        row["Original family"],
                        row["Original relative path"],
                        int(row["Original bytes"]) if row["Original bytes"] else None,
                        row["Original extension"],
                        baseline_rel,
                        n,
                    ),
                )
            folder_rel = "plan/source_registers/Earlier_423_Folder_Inventory.csv"
            for n, row in enumerate(read_csv(root / folder_rel), 1):
                connection.execute(
                    "INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,1)",
                    (
                        row["Dropbox folder ID"],
                        "folder",
                        row.get("Top-level family"),
                        row.get("Original relative path"),
                        None,
                        None,
                        folder_rel,
                        n,
                    ),
                )
            jpg_rel = (
                "plan/source_registers/Boldstone_13_Historical_JPG_Replacements_2026-10-14.csv"
            )
            for n, row in enumerate(read_csv(root / jpg_rel), 1):
                connection.execute(
                    "INSERT OR IGNORE INTO assets VALUES (?,?,?,?,?,?,?,?,1)",
                    (row["Dropbox file ID"], "file", row["Family"], None, None, None, jpg_rel, n),
                )
                connection.execute(
                    """INSERT INTO lineage(edge_id,from_asset_id,to_asset_id,relation,
                  evidence_level,source_path,evidence_json) VALUES (?,?,?,?,?,?,?)""",
                    (
                        f"historical-jpg-{n:02d}",
                        row["Related original BMP ID"],
                        row["Dropbox file ID"],
                        "converted_to",
                        "historical_association_not_fresh_local_QA",
                        jpg_rel,
                        canonical(row),
                    ),
                )
            protection_rel = "checkpoint/controls/Protected_Keepers_And_Replacements.csv"
            for row in read_csv(root / protection_rel):
                connection.execute(
                    "INSERT INTO protections VALUES (?,?,?,?)",
                    (
                        row["Dropbox ID"],
                        "historical_keeper_or_replacement",
                        row["Protection reasons"],
                        protection_rel,
                    ),
                )
            for rel, kind, key in [
                (
                    "checkpoint/controls/Excluded_203_Completed_Renames.csv",
                    "do_not_replay_recorded_rename",
                    "Approved Dropbox ID",
                ),
                (
                    "checkpoint/controls/Excluded_54_Absent_Targets.csv",
                    "do_not_replay_historical_delete",
                    "Delete file ID",
                ),
            ]:
                for row in read_csv(root / rel):
                    connection.execute(
                        "INSERT INTO exclusions VALUES (?,?,?,?)",
                        (row[key], kind, rel, canonical(row)),
                    )
            hold_rel = "checkpoint/controls/Preserved_H01_Holds.csv"
            for n, row in enumerate(read_csv(root / hold_rel), 1):
                connection.execute(
                    "INSERT INTO holds VALUES (?,?,?,?,?,?,NULL)",
                    (
                        f"H01-{n:02d}",
                        row["Target file ID"],
                        "historical_connector_safety_hold",
                        "Unresolved prior block; normal owner/admin resolution required. No bypass.",
                        1,
                        hold_rel,
                    ),
                )
            metadata_rel = "checkpoint/Current_Metadata_208.csv"
            for n, row in enumerate(read_csv(root / metadata_rel), 1):
                connection.execute(
                    """INSERT INTO observations(observation_id,asset_id,observed_utc,endpoint,
                  namespace_id,path_display,name,revision,byte_size,observation_outcome,response_json,is_historical)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (
                        f"imported-first10-{n:03d}",
                        row["Dropbox ID"],
                        row["Observed UTC"],
                        "historical_connector_metadata_transcription",
                        None,
                        row.get("Current display path"),
                        row.get("Current filename"),
                        row.get("Revision"),
                        int(row["Bytes"]) if row.get("Bytes") else None,
                        "historical_metadata_observation",
                        canonical(row),
                    ),
                )
            payload = canonical(
                {
                    "verified_package": verified,
                    "imported_csv_rows": imported_csv_rows,
                    "remote_calls": 0,
                }
            )
            event_payload = canonical(
                {"event_type": "offline_import", "utc": timestamp, "payload": json.loads(payload)}
            )
            connection.execute(
                """INSERT INTO events(event_id,event_utc,entity_kind,entity_id,event_type,
                payload_json,event_hash) VALUES (?,?,?,?,?,?,?)""",
                (
                    "offline-import-" + hashlib.sha256(timestamp.encode()).hexdigest()[:20],
                    timestamp,
                    "package",
                    "Boldstone_Local_Implementation_Pack_2026-10-14",
                    "offline_import",
                    payload,
                    hashlib.sha256(event_payload.encode()).hexdigest(),
                ),
            )
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok" or connection.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Database integrity or foreign-key check failed")
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "sources",
                "source_rows",
                "assets",
                "batches",
                "batch_members",
                "protections",
                "exclusions",
                "holds",
                "observations",
                "lineage",
                "operations",
                "approvals",
            )
        }
        if counts["batches"] != 350 or counts["protections"] != 1813 or counts["holds"] != 7:
            raise RuntimeError("Imported control count mismatch")
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return {
            "outcome": "historical_state_seeded_only",
            "database": str(database),
            "counts": counts,
            "remote_calls": 0,
            "warning": "No credentials, remote mutation or fresh Dropbox verification. Existing statuses remain historical.",
        }
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=ROOT, help="Extracted handover package directory"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify", help="Verify immutable package file checksums and all 350 scopes")
    listing = sub.add_parser("list", help="List preserved batch order/status; no network")
    listing.add_argument("--limit", type=int, default=350)
    show = sub.add_parser("show", help="Print one exact batch scope and saved status")
    show.add_argument("batch_id")
    init = sub.add_parser("init", help="Create a NEW local historical-state database; no network")
    init.add_argument("--db", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.root.expanduser().resolve()
        if args.command == "verify":
            output = verify_package(root)
        elif args.command == "list":
            if args.limit < 1 or args.limit > 350:
                raise ValueError("--limit must be between 1 and 350")
            output = [
                {
                    k: r[k]
                    for k in (
                        "order",
                        "batch_id",
                        "workstream",
                        "family_or_scope",
                        "item_count",
                        "saved_status",
                    )
                }
                for r in load_index(root)[: args.limit]
            ]
        elif args.command == "show":
            found = [r for r in load_index(root) if r["batch_id"] == args.batch_id]
            if not found:
                raise ValueError(f"Unknown fixed batch: {args.batch_id}")
            output = {
                "batch": found[0],
                "exact_scope": read_csv(safe_member(root, found[0]["manifest"])),
            }
        else:
            output = init_state(root, args.db)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, sqlite3.Error, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
