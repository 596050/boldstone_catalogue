"""Freeze B96's exact lease and locate existing cached media; no shared writes."""
from pathlib import Path
from copy import deepcopy
import datetime
import hashlib
import json
import re

B = Path(__file__).resolve().parent
C = B.parents[2]
R = C / "components/reviews"
INV = C / "components/parallel-reviews/remaining-working-review-inventory-2026-10-20"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(name, d):
    p = B / name
    assert not p.exists(), p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    return {"path": str(p), "sha256": sha(p)}


def copy(p, name):
    dest = B / name
    assert not dest.exists()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(p.read_bytes())
    return {"path": str(dest), "sha256": sha(dest)}


lease = read(R / "parallel-allocation-2026-10-20-all-remaining.json")
addendum = read(R / "parallel-allocation-2026-10-20-all-remaining-addendum.json")
lease_ref = copy(R / "parallel-allocation-2026-10-20-all-remaining.json", "ALLOCATION.json")
addendum_ref = copy(R / "parallel-allocation-2026-10-20-all-remaining-addendum.json", "ALLOCATION_ADDENDUM.json")
rows = [x for x in lease["batches"]["96"]["scopes"] if x["key"] != addendum["B96_excluded_key"]]
assert len(rows) == 40
nodes = read(INV / "SCOPE_NODE_SNAPSHOTS.json")
model = read(INV / "snapshot-model.json")
assets = {x["id"]: x for x in model["assets"]}
policies = {}
for name, source in [
    ("standing", R / "parallel-import-2026-10-19-batch80/standing-working-acceptance-policy.json"),
    ("fixing", R / "parallel-import-2026-10-19-batch87/global-fixing-choice-policy.json"),
    ("weight", R / "parallel-import-2026-10-19-batch90/global-approximate-weight-policy.json"),
    ("manufacture", R / "parallel-import-2026-10-19-batch51/owner-policy.json"),
]:
    policies[name] = copy(source, name.upper() + "_POLICY.json")
selected, scope_rows, documents, search_dirs = {}, [], {}, set()


def fid(x):
    return x.get("file_id") or x.get("id") or x.get("asset_id")


def choose(file_id, scope, role):
    assert file_id and file_id.startswith("id:"), (file_id, scope)
    selected.setdefault(file_id, {"file_id": file_id, "uses": []})["uses"].append({"scope": scope, "role": role})


for r in rows:
    key, node = r["key"], nodes[r["key"]]
    slug = key.replace("|", "__").lower()
    source_path = C / (node.get("review_record") or node["source_review_snapshot"])
    source = read(source_path)
    documents[str(source_path)] = source
    search_dirs.add(source_path.parent)
    snapshots = {
        "node": save(slug + "/NODE_AT_ALLOCATION.json", node),
        "original_review": copy(source_path, slug + "/ORIGINAL_REVIEW.json"),
    }
    identity = node.get("identity_approval") or node.get("owner_name_approval")
    if identity:
        snapshots["identity"] = copy(C / identity, slug + "/EXISTING_NAME_APPROVAL.json")
    else:
        ledger = read(INV / "snapshot-ledger.json")
        found = [d for ds in ledger.values() if isinstance(ds, list) for d in ds if isinstance(d, dict)
                 and d.get("source_design_key") == r["scope"] and (d.get("identity_confirmed") or d.get("canonical_name"))]
        snapshots["identity"] = save(slug + "/EXISTING_NAME_APPROVAL.json", found)
    original_props = source.get("specification_review_items", source.get("specifications"))
    assert original_props is not None, key
    primary = r["primary_file_id"]
    choose(primary, key, "PRIMARY")
    contexts = []
    for field in ["context_images", "series_images"]:
        items = source.get(field, [])
        if isinstance(items, list):
            for x in items[:2]:
                image_id = fid(x)
                if image_id:
                    role = "CONTEXT" if field == "context_images" else "SERIES_CONTEXT"
                    choose(image_id, key, role)
                    contexts.append({"file_id": image_id, "role": role, "historical_source": deepcopy(x)})
    for field in ["context_image_id", "room_context_image_id", "garden_context_image_id", "series_image_id"]:
        if source.get(field):
            choose(source[field], key, field.upper())
            contexts.append({"file_id": source[field], "role": field.upper(), "historical_source": {"source_field": field}})
    scope_rows.append({**r, "slug": slug, "source_snapshots": snapshots, "primary_file_id": primary,
                       "selected_contexts": contexts, "original_proposals": original_props,
                       "source_path": str(source_path)})

# Follow only bounded, local JSON evidence pointers; do not read arbitrary home data.
queue = [(Path(k), v, 0) for k, v in documents.items()]


def walk(obj):
    yield obj
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


for path, obj, depth in queue:
    if depth >= 2:
        continue
    for value in walk(obj):
        if not isinstance(value, str) or not value.endswith(".json"):
            continue
        p = Path(value) if value.startswith("/") else C / value
        if not p.is_relative_to(C) or not p.is_file() or p.stat().st_size > 3000000:
            continue
        if str(p) in documents:
            continue
        try:
            d = read(p)
        except (ValueError, OSError):
            continue
        documents[str(p)] = d
        queue.append((p, d, depth + 1))
        search_dirs.add(p.parent)
for directory in sorted(search_dirs):
    for p in directory.glob("*.json"):
        if p.name.startswith("before") or p.stat().st_size > 1500000 or str(p) in documents:
            continue
        try:
            documents[str(p)] = read(p)
        except (ValueError, OSError):
            pass

candidates = {file_id: [] for file_id in selected}
historical_heads = {file_id: [] for file_id in selected}
local_keys = ["local_path", "local_original", "full", "full_path", "original_path", "local_file"]


def consume(obj, source_path):
    if not isinstance(obj, dict):
        return
    file_id = fid(obj)
    if file_id not in selected:
        return
    if obj.get("rev"):
        historical_heads[file_id].append({"rev": obj["rev"], "size": obj.get("size", obj.get("bytes")),
                                          "source_path": source_path})
    for k in local_keys:
        value = obj.get(k)
        if isinstance(value, str) and value.startswith("/") and Path(value).is_file():
            candidates[file_id].append({"file_id": file_id, "path": value, "source_path": source_path,
                                       "expected_sha256": obj.get("sha256"),
                                       "expected_content_hash": next((obj.get(a) for a in ["content_hash", "dropbox_content_hash", "dropbox_content_hash_verified",
                                           "content_hash_snapshot_verified_against_local", "content_hash_verified_against_live_download_metadata"] if obj.get(a)), None)})


for path, document in documents.items():
    for obj in walk(document):
        consume(obj, path)
        if isinstance(obj, dict):
            for field in ["download", "download_metadata", "original_download_metadata", "file_head", "metadata"]:
                child = obj.get(field)
                if isinstance(child, dict) and fid(child) in selected:
                    consume({**obj, **child}, path)

bindings = []
for file_id, selected_item in selected.items():
    a = assets.get(file_id, {})
    if a.get("full") and Path(a["full"]).is_file():
        candidates[file_id].append({"file_id": file_id, "path": a["full"], "source_path": str(INV / "snapshot-model.json"),
                                   "expected_sha256": None, "expected_content_hash": a.get("content_hash")})
    # A deterministic cache path is considered only if its bytes match the recorded Dropbox content hash.
    known_cache = Path("/tmp/boldstone-match-review-20261016/db_images") / (file_id[3:] + ".original")
    if known_cache.is_file():
        candidates[file_id].append({"file_id": file_id, "path": str(known_cache), "source_path": str(INV / "snapshot-model.json"),
                                   "expected_sha256": None, "expected_content_hash": a.get("content_hash")})
    valid = []
    for candidate in candidates[file_id]:
        path = Path(candidate["path"])
        data = path.read_bytes()
        bh = hashlib.sha256(b"".join(hashlib.sha256(data[i:i + 4194304]).digest()
                                    for i in range(0, len(data), 4194304))).hexdigest()
        expected = candidate["expected_content_hash"] or a.get("content_hash")
        if candidate["expected_sha256"] and sha(path) != candidate["expected_sha256"]:
            continue
        if not expected or bh != expected:
            continue
        valid.append({**candidate, "sha256": sha(path), "dropbox_content_hash": bh, "bytes": len(data)})
    if valid:
        chosen = valid[0]
        media_type = "CACHED_ORIGINAL"
    else:
        thumb = Path(a.get("thumb", ""))
        if not thumb.is_file():
            raise RuntimeError("No original or preview cache for " + file_id)
        chosen = {"file_id": file_id, "path": str(thumb), "sha256": sha(thumb),
                  "bytes": thumb.stat().st_size, "snapshot_source_content_hash": a.get("content_hash"),
                  "source_path": str(INV / "snapshot-model.json")}
        media_type = "CACHED_PREVIEW_ONLY_ORIGINAL_BYTES_UNVERIFIED"
    bindings.append({**selected_item, **chosen, "media_type": media_type,
                     "historical_metadata_candidates": historical_heads[file_id],
                     "source_asset": a, "current_remote_bytes_verified": False})
metadata_ids = sorted(set(selected) | {x["folder_id"] for x in rows} |
                      {assets.get(i, {}).get("folder_id") for i in selected} - {None})
save("DISCOVERED_EVIDENCE.json", {
    "schema": "boldstone.scoped-bulk-review-evidence-discovery.v1", "created_utc": NOW,
    "allocation": lease_ref, "allocation_addendum": addendum_ref, "scopes": scope_rows,
    "policies": policies, "media": bindings, "metadata_requests": metadata_ids,
    "document_refs": [{"path": k, "sha256": sha(Path(k))} for k in documents],
    "new_acceptances": 0, "new_private_original_downloads": 0, "shared_writes": False,
})
print(json.dumps({"scopes": len(rows), "selected_media": len(bindings), "cached_originals": sum(x["media_type"] == "CACHED_ORIGINAL" for x in bindings),
                  "preview_only": [x["file_id"] for x in bindings if x["media_type"] != "CACHED_ORIGINAL"],
                  "metadata_requests": len(metadata_ids), "documents": len(documents)}))
