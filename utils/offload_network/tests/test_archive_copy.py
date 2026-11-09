"""Independent archive copies and unchanged object-commit verification."""
import errno
import pytest

from research_workflows import archive_copy, objects


def test_portable_fallback_is_an_independent_byte_copy(tmp_path, monkeypatch):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.write_bytes(b"unchanged source")
    monkeypatch.setattr(archive_copy, "_clone", lambda *_: False)
    assert archive_copy.copy(source, destination) == "copy"
    assert source.read_bytes() == destination.read_bytes()
    destination.write_bytes(b"changed destination")
    assert source.read_bytes() == b"unchanged source"


def test_existing_destination_and_source_links_are_not_overwritten(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.write_bytes(b"source")
    destination.write_bytes(b"retained")
    with pytest.raises(FileExistsError):
        archive_copy.copy(source, destination)
    assert destination.read_bytes() == b"retained"
    link = tmp_path / "link"
    link.symlink_to(source)
    with pytest.raises(ValueError, match="regular file"):
        archive_copy.copy(link, tmp_path / "new")
    with pytest.raises(FileExistsError):
        archive_copy.copy(source, link)


def test_unexpected_partial_clone_is_retained_not_overwritten(tmp_path, monkeypatch):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.write_bytes(b"source")
    def partial(_source, output):
        output.write_bytes(b"ambiguous retained bytes")
        return False
    monkeypatch.setattr(archive_copy, "_clone", partial)
    with pytest.raises(FileExistsError):
        archive_copy.copy(source, destination)
    assert destination.read_bytes() == b"ambiguous retained bytes"


def test_io_failure_is_not_silently_retried_as_a_copy(tmp_path, monkeypatch):
    source = tmp_path / "source"; source.write_bytes(b"source")
    def failure(*_):
        raise OSError(errno.EIO, "controlled clone I/O failure")
    monkeypatch.setattr(archive_copy, "_clone", failure)
    with pytest.raises(OSError, match="clone I/O failure"):
        archive_copy.copy(source, tmp_path / "destination")


def test_a_hardlink_cannot_substitute_for_an_independent_clone(tmp_path, monkeypatch):
    source = tmp_path / "source"; source.write_bytes(b"source")
    def linked(original, destination):
        destination.hardlink_to(original)
        return True
    monkeypatch.setattr(archive_copy, "_clone", linked)
    with pytest.raises(ValueError, match="file identity"):
        archive_copy.copy(source, tmp_path / "destination")
    assert source.read_bytes() == b"source"


def test_clone_completion_does_not_skip_object_archive_hash_check(tmp_path, monkeypatch):
    source = tmp_path / "source"; source.mkdir(); (source / "data").write_bytes(b"payload")
    archive = tmp_path / "archive.tar.gz"
    identity = objects.pack(source, archive)["object_sha256"]
    store = objects.ObjectStore(tmp_path / "store", max_object_mb=4, min_free_mb=1)
    payload = archive.read_bytes()
    store.begin(identity, len(payload)); store.append(identity, 0, payload)
    def corrupt_clone(_source, destination):
        destination.write_bytes(b"invalid returned clone")
        return True
    monkeypatch.setattr(archive_copy, "_clone", corrupt_clone)
    with pytest.raises(ValueError, match="object copy verification failed"):
        store.commit(identity)
    assert not (store.directory(identity) / "COMMITTED.json").exists()
    assert (store.root / "uploads" / (identity + ".part")).read_bytes() == payload
