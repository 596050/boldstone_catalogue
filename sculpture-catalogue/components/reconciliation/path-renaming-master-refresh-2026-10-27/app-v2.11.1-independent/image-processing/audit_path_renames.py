"""Read-only conservation audit of immutable path-renaming receipts."""
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath

RUNTIME = Path.home() / "Library/Application Support/BoldstoneImageProcessing/path-renaming-20261016"
DELIVERY = Path.home() / "BoldstoneMigration/path-renaming-20261016"


def read(path):
    return json.loads(Path(path).read_text())


def referenced(ref):
    p = Path(ref["path"])
    assert hashlib.sha256(p.read_bytes()).hexdigest() == ref["sha256"], "Reference checksum mismatch"
    return read(p)


def audit():
    active = RUNTIME / "ACTIVE-MANIFEST.json"
    manifest_path = Path(read(active)["path"]) if active.exists() else RUNTIME / "manifest.json"
    if active.exists():
        referenced(read(active))
    manifest = read(manifest_path)
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    versions = {digest: manifest}
    prior = manifest
    while prior.get("previous_manifest"):
        ref = prior["previous_manifest"]
        assert ref["sha256"] not in versions
        prior = referenced(ref)
        versions[ref["sha256"]] = prior
    baseline = {e["id"]: e for e in referenced(manifest["inventory"])["entries"]}
    proposals = {r["source"]["id"]: r for r in manifest["rows"]}
    assert len(proposals) == manifest["file_count"]
    assert len({r["destination_path"].casefold() for r in proposals.values()}) == len(proposals)
    mapping_path = Path(manifest.get("mapping", {}).get("path", DELIVERY / "OLD-AND-NEW-NAMES.csv"))
    if manifest.get("mapping"):
        assert hashlib.sha256(mapping_path.read_bytes()).hexdigest() == manifest["mapping"]["sha256"]
    with mapping_path.open(newline="") as stream:
        mapping = {r["file_id"]: r for r in csv.DictReader(stream)}
    assert set(mapping) == set(proposals)
    for i, row in proposals.items():
        assert mapping[i]["original_path"] == row["source"]["path"]
        assert mapping[i]["new_path"] == row["destination_path"]
        assert PurePosixPath(row["destination_path"]).parent == PurePosixPath(row["source"]["path"]).parent
        assert PurePosixPath(row["destination_path"]).suffix == PurePosixPath(row["source"]["path"]).suffix
    verified, heads, batch_count = set(), {}, 0
    for batch in manifest["batches"]:
        directory = RUNTIME / "batches" / batch["batch_id"]
        if not (directory / "verified.json").exists():
            continue
        receipt = read(directory / "verified.json")
        assert receipt["status"] == "RENAMED_VERIFIED"
        assert receipt["manifest_sha256"] in versions
        if receipt["manifest_sha256"] != digest:
            earlier = versions[receipt["manifest_sha256"]]
            prior_rows = {r["source"]["id"]:r for r in earlier["rows"]}
            assert next(b for b in earlier["batches"] if b["batch_id"] == batch["batch_id"]) == batch
            assert all(prior_rows[i] == proposals[i] for i in batch["file_ids"])
        assert set(receipt["file_ids"]) == set(batch["file_ids"])
        assert not verified.intersection(batch["file_ids"])
        before = referenced(read(directory / "intent.json")["before"])["entries"]
        after = referenced(receipt["post_readback"])["entries"]
        assert set(before) == set(after), "Sibling membership changed"
        terminal = read(directory / "terminal.json")
        assert not terminal["failed"]
        native = {e["source_id"]: e for e in terminal["entries"]}
        assert set(native) == set(batch["file_ids"])
        for identifier, old in before.items():
            new = after[identifier]
            for key in ("id", "size", "content_hash", "parent_id", "has_explicit_shared_members", "sharing_info_present", "read_only", "file_lock_present", "parent_shared_folder_id"):
                assert old.get(key) == new.get(key), (identifier, key)
            if identifier in native:
                assert new["path"] == proposals[identifier]["destination_path"]
                assert new["name"] == proposals[identifier]["destination_name"]
                assert native[identifier]["tag"] == "success"
                for key in ("id", "rev", "size", "content_hash"):
                    assert native[identifier]["metadata"][key] == new[key]
                heads[identifier] = new
            else:
                assert old["path"] == new["path"] and old["rev"] == new["rev"]
        verified.update(batch["file_ids"])
        batch_count += 1
    result = {"status": "VERIFIED_CHECKPOINTS_PASS", "files_verified": len(verified), "files_total": len(proposals), "batches_verified": batch_count, "batches_total": len(manifest["batches"]), "manifest_sha256": digest}
    if (RUNTIME / "COMPLETION.json").exists():
        complete = read(RUNTIME / "COMPLETION.json")
        assert complete["status"] == "PASS"
        assert verified == {i for i,r in proposals.items() if r["operation"] == "RENAME"}
        final = {e["id"]:e for e in referenced(complete["final_census"])["entries"]}
        assert set(final) == set(baseline)
        for identifier, old in baseline.items():
            new = final[identifier]
            if old["kind"] == "folder":
                for key in ("kind", "name", "path", "parent_id", "sharing_info_present"):
                    assert new.get(key) == old.get(key)
            else:
                assert new["path"] == proposals[identifier]["destination_path"]
                for key in ("id", "size", "content_hash", "parent_id", "has_explicit_shared_members", "sharing_info_present", "read_only", "file_lock_present", "parent_shared_folder_id"):
                    assert new.get(key) == old.get(key)
                if identifier in heads:
                    assert new["rev"] == heads[identifier]["rev"]
        old_links = referenced(manifest["sharing_snapshot"])["links"]
        expected_links = {l["url_sha256"]: l for l in old_links if l["id"] in proposals}
        links = referenced(complete["shared_link_verification"])
        assert links["status"] == "PASS"
        assert {c["old_url_sha256"] for c in links["checks"]} == set(expected_links)
        for check in links["checks"]:
            old = expected_links[check["old_url_sha256"]]
            new = check["current"]
            assert check["status"] == "ORIGINAL_URL_RESOLVES_SAME_FILE_ID"
            assert new["name"] == proposals[old["id"]]["destination_name"]
            for key in ("id", "resolved_visibility", "effective_audience", "link_access_level", "expires"):
                assert new[key] == old[key]
        result.update(status="PASS", folders_unchanged=sum(e["kind"] == "folder" for e in final.values()), original_file_urls_verified=len(expected_links), public_file_urls_verified=sum(l["resolved_visibility"] == "public" for l in expected_links.values()), bmps_remaining=sum(e["kind"] == "file" and e["name"].lower().endswith(".bmp") for e in final.values()))
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
