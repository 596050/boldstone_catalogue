"""Independent evidence audit, final live readback, and additive path handover."""
import collections
from contextlib import ExitStack
import csv
import fcntl
import io
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
import realign_filenames as a
from retire_bmps import fingerprint_stream, RetirementBudget


def main():
    run, delivery = a.RUN, a.DELIVERY
    completion = a.load(run / "COMPLETION.json")
    assert completion["status"] == "PASS" and completion["pending_operations"] == 0
    manifest = a.r.read_reference(completion["manifest"])
    manifest_hash = completion["manifest"]["sha256"]
    baseline = a.r.read_reference(manifest["inventory"])
    initial = {e["id"]: e for e in baseline["entries"]}
    rows = {e["source"]["id"]: e for e in manifest["rows"]}
    renamed = {i: row for i, row in rows.items() if row["operation"] == "RENAME"}
    verified_ids = set()
    by_app = collections.Counter()
    for batch in manifest["batches"]:
        folder = run / "batches" / batch["batch_id"]
        proof = a.load(folder / "verified.json")
        assert proof["status"] == "PASS" and proof["manifest_sha256"] == manifest_hash
        assert proof["file_ids"] == batch["file_ids"]
        intent = a.load(folder / "intent.json")
        assert intent["manifest_sha256"] == manifest_hash and not intent["request"]["autorename"]
        assert not intent["request"]["allow_ownership_transfer"]
        assert intent["request"]["entries"] == [{"from_path": i, "to_path": rows[i]["destination_path"]} for i in batch["file_ids"]]
        before = a.load(folder / "before.json")["entries"]
        after = a.r.read_reference(proof["post_readback"])["entries"]
        a.r.compare_parent(before, after, {i: rows[i]["destination_path"] for i in batch["file_ids"]})
        terminal = a.load(folder / "terminal.json")
        assert not terminal["failed"]
        assert [e["source_id"] for e in terminal["entries"]] == batch["file_ids"]
        for receipt in terminal["entries"]:
            identifier = receipt["source_id"]
            assert identifier not in verified_ids
            assert receipt["tag"] == "success"
            assert all(receipt["metadata"][k] == after[identifier][k] for k in ("id", "rev", "size", "content_hash"))
            verified_ids.add(identifier)
        by_app[proof["app"]] += len(batch["file_ids"])
    assert verified_ids == set(renamed) and len(verified_ids) == completion["files_renamed_verified"]
    assert all((p.parent / "verified.json").exists() for p in (run / "batches").glob("*/intent.json"))
    assert len(list((run / "batches").glob("*/intent.json"))) == len(manifest["batches"])
    connector = [a.load(p) for p in (run / "connector-verification").glob("folder-*.json")]
    expected_parents = {b["parent_id"] for b in manifest["batches"]}
    assert len(connector) == len(expected_parents)
    assert {p["parent_id"] for p in connector} == expected_parents
    for proof in connector:
        assert proof["status"] == "PASS" and proof["pagination_exhausted"]
        expected = {i: [r["destination_name"], r["source"]["size"]] for i, r in rows.items() if r["parent_id"] == proof["parent_id"]}
        assert proof["entries"] == expected
    a.w.BUDGET = RetirementBudget()
    with ExitStack() as stack:
        for path in (a.w.RUN_PATH / "worker.lock", Path.home() / "Library/Application Support/BoldstoneImageConsistency/wall-duplicate-writer.lock"):
            lock = stack.enter_context(path.open("a"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        apps = a.grants()
        api = a.AppAPI(apps[1][1])
        try:
            live = a.r.census(api)
            a.r.check_full(a.r.read_reference(completion["independent_live_census"]), live)
            current = {e["id"]: e for e in live["entries"]}
            for identifier, row in rows.items():
                now = current[identifier]
                parent = current[now["parent_id"]]
                family = current[parent["parent_id"]]
                assert family["parent_id"] == a.w.ROOT_ID
                prefix = a.r.slug(family["name"]) + "__" + a.r.slug(parent["name"]) + "__"
                extension = PurePosixPath(now["name"]).suffix
                suffix = now["name"][len(prefix):-len(extension)]
                assert now["name"].startswith(prefix) and re.fullmatch(r"\d{3,}", suffix)
                assert extension == PurePosixPath(row["source"]["name"]).suffix
                assert now["path"] == row["destination_path"]
                assert all(now[k] == row["source"][k] for k in ("id", "content_hash", "size", "parent_id"))
            public = []
            for item in a.load(run / "private-original-link-urls.json"):
                link = item["record"]
                if link["id"] not in rows or link["type"] != "FileLinkMetadata" or link["resolved_visibility"] != "public":
                    continue
                url = urlsplit(item["url"])
                assert url.scheme == "https" and url.hostname in {"www.dropbox.com", "dropbox.com"}
                query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if k not in {"dl", "raw"}]
                query.append(("dl", "1"))
                download = urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), url.fragment))
                with requests.get(download, stream=True, timeout=45) as response:
                    assert response.status_code == 200
                    response.raw.decode_content = True
                    actual = fingerprint_stream(response.raw)
                assert all(actual[k] == current[link["id"]][k] for k in ("size", "content_hash"))
                public.append({"id": link["id"], "original_url_sha256": link["url_sha256"], "status": "PUBLIC_ANONYMOUS_DOWNLOAD_VERIFIED", **actual})
        finally:
            api.close()
        live_ref = a.save(run / "final-independent-live-census.json", live)
        public_ref = a.save(run / "anonymous-public-link-verification.json", {"status": "PASS", "checks": public})
        links = a.r.read_reference(completion["shared_links"])
        overlay = {"schema": "boldstone-current-path-overlay-v2", "recorded_utc": a.w.now(), "status": "PASS", "scope_root_id": a.w.ROOT_ID,
                   "completion": a.r.reference(run / "COMPLETION.json"), "live_census": live_ref,
                   "files": [{k: e[k] for k in ("id", "name", "path", "parent_id", "rev", "size", "content_hash")} for e in current.values() if e["kind"] == "file"],
                   "note": "Current names after the completed folder review and filename alignment. Historical identity, protection and migration evidence is unchanged."}
        overlay_ref = a.save(delivery / "CURRENT-FILE-PATHS.json", overlay)
        original_completion = a.load(a.w.RUNTIME / "path-renaming-20261016/COMPLETION.json")
        original_manifest = a.r.read_reference(original_completion["manifest"])
        origins = {x["source"]["id"]: x["source"]["path"] for x in original_manifest["rows"]}
        assert set(origins) == set(rows)
        buffer = io.StringIO(); writer = csv.writer(buffer)
        writer.writerow(["file_id", "original_path_before_filename_work", "current_path", "size", "content_hash"])
        for identifier in sorted(rows):
            now = current[identifier]
            writer.writerow([identifier, origins[identifier], now["path"], now["size"], now["content_hash"]])
        mapping = delivery / "ORIGINAL-TO-CURRENT-NAMES.csv"
        with mapping.open("x") as stream:stream.write(buffer.getvalue())
        mapping.chmod(0o600)
        report = {"status": "PASS", "recorded_utc": a.w.now(), "files_total_verified": len(rows), "filenames_updated": len(renamed),
                  "filenames_already_correct": len(rows)-len(renamed), "all_filenames_match_current_directory_paths": True,
                  "folder_count_unchanged": sum(e["kind"] == "folder" for e in live["entries"]), "bmps_remaining": 0,
                  "file_ids_bytes_extensions_parents_and_access_preserved": True, "batches_verified": len(manifest["batches"]),
                  "native_apps_renames": dict(by_app), "connector_folders_independently_verified": len(connector),
                  "connector_files_independently_verified": sum(p["files_verified"] for p in connector),
                  "original_file_urls_verified": links["original_file_urls_verified"], "public_original_urls_download_verified": len(public),
                  "pending_operations": 0, "completion": a.r.reference(run / "COMPLETION.json"), "manifest": completion["manifest"],
                  "independent_live_census": live_ref, "anonymous_public_link_check": public_ref,
                  "current_paths": overlay_ref, "original_to_current_mapping": a.r.reference(mapping)}
        assert not any(e["kind"] == "file" and e["name"].lower().endswith(".bmp") for e in live["entries"])
        report_ref = a.save(delivery / "FINAL-INDEPENDENT-CHECK.json", report)
        a.save(run / "FINAL-INDEPENDENT-CHECK.json", report)
        state_path = a.w.RUNTIME / "latest-library-state.json"
        previous = a.load(state_path)
        a.save(run / "previous-latest-library-state.json", previous)
        a.w.private_json(state_path, {**previous, "status": "PASS", "state": "ALL_FILENAMES_ALIGNED_AFTER_COMPLETED_FOLDER_REVIEW",
            "recorded_utc": a.w.now(), "completion": report["completion"], "final_census": live_ref, "file_count": len(rows),
            "folder_count": report["folder_count_unchanged"], "remaining_bmps": 0, "current_file_paths": overlay_ref, "filename_audit": report_ref})
        pointer = a.w.SHARED / "CURRENT-FILENAME-PATHS.json"
        a.save(run / "previous-shared-filename-pointer.json", a.load(pointer))
        a.w.private_json(pointer, {"status": "PASS", "recorded_utc": a.w.now(), "current_paths": overlay_ref, "completion": report["completion"], "independent_check": report_ref})
        consistency = Path.home() / "Library/Application Support/BoldstoneImageConsistency"
        for name in ("CURRENT-CANONICAL-ASSET-REGISTRY.json", "CURRENT-IDENTITY-REVIEW.json"):
            pointer = consistency / name; previous = a.load(pointer)
            a.save(run / ("previous-" + name), previous)
            a.w.private_json(pointer, {**previous, "filename_alignment": {"recorded_utc": a.w.now(), "current_paths": overlay_ref, "independent_check": report_ref,
                "note": "Resolve current file names and paths by stable ID using this overlay. Historical review and remaining evidence questions retain their original status."}})
        print(json.dumps({k: v for k, v in report.items() if not isinstance(v, (list, dict))}), flush=True)


if __name__ == "__main__":main()
