"""Verify relocated shared artifacts as data, without importing returned code.

The encoded blob must stay inside the returned native output tree. Its encoded
and decoded identities are checked by streaming, with the declared per-job work
limit bounding each decoded artifact. Ordinary-file evidence remains supported.
"""
import gzip
import hashlib
from pathlib import Path

from .common import digest, hash_id, load, no_links, rel, sha


def verify(path, expected, *, root, prefix, max_decoded_bytes):
    root, path = Path(root).absolute(), Path(path).absolute()
    path.relative_to(root)
    no_links(path, root)
    hash_id(expected)
    item = manifest = None
    for parent in path.parents:
        if not parent.is_relative_to(root):
            break
        source = parent / "ARTIFACTS.json"
        if source.exists() or source.is_symlink():
            no_links(source, root)
            manifest = load(source)
            body = dict(manifest)
            ident = body.pop("manifest_id", None)
            if (manifest.get("schema") != "marketmaker.shared_artifacts.v1"
                    or digest(body) != ident or not isinstance(manifest.get("files"), dict)):
                raise ValueError("native shared artifact manifest changed")
            for name in manifest["files"]:
                if rel(name) != name:
                    raise ValueError("invalid native shared artifact name")
            item = manifest["files"].get(path.relative_to(parent).as_posix())
            break
    if item is None:
        if sha(path) != expected:
            raise ValueError("returned native ledger/artifact changed")
        return

    def relocated(value):
        if not isinstance(value, str) or not value.startswith(prefix + "/"):
            raise ValueError("native shared artifact escapes returned output")
        suffix = value[len(prefix) + 1:]
        if rel(suffix) != suffix:
            raise ValueError("noncanonical native shared artifact path")
        return no_links(root / suffix, root)

    store = manifest["store"]
    relocated(store)
    hash_id(item["sha256"])
    hash_id(item["encoded_sha256"])
    if item["sha256"] != expected or item["codec"] not in {"gzip", "identity"}:
        raise ValueError("native shared artifact identity or codec changed")
    if (type(max_decoded_bytes) is not int or max_decoded_bytes <= 0
            or any(type(item[key]) is not int or not 0 <= item[key] <= max_decoded_bytes
                   for key in ("bytes", "encoded_bytes"))):
        raise ValueError("native shared artifact exceeds declared work bound")
    suffix = "data.gz" if item["codec"] == "gzip" else "data"
    wanted = store + "/blobs/" + expected[:2] + "/" + expected + "/" + suffix
    if item["path"] != wanted:
        raise ValueError("native shared blob is outside its declared store")
    blob = relocated(item["path"])
    if not blob.is_file() or blob.stat().st_size != item["encoded_bytes"]:
        raise ValueError("native encoded artifact size changed")
    encoded_hash, decoded_hash = hashlib.sha256(), hashlib.sha256()

    class Reader:
        def __init__(self, stream):
            self.stream, self.count = stream, 0

        def read(self, size=-1):
            # Never accept a growing encoded file beyond the authenticated size.
            remaining = item["encoded_bytes"] - self.count + 1
            data = self.stream.read(remaining if size < 0 else min(size, remaining))
            self.count += len(data)
            if self.count > item["encoded_bytes"]:
                raise ValueError("native encoded artifact exceeds its bound")
            encoded_hash.update(data)
            return data

    size = 0
    with blob.open("rb") as raw:
        reader = Reader(raw)
        stream = gzip.GzipFile(fileobj=reader, mode="rb") if item["codec"] == "gzip" else reader
        try:
            while chunk := stream.read(min(1 << 20, item["bytes"] - size + 1)):
                size += len(chunk)
                if size > item["bytes"]:
                    raise ValueError("native decoded artifact exceeds its bound")
                decoded_hash.update(chunk)
        finally:
            if stream is not reader:
                stream.close()
    if (reader.count != item["encoded_bytes"]
            or encoded_hash.hexdigest() != item["encoded_sha256"]
            or size != item["bytes"] or decoded_hash.hexdigest() != expected):
        raise ValueError("native encoded or decoded artifact changed")
    if path.exists() and sha(path) != expected:
        raise ValueError("native ordinary and packed artifact copies disagree")
