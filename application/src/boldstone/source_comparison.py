from __future__ import annotations

import json
from pathlib import Path

from .binary_cache import decode_image
from .errors import IntegrityError
from .hashing import hash_file
from .util import check_no_symlinks, file_sha256


def compare_verified_local_source(state, scope, source_id, jpg_check):
    """Compare traceable source bytes; a missing cache does not prove source absence."""
    records = state.conn.execute(
        """SELECT b.* FROM binary_checks b JOIN runs r USING(run_id)
        WHERE b.asset_id=? AND b.outcome='BINARY_INTEGRITY_VERIFIED' AND b.cache_path IS NOT NULL
        AND r.account_id=? AND r.namespace_id=? AND r.root_folder_id=? ORDER BY b.checked_utc DESC""",
        (source_id, scope.run.account_id, scope.run.namespace_id, scope.run.root_id),
    ).fetchall()
    result = {
        "source_id": source_id,
        "source_equivalence_accepted": False,
        "remote_historical_revision_retrieval": "not_attempted",
        "independent_backup_records": "not_assessed_in_this_version",
        "visual_content_comparison": "not_performed",
    }
    for row in records:
        path = check_no_symlinks(Path(row["cache_path"]))
        if not path.is_relative_to(state.config.directory("cache")):
            raise IntegrityError("Recorded source cache escaped the private cache directory")
        if not path.exists():
            continue
        if (
            file_sha256(path) != row["sha256"]
            or hash_file(path) != row["dropbox_content_hash"]
            or path.stat().st_size != row["byte_size"]
        ):
            raise IntegrityError("Recorded historical source cache failed byte verification")
        original = json.loads(row["evidence_json"])
        if original.get("asset_id") != source_id or original.get("revision") != row["revision"]:
            raise IntegrityError("Recorded source cache ID/revision association is inconsistent")
        image = decode_image(path, max_frames=state.config.data["read_policy"]["max_frames"])
        if image["actual_format"] != "BMP":
            return {
                **result,
                "source_status": "LOCAL_SOURCE_ACTUAL_FORMAT_MISMATCH",
                "actual_format": image["actual_format"],
            }
        jpg = jpg_check["image"]
        return {
            **result,
            "source_status": "VERIFIED_LOCAL_SOURCE_LOCATED",
            "source_binary_check_id": row["binary_check_id"],
            "source_revision": row["revision"],
            "source_sha256": row["sha256"],
            "source_image": image,
            "dimensions_match": (image["width"], image["height"]) == (jpg["width"], jpg["height"]),
            "orientation_match": image["orientation"] == jpg["orientation"],
            "boundary": "Dimension/profile observations do not establish visual or colour equivalence",
        }
    return {
        **result,
        "source_status": "NOT_LOCATED_IN_VERIFIED_LOCAL_DOWNLOAD_RECORDS",
        "source_bytes_unavailable_everywhere": None,
    }
