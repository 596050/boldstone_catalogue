"""Preserve every converted BMP outside the conversion cache and test restoration."""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import convert_bmps as w
from check_bmp_retirement import CHECKS, reference
from PIL import Image

ARCHIVE_DIR = Path.home() / "BoldstoneMigration/bmp-originals-20261015"
ARCHIVE = ARCHIVE_DIR / "Boldstone_BMP_Originals_2026-10-15.zip"


def main():
    os.umask(0o077)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    plan = json.loads(w.PLAN_PATH.read_text())
    w.validate_plan(plan)
    rows = [row for row in plan["rows"] if row["status"] == "ELIGIBLE"]
    records = []
    source_formats = {}
    for row in rows:
        state = w.saved_state(row)
        source_format = state["local_jpeg"].get("source_format", "BMP")
        if source_format not in ("BMP", "JPEG"):
            raise w.SetupError("Unsupported original format in conversion evidence")
        source_formats[row["source_id"]] = source_format
        original = Path(state["work_directory"]) / "original.bmp"
        if w.fingerprint(original) != state["backup"]:
            raise w.SetupError("Source backup differs before archiving")
        records.append({"source_id": row["source_id"], "source_path": row["source_path"],
                        "source_head": state["source_head"], "jpeg_head": state["output_head"],
                        "jpeg_dimensions": state["local_jpeg"]["dimensions"],
                        "backup": state["backup"], "local_original": str(original),
                        "archive_member": "originals/" + str(PurePosixPath(row["source_path"]).relative_to(w.ROOT_PATH))})
    manifest = {"schema": "boldstone-bmp-preservation-archive-v1", "created_utc": w.now(),
                "root_path": w.ROOT_PATH, "records": records,
                "purpose": "Lossless original bytes preserved independently of JPEGs and the conversion cache.",
                "restore_note": "Extract the named BMP. Restoring a deleted file ID, shared link, or native revision history is a separate Dropbox operation."}
    if not ARCHIVE.exists():
        temporary = ARCHIVE.with_suffix(".zip.partial")
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            archive.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            archive.writestr("README.txt", f"These are the exact original files for {len(records)} full-resolution JPEG conversions.\n"
                             "JPEG uses quality 100 and 4:4:4 but is still lossy; keep this lossless source archive.\n"
                             "Each manifest entry binds a BMP to its Dropbox ID, revision, hashes and JPEG replacement.\n"
                             "This archive is not a backup of Dropbox sharing permissions or native revision history.\n")
            for record in records:
                archive.write(record["local_original"], record["archive_member"])
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        temporary.rename(ARCHIVE)
        os.chmod(ARCHIVE, 0o600)
    verified = []
    with zipfile.ZipFile(ARCHIVE) as archive, tempfile.TemporaryDirectory(prefix="restore-test-", dir=ARCHIVE_DIR) as temp:
        archived_manifest = json.loads(archive.read("MANIFEST.json"))
        if archived_manifest["records"] != records:
            raise w.SetupError("Existing archive manifest differs")
        members = archive.namelist()
        if (len(members) != len(records) + 2 or
                set(members) != {"MANIFEST.json", "README.txt", *(r["archive_member"] for r in records)}):
            raise w.SetupError("Archive member list differs")
        for index, record in enumerate(records, 1):
            restored = Path(temp) / "original.bmp"
            with archive.open(record["archive_member"]) as source, restored.open("wb") as destination:
                while data := source.read(w.BLOCK_SIZE):
                    destination.write(data)
                destination.flush()
                os.fsync(destination.fileno())
            fingerprint = w.fingerprint(restored)
            if fingerprint != record["backup"]:
                raise w.SetupError("Archive restoration fingerprint failed")
            with Image.open(restored) as image:
                image.load()
                # Conversion also accepts a JPEG stored under a .bmp extension
                # and copies its bytes without recompression. Restoration must
                # verify that recorded source format rather than its suffix.
                if (image.format != source_formats[record["source_id"]]
                        or list(image.size) != record["jpeg_dimensions"]):
                    raise w.SetupError("Archive restoration decode failed")
            verified.append({"source_id": record["source_id"], "archive_member": record["archive_member"],
                             **fingerprint, "restore_and_decode_passed": True})
            if index % 50 == 0 or index == len(records):
                print(f"Archive restore-tested: {index}/{len(records)}", flush=True)
    w.private_json(ARCHIVE_DIR / "MANIFEST.json", archived_manifest)
    proof = {"schema": "boldstone-bmp-archive-restoration-proof-v1", "completed_utc": w.now(),
             "archive": {**reference(ARCHIVE), "size": ARCHIVE.stat().st_size},
             "manifest": reference(ARCHIVE_DIR / "MANIFEST.json"), "records": verified,
             "original_bytes": sum(r["size"] for r in verified), "status": "PASS"}
    w.private_json(ARCHIVE_DIR / "RESTORE-VERIFICATION.json", proof)
    w.private_json(CHECKS / "archive-proof.json", proof)
    print(json.dumps({"status": "PASS", "files": len(verified), "archive": proof["archive"]}, indent=2))


if __name__ == "__main__":
    main()
