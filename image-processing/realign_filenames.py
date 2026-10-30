"""Finish path-derived filenames after the independently completed folder review.

Two authorized native apps share one write gate, with concurrent preparation,
readback, and audit. Native moves preserve IDs and bytes. Every batch has a
frozen intent, native outcome, and independent complete-parent readback.
"""
from __future__ import annotations

import argparse
import collections
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
import csv
import fcntl
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import threading
import time

import dropbox
from dropbox.common import PathRoot
from dropbox.files import FolderMetadata, RelocationPath
import authorize
import convert_bmps as w
import rename_from_paths as r
from retire_bmps import RetirementBudget

RUN = w.RUNTIME / "path-realignment-20261016"
DELIVERY = Path.home() / "BoldstoneMigration/path-realignment-20261016"
MANIFEST = RUN / "manifest.json"
WRITE_GATE = threading.Lock()
STATE_GATE = threading.Lock()
STOP = threading.Event()


def save(path, value):
    return r.write_once(path, value)


def load(path):
    return json.loads(path.read_text())


class AppAPI(w.API):
    def __init__(self, grant):
        self.client = dropbox.Dropbox(
            app_key=grant["app_key"], oauth2_refresh_token=grant["refresh_token"],
            timeout=90, max_retries_on_error=0, max_retries_on_rate_limit=0,
        ).with_path_root(PathRoot.namespace_id(w.NAMESPACE_ID))


def grants():
    records = []
    for label, service, account in (
        ("image-processing", w.SERVICE, w.CREDENTIAL_ACCOUNT),
        ("boldstone-executor", "BoldstoneLocal", "boldstone/dropbox/executor"),
    ):
        value = w.keychain_backend().get_password(service, account)
        if not value:
            raise w.Hold("EXPECTED_AUTHORIZED_APP_MISSING")
        grant = json.loads(value)
        scopes = set(grant.get("scopes", grant.get("granted_scopes", [])))
        if scopes != set(authorize.SCOPES) or not grant.get("refresh_token"):
            raise w.Hold("APP_GRANT_SCOPE_MISMATCH")
        api = AppAPI(grant)
        try:
            identity = api.read("users_get_current_account")
            root = api.metadata(w.ROOT_ID)
            authorize.verify_identity(identity, root, grant["account_id"])
        finally:
            api.close()
        records.append((label, grant))
    if records[0][1]["app_key"] == records[1][1]["app_key"]:
        raise w.Hold("APPS_ARE_NOT_DISTINCT")
    return records


def build_rows(inventory, controls):
    entries = {e["id"]: e for e in inventory["entries"]}
    held = {h["asset_id"] for h in controls["holds"]}
    grouped = collections.defaultdict(list)
    for source in entries.values():
        if source["kind"] != "file":
            continue
        if source["id"] in held or any(source.get(k) for k in (
            "has_explicit_shared_members", "sharing_info_present", "read_only", "file_lock_present"
        )):
            raise w.Hold("LIVE_HOLD_OR_UNREVIEWED_ACCESS")
        if not source.get("rev") or not source.get("content_hash"):
            raise w.Hold("MISSING_SOURCE_REVISION_OR_HASH")
        grouped[source["parent_id"]].append(source)
    rows, batches = [], []
    occupied = {e["path"].casefold(): e["id"] for e in entries.values()}
    for parent_id in sorted(grouped, key=lambda i: entries[i]["path"].casefold()):
        parent = entries[parent_id]
        family = entries[parent["parent_id"]]
        if family.get("parent_id") != w.ROOT_ID:
            raise w.Hold("UNEXPECTED_LEAF_DEPTH")
        prefix = r.slug(family["name"]) + "__" + r.slug(parent["name"]) + "__"
        sources = sorted(grouped[parent_id], key=lambda e: (e["name"].casefold(), e["id"]))
        reserved = set()
        for source in sources:
            extension = PurePosixPath(source["name"]).suffix
            if source["name"].startswith(prefix):
                number = source["name"][len(prefix):-len(extension)]
                if not re.fullmatch(r"\d{3,}", number) or int(number) < 1:
                    raise w.Hold("UNEXPECTED_EXISTING_FILENAME_FORMAT")
                reserved.add(int(number))
        changed = []
        for source in sources:
            extension = PurePosixPath(source["name"]).suffix
            name = source["name"]
            if not name.startswith(prefix):
                suffix = re.search(r"__(\d{3,})$", PurePosixPath(name).stem)
                if not suffix:
                    raise w.Hold("ORIGINAL_NUMBER_MISSING")
                number = int(suffix[1])
                if number in reserved:
                    number = next(n for n in range(1, len(sources) + 2) if n not in reserved)
                reserved.add(number)
                name = prefix + f"{number:03d}" + extension
            path = parent["path"] + "/" + name
            if len(name.encode()) > 255 or len(path) > 255:
                raise w.Hold("NAME_EXCEEDS_ESTABLISHED_PORTABILITY_LIMIT")
            if occupied.get(path.casefold(), source["id"]) != source["id"]:
                raise w.Hold("DESTINATION_ALREADY_OCCUPIED")
            occupied[path.casefold()] = source["id"]
            row = {"source": source, "parent_id": parent_id, "family_id": family["id"],
                   "destination_path": path, "destination_name": name, "extension": extension,
                   "operation": "NOOP" if name == source["name"] else "RENAME"}
            rows.append(row)
            if row["operation"] == "RENAME":
                changed.append(row)
        for offset in range(0, len(changed), 25):
            batches.append({"batch_id": f"REALIGN-{len(batches)+1:04d}", "parent_id": parent_id,
                            "family_id": family["id"], "file_ids": [e["source"]["id"] for e in changed[offset:offset+25]]})
    return rows, batches


def prepare():
    inventory = load(RUN / "inventory.json")
    controls = load(RUN / "controls.json")
    rows, batches = build_rows(inventory, controls)
    waiver = load(r.WAIVER)
    if waiver["scope"] != "NATIVE_MOVE_ONLY_NO_CONTENT_CHANGE" or waiver["backup_downloads_required"]:
        raise w.Hold("PRIOR_MOVE_ONLY_POLICY_NOT_APPLICABLE")
    manifest = {"schema": "boldstone-final-folder-filename-alignment-v1", "prepared_utc": w.now(),
                "user_instruction": "Do all this work that needs doing as much in parallel as possible across the dropbox apps available",
                "scope_root_id": w.ROOT_ID, "namespace_id": w.NAMESPACE_ID,
                "naming_rule": "Current family and immediate folder slugs; preserve existing numeric suffix when available; allocate the first free number only on a collision; preserve exact extension",
                "inventory": r.reference(RUN / "inventory.json"), "controls": r.reference(RUN / "controls.json"),
                "links": r.reference(RUN / "links.json"), "folder_review": r.reference(RUN / "folder-review-completion.json"),
                "backup_download_waiver": r.reference(r.WAIVER), "rows": rows, "batches": batches,
                "files_total": len(rows), "files_to_rename": sum(e["operation"] == "RENAME" for e in rows),
                "folders_to_create": 0, "folders_to_move": 0, "content_changes": 0, "deletions": 0}
    save(MANIFEST, manifest)
    save(DELIVERY / "RENAME-PLAN.json", manifest)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["file_id", "current_path", "new_path", "operation", "source_revision", "size", "content_hash"])
    for row in rows:
        s = row["source"]
        writer.writerow([s["id"], s["path"], row["destination_path"], row["operation"], s["rev"], s["size"], s["content_hash"]])
    path = DELIVERY / "OLD-AND-NEW-NAMES.csv"
    if path.exists():
        raise w.Hold("MAPPING_ALREADY_EXISTS")
    path.write_text(stream.getvalue()); path.chmod(0o600)
    save(DELIVERY / "REVERSAL-MAP.json", {"note": "Reference only; reversal requires fresh source/destination guards", "manifest": r.reference(MANIFEST),
        "rows": [{"file_id": x["source"]["id"], "from": x["destination_path"], "to": x["source"]["path"]} for x in rows if x["operation"] == "RENAME"]})
    print(json.dumps({"status": "PREPARED", "files_to_rename": manifest["files_to_rename"], "unchanged_files": len(rows)-manifest["files_to_rename"], "batches": len(batches), "affected_folders": len({b['parent_id'] for b in batches}), "manifest": r.reference(MANIFEST)}), flush=True)


def batch_move(api, label, child_rows, directory):
    request = {"entries": [{"from_path": x["source"]["id"], "to_path": x["destination_path"]} for x in child_rows],
               "autorename": False, "allow_ownership_transfer": False}
    save(directory / "intent.json", {"recorded_utc": w.now(), "app": label, "manifest_sha256": r.reference(MANIFEST)["sha256"], "request": request})
    try:
        w.BUDGET.wait()
        result = api.client.files_move_batch_v2([RelocationPath(**entry) for entry in request["entries"]], autorename=False, allow_ownership_transfer=False)
    except Exception as error:
        details = {"recorded_utc": w.now(), "error_type": type(error).__name__, "automatic_retry": False}
        if isinstance(error, w.RateLimitError):
            details.update(http_status=429, reason=getattr(getattr(error.error, "reason", None), "_tag", None), retry_after=error.backoff)
        save(directory / "submission-error.json", details)
        raise w.Hold("SUBMISSION_REQUIRES_READ_ONLY_RECONCILIATION") from None
    if result.is_async_job_id():
        job = result.get_async_job_id()
        save(directory / "launch.json", {"recorded_utc": w.now(), "app": label, "async_job_id": job})
        started = time.monotonic()
        while True:
            time.sleep(2)
            poll = api.read("files_move_batch_check_v2", job)
            if poll.is_complete():
                result = poll.get_complete(); break
            if not poll.is_in_progress():
                save(directory / "job-error.json", {"recorded_utc": w.now(), "tag": poll._tag})
                raise w.Hold("NATIVE_JOB_DID_NOT_COMPLETE")
            if time.monotonic() - started > 1800:
                raise w.Hold("NATIVE_JOB_STILL_PENDING")
    elif result.is_complete():
        save(directory / "launch.json", {"recorded_utc": w.now(), "app": label, "synchronous": True})
        result = result.get_complete()
    else:
        raise w.Hold("UNRECOGNIZED_NATIVE_LAUNCH")
    records, failed = r.terminal_rows(result, child_rows)
    save(directory / "terminal.json", {"recorded_utc": w.now(), "entries": records, "failed": failed})
    if failed:
        raise w.Hold("BATCH_HAS_FAILED_ENTRIES_REQUIRES_RECONCILIATION")
    return records


def execute(manifest_sha256):
    if r.reference(MANIFEST)["sha256"] != manifest_sha256:
        raise w.Hold("MANIFEST_HASH_MISMATCH")
    if (RUN / "COMPLETION.json").exists():
        raise w.Hold("RUN_ALREADY_COMPLETE")
    manifest = load(MANIFEST)
    baseline = r.read_reference(manifest["inventory"])
    for key in ("controls", "links", "folder_review", "backup_download_waiver"):
        r.read_reference(manifest[key])
    if list((RUN / "batches").glob("*/intent.json")):
        raise w.Hold("EXISTING_INTENTS_REQUIRE_EXPLICIT_RECONCILIATION")
    apps = grants()
    entries = {e["id"]: e for e in baseline["entries"]}
    rows = {x["source"]["id"]: x for x in manifest["rows"]}
    main_api = AppAPI(apps[0][1])
    try:
        live = r.census(main_api)
        r.check_full(baseline, live)
        save(RUN / "pre-execution.json", live)
        current_links = r.get_owned_urls(main_api)
        if sorted((x["record"] for x in current_links), key=lambda x:x["url_sha256"]) != sorted(r.read_reference(manifest["links"])["links"], key=lambda x:x["url_sha256"]):
            raise w.Hold("LINKS_CHANGED_SINCE_PLAN")
        grouped = collections.defaultdict(list)
        for batch in manifest["batches"]:
            grouped[batch["parent_id"]].append(batch)
        app_counts = collections.Counter()
        verified = 0

        def process_parent(parent_id, batches, app_index):
            nonlocal verified
            if STOP.is_set():
                raise w.Hold("PEER_STOPPED")
            label, grant = apps[app_index]
            api = AppAPI(grant)
            parent = entries[parent_id]
            expected = {i:e for i,e in entries.items() if e["kind"] == "file" and e["parent_id"] == parent_id}
            try:
                # This preflight overlaps another app's server-side batch.
                r.compare_parent(expected, r.folder_listing(api, parent))
                for batch in batches:
                    directory = RUN / "batches" / batch["batch_id"]
                    children = [rows[i] for i in batch["file_ids"]]
                    with WRITE_GATE:
                        if STOP.is_set():
                            raise w.Hold("PEER_STOPPED")
                        family = entries[batch["family_id"]]
                        fm = api.metadata(family["id"])
                        if not isinstance(fm, FolderMetadata) or fm.name != family["name"] or not w.path_equal(fm.path_display, family["path"]):
                            raise w.Hold("FAMILY_CHANGED")
                        before = r.folder_listing(api, parent)
                        r.compare_parent(expected, before)
                        occupied = {e["path"].casefold() for e in before.values()}
                        if any(x["destination_path"].casefold() in occupied for x in children):
                            raise w.Hold("DESTINATION_NOW_OCCUPIED")
                        save(directory / "before.json", {"recorded_utc": w.now(), "entries": before})
                        print(f"Submitting {batch['batch_id']}: {len(children)} renames via {label}", flush=True)
                        receipts = batch_move(api, label, children, directory)
                    # Readback runs while the other authorized app writes a disjoint parent.
                    after = r.folder_listing(api, parent)
                    r.compare_parent(before, after, {x["source"]["id"]: x["destination_path"] for x in children})
                    for receipt in receipts:
                        actual = after[receipt["source_id"]]
                        if any(receipt["metadata"].get(k) != actual.get(k) for k in ("id", "rev", "size", "content_hash")):
                            raise w.Hold("RECEIPT_READBACK_MISMATCH")
                    post = save(directory / "after.json", {"recorded_utc": w.now(), "entries": after})
                    save(directory / "verified.json", {"status": "PASS", "recorded_utc": w.now(), "app": label, "manifest_sha256": manifest_sha256, "file_ids": batch["file_ids"], "post_readback": post})
                    expected = after
                    with STATE_GATE:
                        verified += len(children); app_counts[label] += len(children)
                        w.private_json(RUN / "status.json", {"status": "RUNNING", "recorded_utc": w.now(), "files_verified": verified, "files_to_rename": manifest["files_to_rename"], "by_app": dict(app_counts)})
                        print(f"Verified {verified}/{manifest['files_to_rename']} renames; {parent['name']}", flush=True)
                return {"parent_id": parent_id, "entries": expected}
            except Exception:
                STOP.set(); raise
            finally:
                api.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(process_parent, parent, batches, index % len(apps)) for index, (parent, batches) in enumerate(grouped.items())]
            for future in as_completed(futures):
                future.result()
        final = r.census(main_api)
        destinations = {i:x["destination_path"] for i,x in rows.items() if x["operation"] == "RENAME"}
        r.check_full(baseline, final, destinations)
        final_ref = save(RUN / "final-census.json", final)
        # Independently list all folders through the other native app in parallel.
        def second_census():
            api = AppAPI(apps[1][1])
            try:return r.census(api)
            finally:api.close()
        def links_check():
            api = AppAPI(apps[0][1])
            try:
                old = load(RUN / "private-original-link-urls.json")
                current = r.get_owned_urls(api)
                def identity(u):
                    x=u["record"]
                    return tuple(x[k] for k in ("id", "resolved_visibility", "effective_audience", "link_access_level", "expires"))
                if collections.Counter(map(identity,old)) != collections.Counter(map(identity,current)):
                    raise w.Hold("LINK_MEMBERSHIP_OR_ACCESS_CHANGED")
                checks=[]
                for item in old:
                    original=item["record"]
                    if original["id"] not in rows:continue
                    current_record=r.link_record(api.read("sharing_get_shared_link_metadata",item["url"]))
                    if current_record["id"]!=original["id"] or current_record["name"]!=rows[original["id"]]["destination_name"]:
                        raise w.Hold("ORIGINAL_FILE_LINK_TARGET_CHANGED")
                    if any(current_record[k]!=original[k] for k in ("resolved_visibility","effective_audience","link_access_level","expires")):
                        raise w.Hold("LINK_ACCESS_CHANGED")
                    checks.append({"url_sha256":original["url_sha256"],"current":current_record,"status":"PASS"})
                return {"status":"PASS","original_file_urls_verified":len(checks),"checks":checks}
            finally:api.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            census_future=pool.submit(second_census); links_future=pool.submit(links_check)
            independent=census_future.result(); links=links_future.result()
        r.check_full(final, independent)
        independent_ref=save(RUN/'independent-live-census.json',independent)
        link_ref=save(RUN/'shared-link-verification.json',links)
        if verified != manifest['files_to_rename'] or any(not (p.parent/'verified.json').exists() for p in (RUN/'batches').glob('*/intent.json')):
            raise w.Hold('UNVERIFIED_INTENTS_REMAIN')
        completion={"status":"PASS","recorded_utc":w.now(),"files_renamed_verified":verified,"files_total":len(rows),"files_already_correct":len(rows)-verified,
            "folders_unchanged":sum(e['kind']=='folder' for e in final['entries']),"bmps_remaining":sum(e['kind']=='file' and e['name'].lower().endswith('.bmp') for e in final['entries']),
            "all_filenames_match_current_folders":True,"file_ids_bytes_extensions_parents_and_access_preserved":True,"pending_operations":0,"native_apps_used":dict(app_counts),
            "manifest":r.reference(MANIFEST),"final_census":final_ref,"independent_live_census":independent_ref,"shared_links":link_ref,
            "original_name_mapping":r.reference(DELIVERY/'OLD-AND-NEW-NAMES.csv')}
        save(RUN/'COMPLETION.json',completion);save(DELIVERY/'COMPLETION.json',completion)
        w.private_json(RUN/'status.json',completion)
        print(json.dumps({k:v for k,v in completion.items() if not isinstance(v,(dict,list))}),flush=True)
    finally:
        main_api.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('prepare','execute'))
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--manifest-sha256')
    args=parser.parse_args()
    os.umask(0o077)
    if args.mode=='prepare':prepare();return
    if not args.apply or not args.manifest_sha256:raise w.Hold('APPLY_AND_MANIFEST_REQUIRED')
    w.BUDGET=RetirementBudget()
    with ExitStack() as stack:
        for path in (w.RUN_PATH/'worker.lock',Path.home()/'Library/Application Support/BoldstoneImageConsistency/wall-duplicate-writer.lock'):
            lock=stack.enter_context(path.open('a'));fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:execute(args.manifest_sha256)
        except Exception as error:
            reason=str(error) if isinstance(error,(w.Hold,w.SetupError)) else type(error).__name__
            w.private_json(RUN/'stopped.json',{'recorded_utc':w.now(),'status':'STOPPED','reason':reason})
            print('Stopped: '+reason,flush=True)
            raise SystemExit(2) from None


if __name__=='__main__':main()
