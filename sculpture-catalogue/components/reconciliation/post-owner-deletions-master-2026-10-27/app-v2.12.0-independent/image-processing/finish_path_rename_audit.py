"""Final independent live check and additive current-path handover."""
import fcntl
import hashlib
import json
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

import audit_path_renames as independent
import convert_bmps as w
import rename_from_paths as r
from retire_bmps import RetirementBudget, fingerprint_stream


def main():
    completion_path = r.RUN / "COMPLETION.json"
    completion = json.loads(completion_path.read_text())
    assert completion["status"] == "PASS"
    result = independent.audit()
    assert result["status"] == "PASS"
    finished = r.DELIVERY / "FINAL-INDEPENDENT-CHECK.json"
    if finished.exists():
        saved = json.loads(finished.read_text())
        assert saved["status"] == "PASS" and saved["completion"] == r.reference(completion_path)
        print(json.dumps({"status": "ALREADY_VERIFIED", "report": str(finished)}), flush=True)
        return
    with ExitStack() as stack:
        for path in (w.RUN_PATH / "worker.lock", Path.home() / "Library/Application Support/BoldstoneImageConsistency/wall-duplicate-writer.lock"):
            lock = stack.enter_context(path.open("a"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        w.BUDGET = RetirementBudget()
        grant = json.loads(w.keychain_backend().get_password(w.SERVICE, w.CREDENTIAL_ACCOUNT))
        w.verify_grant(grant)
        api = w.API(grant)
        try:
            previous = r.read_reference(completion["final_census"])
            live = r.census(api)
            first = {e["id"]: e for e in previous["entries"]}
            current = {e["id"]: e for e in live["entries"]}
            assert set(first) == set(current)
            for identifier, old in first.items():
                new = current[identifier]
                keys = ("kind", "name", "path", "parent_id", "sharing_info_present")
                if old["kind"] == "file":
                    keys += ("rev", "size", "content_hash", "has_explicit_shared_members", "read_only", "file_lock_present", "parent_shared_folder_id")
                assert all(old.get(k) == new.get(k) for k in keys), identifier
            census_digest = hashlib.sha256((json.dumps(live, indent=2, sort_keys=True) + "\n").encode()).hexdigest()
            census_ref = r.write_once(r.RUN / ("independent-live-census-" + census_digest + ".json"), live)
            public_checks = []
            for item in json.loads((r.RUN / "private-original-link-urls.json").read_text()):
                link = item["record"]
                if link["id"] not in current or link["type"] != "FileLinkMetadata" or link["resolved_visibility"] != "public":
                    continue
                # Test the original shared-link token anonymously, requesting its
                # download representation. No OAuth header, session cookie, or
                # credentials are sent to this public endpoint.
                url = urlsplit(item["url"])
                assert url.scheme == "https" and url.hostname in {"www.dropbox.com", "dropbox.com"}
                query = [(k,v) for k,v in parse_qsl(url.query, keep_blank_values=True) if k not in {"dl", "raw"}]
                query.append(("dl", "1"))
                download = urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), url.fragment))
                with requests.get(download, stream=True, timeout=45) as response:
                    assert response.status_code == 200, "Public link HTTP response failed"
                    response.raw.decode_content = True
                    actual = fingerprint_stream(response.raw)
                    assert actual["size"] == current[link["id"]]["size"]
                    assert actual["content_hash"] == current[link["id"]]["content_hash"]
                    observed = w.head(api.metadata(link["id"]))
                    assert all(observed[k] == current[link["id"]][k] for k in ("id", "rev", "size", "content_hash"))
                    public_checks.append({"id": link["id"], "original_url_sha256": link["url_sha256"], "status": "ORIGINAL_PUBLIC_LINK_DOWNLOAD_VERIFIED", "http_status": response.status_code, "final_host": urlsplit(response.url).hostname, **actual})
            public_ref = r.write_once(r.RUN / "anonymous-public-link-verification.json", {"recorded_utc": w.now(), "status": "PASS", "checks": public_checks})
        finally:
            api.close()
        manifest = r.read_reference(completion["manifest"])
        origins = {row["source"]["id"]: row["source"]["path"] for row in manifest["rows"]}
        paths = {"schema": "boldstone-current-path-overlay-v1", "recorded_utc": w.now(), "completion": r.reference(completion_path), "live_census": census_ref, "scope_root_id": w.ROOT_ID,
                 "note": "Current paths by stable ID. Historical migration, BMP, keeper, and lineage receipts remain immutable.",
                 "files": [{"id": item["id"], "path": item["path"], "name": item["name"], "parent_id": item["parent_id"], "rev": item["rev"], "size": item["size"], "content_hash": item["content_hash"], "source_path_before_filename_rename": origins[item["id"]]} for item in current.values() if item["kind"] == "file"]}
        path_ref = r.write_once(r.DELIVERY / "CURRENT-FILE-PATHS.json", paths)
        result.update(recorded_utc=w.now(), completion=r.reference(completion_path), independent_live_census=census_ref, current_paths=path_ref, anonymous_public_link_check=public_ref,
                      external_folder_changes_adopted=manifest.get("external_change_amendment"), original_name_mapping=completion["original_name_mapping"], no_pending_write_intents=all((p.parent / "verified.json").exists() for p in (r.RUN / "batches").glob("*/intent.json")))
        assert result["no_pending_write_intents"]
        audit_ref = r.write_once(r.DELIVERY / "FINAL-INDEPENDENT-CHECK.json", result)
        r.write_once(r.RUN / "FINAL-INDEPENDENT-CHECK.json", result)
        state_path = w.RUNTIME / "latest-library-state.json"
        previous_state = json.loads(state_path.read_text())
        r.write_once(r.RUN / "previous-latest-library-state.json", previous_state)
        state = {**previous_state, "recorded_utc": w.now(), "status": "PASS", "state": "ALL_CURRENT_FILENAMES_DERIVED_FROM_DIRECTORY_PATHS", "bmp_retirement_completion": previous_state.get("completion"), "completion": r.reference(completion_path), "final_census": census_ref, "file_count": result["files_total"], "folder_count": result["folders_unchanged"], "remaining_bmps": result["bmps_remaining"], "current_file_paths": path_ref, "filename_audit": audit_ref}
        w.private_json(state_path, state)
        w.private_json(w.SHARED / "CURRENT-FILENAME-PATHS.json", {"status": "PASS", "recorded_utc": w.now(), "current_paths": path_ref, "completion": r.reference(completion_path), "independent_check": audit_ref, "note": "Resolve historical JPEG successor and keeper paths through this stable-ID overlay. Original protection and lineage records are retained unchanged."})
        print(json.dumps({k: result[k] for k in ("status", "files_verified", "files_total", "folders_unchanged", "original_file_urls_verified", "public_file_urls_verified", "bmps_remaining")}), flush=True)


if __name__ == "__main__":
    main()
