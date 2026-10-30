from __future__ import annotations

import json

from . import historical_bootstrap as historical
from .errors import IntegrityError
from .state import State
from .util import canonical, digest, file_sha256


def verify_pack(root):
    try:
        return historical.verify_package(root)
    except (OSError, ValueError, KeyError) as exc:
        raise IntegrityError(
            "Handover package validation failed", details={"reason": str(exc)}
        ) from exc


def validate_import(state, root):
    """Recheck immutable bytes and exact rows, not just aggregate control counts."""
    conn = state.conn
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise IntegrityError("State database integrity failure")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise IntegrityError("State database foreign-key failure")
    expected_sources = set()
    for folder in ("plan", "checkpoint", "source_archives", "supplemental_identity"):
        for path in sorted((root / folder).rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            historical.safe_member(root, relative)
            expected_sources.add(relative)
            source = conn.execute(
                "SELECT * FROM sources WHERE source_path=?", (relative,)
            ).fetchone()
            if (
                not source
                or source["sha256"] != file_sha256(path)
                or source["byte_size"] != path.stat().st_size
            ):
                raise IntegrityError(
                    "Imported source conflicts with handover", details={"source": relative}
                )
            if path.suffix.lower() == ".csv":
                imported = list(
                    conn.execute(
                        "SELECT row_number,row_sha256,row_json FROM source_rows WHERE source_path=? ORDER BY row_number",
                        (relative,),
                    )
                )
                expected = historical.read_csv(path)
                if len(imported) != len(expected):
                    raise IntegrityError("Historical source row count changed")
                for n, (saved, row) in enumerate(zip(imported, expected, strict=True), 1):
                    if (saved["row_number"], saved["row_sha256"], saved["row_json"]) != (
                        n,
                        digest(row),
                        canonical(row),
                    ):
                        raise IntegrityError("Historical source row content changed")
    if {r[0] for r in conn.execute("SELECT source_path FROM sources")} != expected_sources:
        raise IntegrityError("Historical source set differs from handover")
    expected_index = historical.load_index(root)
    register = {
        r["Batch ID"]: r
        for r in historical.read_csv(
            root / "checkpoint/Boldstone_Batch_Register_Updated_First10.csv"
        )
    }
    for batch in expected_index:
        saved = conn.execute(
            "SELECT * FROM batches WHERE batch_id=?", (batch["batch_id"],)
        ).fetchone()
        if (
            not saved
            or saved["manifest_sha256"] != batch["manifest_sha256"]
            or saved["original_order"] != batch["order"]
            or saved["saved_status"] != register[batch["batch_id"]]["Status"]
        ):
            raise IntegrityError("Fixed batch history changed")
        members = list(
            conn.execute(
                "SELECT * FROM batch_members WHERE batch_id=? ORDER BY row_number",
                (batch["batch_id"],),
            )
        )
        rows = historical.read_csv(root / batch["manifest"])
        if len(members) != len(rows):
            raise IntegrityError("Fixed batch membership changed")
        for n, (member, row) in enumerate(zip(members, rows, strict=True), 1):
            primary, secondary = historical.primary_ids(row)
            if (
                member["row_number"],
                member["row_sha256"],
                member["row_json"],
                member["primary_object_id"],
                member["secondary_object_id"],
            ) != (n, digest(row), canonical(row), primary, secondary):
                raise IntegrityError("Fixed batch member changed")
    protection_source = "checkpoint/controls/Protected_Keepers_And_Replacements.csv"
    expected_protections = {
        (
            row["Dropbox ID"],
            "historical_keeper_or_replacement",
            row["Protection reasons"],
            protection_source,
        )
        for row in historical.read_csv(root / protection_source)
    }
    if {
        tuple(r)
        for r in conn.execute("SELECT asset_id,protection_role,reason,source_path FROM protections")
    } != expected_protections:
        raise IntegrityError("Exact protected ID or role set changed")
    expected_exclusions = set()
    for relative, kind, key in (
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
    ):
        expected_exclusions.update(
            (row[key], kind, relative, canonical(row))
            for row in historical.read_csv(root / relative)
        )
    if {tuple(r) for r in conn.execute("SELECT * FROM exclusions")} != expected_exclusions:
        raise IntegrityError("Exact historical operation exclusion set changed")
    hold_source = "checkpoint/controls/Preserved_H01_Holds.csv"
    expected_holds = {
        (f"H01-{n:02d}", row["Target file ID"], "historical_connector_safety_hold", 1, hold_source)
        for n, row in enumerate(historical.read_csv(root / hold_source), 1)
    }
    if {
        tuple(r)
        for r in conn.execute(
            "SELECT hold_id,asset_id,hold_kind,active,source_path FROM holds WHERE hold_id LIKE 'H01-%'"
        )
    } != expected_holds:
        raise IntegrityError("Exact H01 target IDs, restrictions or active state changed")
    return {
        "sources": len(expected_sources),
        "batches": len(expected_index),
        "source_rows": conn.execute("SELECT count(*) FROM source_rows").fetchone()[0],
        "batch_members": conn.execute("SELECT count(*) FROM batch_members").fetchone()[0],
    }


def import_pack(config, pack=None):
    root = pack or config.pack
    if root != config.pack:
        raise IntegrityError("Import pack must match the configured historical input")
    verified = verify_pack(root)
    created = not config.database.exists()
    if created:
        # The bundled, reviewed importer is not executable code loaded from the input pack.
        historical.init_state(root, config.database)
    with State(config) as state, state.writer():
        counts = validate_import(state, root)
        state.migrate()
        added_provenance = 0
        with state.conn:
            for source in state.conn.execute(
                "SELECT source_path,row_number,row_json FROM source_rows"
            ):
                row = json.loads(source["row_json"])
                representation = row.get("Representation") or "preserved_historical_csv_row"
                data = (
                    source["source_path"],
                    source["row_number"],
                    row.get("Source date"),
                    row.get("Observed UTC") or row.get("Recorded UTC"),
                    row.get("Execution UTC")
                    or row.get("Completed UTC")
                    or row.get("Source delete event UTC"),
                    row.get("Source file ID"),
                    representation,
                    canonical(
                        {
                            "source_workbook": row.get("Source workbook"),
                            "source_section": row.get("Source section"),
                            "source_record_id": row.get("Source record ID")
                            or row.get("Transcription row key"),
                            "boundary": "historical; dates are not fresh verification",
                        }
                    ),
                )
                result = state.conn.execute(
                    "INSERT OR IGNORE INTO source_provenance VALUES (?,?,?,?,?,?,?,?)", data
                )
                added_provenance += result.rowcount
            state.event(
                "package",
                "handover-2026-10-14",
                "historical_import_validated",
                {
                    "created_database": created,
                    "counts": counts,
                    "new_provenance_rows": added_provenance,
                    "remote_calls": 0,
                },
            )
        return {
            "objective_outcome": "HISTORICAL_IMPORT_VALIDATED",
            "created_database": created,
            "package": verified,
            "counts": counts,
            "new_provenance_rows": added_provenance,
            "remote_calls": 0,
            "current_remote_verification": False,
        }
