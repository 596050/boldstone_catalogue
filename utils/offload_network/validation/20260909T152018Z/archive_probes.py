"""Synthetic archive probes confined to the supplied temporary directory."""
import argparse
import io
import json
from pathlib import Path
import sys
import tarfile
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(args.source))
from v2 import result, seal, transport
from v2.manifest import HostSpec, ResultSpec, SealedBlob, SealedManifest

records = []
for mode in ("result", "seal"):
    root = args.out / mode
    root.mkdir()
    outside = root / "outside"
    outside.mkdir()
    dest = root / "destination"
    dest.mkdir()
    archive = root / "links.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../outside"
        handle.addfile(link)
        entry = tarfile.TarInfo("link/proof.txt")
        payload = b"synthetic proof only"
        entry.size = len(payload)
        handle.addfile(entry, io.BytesIO(payload))
    error = None
    try:
        if mode == "result":
            result._safe_extract(archive, dest)
        else:
            with tarfile.open(archive, "r:gz") as handle:
                seal._safe_extract_tar(handle, dest)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    records.append({"extractor": mode, "python": sys.version.split()[0],
                    "wrote_outside_destination": (outside / "proof.txt").exists(), "error": error})

root = args.out / "integrity"
root.mkdir()
entry = root / "entry.py"
entry.write_text("pass\n")
manifest = SealedManifest(job_id="audit-integrity", host=HostSpec("synthetic", "/synthetic/jobs"),
    blobs=[SealedBlob("entry", str(entry), "code/job.py")], entrypoint_rel="code/job.py",
    result=ResultSpec(local_dir=str(root / "results")))
original = seal.build_seal(manifest, out_dir=root / "bundles")
modified = root / "modified.tar.gz"
with tarfile.open(original, "r:gz") as src, tarfile.open(modified, "w:gz") as dst:
    for member in src.getmembers():
        content = src.extractfile(member).read() if member.isfile() else None
        if member.name == "runner.py":
            content = b"# synthetic replacement; never executed\n"
            member.size = len(content)
        dst.addfile(member, io.BytesIO(content) if content is not None else None)
record = {"changed_member": "runner.py"}
for label, kwargs in (("without_expected_archive_hash", {}), ("with_expected_archive_hash", {"expected_sha256": manifest.seal_sha256})):
    try:
        seal.verify_seal(modified, **kwargs)
        record[label] = "ACCEPTED"
    except Exception as exc:
        record[label] = type(exc).__name__
records.append(record)

with patch.object(transport, "_mkdir_remote"), \
     patch.object(transport, "remote_file_size", return_value=original.stat().st_size), \
     patch.object(transport, "_retrying") as transfer:
    transport.push_seal(seal_path_local=original, host_alias="synthetic", remote_workdir="/synthetic/jobs", platform="macos")
records.append({"remote_seal_same_size_only": True, "transfer_performed": transfer.called,
                "remote_content_hash_checked": False, "actual_remote_operations": 0})
print(json.dumps(records, indent=2))
(args.out / "ARCHIVE_PROBES.json").write_text(json.dumps(records, indent=2))
