"""Large registered datasets must not reserve their limit for every tiny result."""
import hashlib
import io
import json
import tarfile

import pytest

from research_workflows.objects import ObjectStore, object_expansion_budget, pack


def malformed(tmp_path, files, content, *, first_name="OBJECT.json", extra=None):
    target = tmp_path / "object.tar.gz"
    manifest = json.dumps({"schema": "marketmaker.offload_object.v1", "files": files}).encode()
    with tarfile.open(target, "w:gz") as archive:
        for name, value in [(first_name, manifest), ("data/value", content), *([] if extra is None else [extra])]:
            item = tarfile.TarInfo(name)
            item.size = len(value)
            archive.addfile(item, io.BytesIO(value))
    return target


def admit(store, path):
    raw = path.read_bytes()
    identity = hashlib.sha256(raw).hexdigest()
    store.begin(identity, len(raw))
    store.append(identity, 0, raw)
    return identity


def test_tiny_commit_with_large_per_object_limit_and_small_total_store(tmp_path):
    data = tmp_path / "source"
    data.mkdir()
    (data / "result.json").write_text('{"result":"small"}')
    archive = tmp_path / "packed.tar.gz"
    packed = pack(data, archive)
    store = ObjectStore(tmp_path / "store", max_object_mb=128, max_store_mb=1, min_free_mb=1)
    identity = admit(store, archive)
    assert identity == packed["object_sha256"]
    expanded, members = object_expansion_budget(archive, max_bytes=128 << 20)
    assert expanded < 1024 and members == 2
    assert store.commit(identity)["state"] == "committed"
    assert store.get(identity)[1] == packed["content_manifest"]


def test_false_small_declaration_cannot_expand_past_reserved_budget(tmp_path):
    payload = b"x" * (2 << 20)
    archive = malformed(tmp_path, {"value": {"bytes": 1, "sha256": hashlib.sha256(payload).hexdigest()}}, payload)
    store = ObjectStore(tmp_path / "store", max_object_mb=4, max_store_mb=1, min_free_mb=1)
    identity = admit(store, archive)
    with pytest.raises(ValueError, match="extraction limits"):
        store.commit(identity)
    assert not store.directory(identity).exists()
    assert not list((store.root / "uploads").glob(".verify-*"))


@pytest.mark.parametrize("size", [-1, True, "1", 1.5])
def test_manifest_sizes_are_strict_nonnegative_integers(tmp_path, size):
    archive = malformed(tmp_path, {"value": {"bytes": size, "sha256": "a"*64}}, b"x")
    with pytest.raises(ValueError, match="nonnegative integer"):
        object_expansion_budget(archive, max_bytes=4 << 20)


@pytest.mark.parametrize("name", ["../escape", "other.json"])
def test_manifest_must_be_first_canonical_member(tmp_path, name):
    archive = malformed(tmp_path, {"value": {"bytes": 1, "sha256": "a"*64}}, b"x", first_name=name)
    with pytest.raises(ValueError, match="start with bounded regular|unsafe"):
        object_expansion_budget(archive, max_bytes=4 << 20)


@pytest.mark.parametrize("extra", [b"ignored", b""])
def test_extra_undeclared_bytes_do_not_escape_the_budget(tmp_path, extra):
    payload = b"x"
    archive = malformed(tmp_path, {"value": {"bytes": 1, "sha256": hashlib.sha256(payload).hexdigest()}}, payload,
                        extra=("data/extra", extra))
    store = ObjectStore(tmp_path / "store", max_object_mb=4, max_store_mb=1, min_free_mb=1)
    identity = admit(store, archive)
    with pytest.raises(ValueError, match="extraction limits"):
        store.commit(identity)
