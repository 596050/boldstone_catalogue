from __future__ import annotations

import hashlib
import io
from datetime import datetime
from pathlib import Path

import convert_bmps as worker
import pytest
from dropbox.files import FileMetadata, FolderMetadata
from PIL import Image, JpegImagePlugin


def bitmap_bytes(fmt="BMP", mode="RGB"):
    image = Image.new(mode, (37, 29))
    for x in range(37):
        for y in range(29):
            value = (x * 6, y * 8, (x + y) * 3)
            if mode == "RGBA":
                value += (80,)
            image.putpixel((x, y), value)
    stream = io.BytesIO()
    image.save(stream, fmt)
    return stream.getvalue()


def meta(identifier, path, data, rev="0000000000001"):
    block_hash = hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()
    return FileMetadata(id=identifier, name=Path(path).name, path_display=path,
                        path_lower=path.casefold(), size=len(data), rev=rev,
                        content_hash=block_hash, client_modified=datetime(2026, 10, 1),
                        server_modified=datetime(2026, 10, 2))


class FakeAPI:
    def __init__(self, row):
        self.row = row
        self.uploads = 0
        self.metadata_calls = 0
        self.mutate_before_upload = False
        self.corrupt_download = False
        self.lose_upload_response = False
        self.source_data = bitmap_bytes()
        self.source = meta(row["source_id"], row["source_path"], self.source_data)
        self.output = None
        self.output_data = None

    def metadata(self, path):
        if path in (self.row["parent_id"], self.row["family_id"]):
            prefix = "parent" if path == self.row["parent_id"] else "family"
            return FolderMetadata(id=path, name=prefix, path_display=self.row[prefix + "_path"])
        if path == self.row["source_id"]:
            self.metadata_calls += 1
            if self.mutate_before_upload and self.metadata_calls > 1:
                self.source.rev = "0000000000002"
            return self.source
        if self.output and path in (self.row["destination_path"], self.output.id):
            return self.output
        return None

    def download(self, destination, file_id, revision):
        source = file_id == self.source.id
        content = self.source_data if source else self.output_data
        if not source and self.corrupt_download:
            content = b"corrupt readback"
        Path(destination).write_bytes(content)
        return self.source if source else self.output

    def upload(self, output, destination, modified):
        assert self.output is None, "Worker must never overwrite an existing output"
        self.uploads += 1
        self.output_data = output.read_bytes()
        self.output = meta("id:jpeg", destination, self.output_data)
        if self.lose_upload_response:
            raise TimeoutError("response lost")
        return self.output


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "RUN_PATH", tmp_path / "run")
    monkeypatch.setattr(worker, "SHARED", tmp_path / "shared")
    worker.STOP.clear()
    base = worker.ROOT_PATH + "/Family/Leaf"
    row = {"source_id": "id:bmp", "source_path": base + "/image.bmp", "destination_path": base + "/image.jpg",
           "family": "Family", "family_id": "id:family", "family_path": worker.ROOT_PATH + "/Family",
           "parent_id": "id:leaf", "parent_path": base,
           "size": len(bitmap_bytes()), "client_modified": "2026-10-01T00:00:00Z", "server_modified": "2026-10-02T00:00:00Z"}
    yield row, FakeAPI(row)
    worker.STOP.clear()


def test_real_bmp_encoding_and_download_verified_without_source_change(fixture):
    row, api = fixture
    original = api.source_data
    assert worker.process(api, row) == "VERIFIED"
    assert api.uploads == 1
    assert api.source_data == original
    state = worker.saved_state(row)
    assert state["source_retained"] is True
    assert state["local_jpeg"]["dimensions"] == [37, 29]
    assert state["output_head"]["id"] == "id:jpeg"
    with Image.open(io.BytesIO(api.output_data)) as output:
        assert JpegImagePlugin.get_sampling(output) == 0
        assert all(value == 1 for table in output.quantization.values() for value in table)
    assert Path(state["work_directory"], "original.bmp").read_bytes() == original
    assert '"state": "UPLOAD_INTENT"' in (worker.SHARED / "operations.jsonl").read_text()


def test_existing_jpeg_is_held_without_upload(fixture):
    row, api = fixture
    api.output = meta("id:existing", row["destination_path"], b"existing")
    assert worker.process(api, row) == "HELD"
    assert worker.saved_state(row)["reason"] == "JPEG_DESTINATION_ALREADY_EXISTS"
    assert api.uploads == 0


def test_source_revision_change_prevents_upload(fixture):
    row, api = fixture
    api.mutate_before_upload = True
    assert worker.process(api, row) == "HELD"
    assert worker.saved_state(row)["reason"] == "SOURCE_CHANGED_DURING_CONVERSION"
    assert api.uploads == 0


def test_corrupt_uploaded_readback_never_counts_as_success(fixture):
    row, api = fixture
    api.corrupt_download = True
    assert worker.process(api, row) == "HELD"
    state = worker.saved_state(row)
    assert state["reason"] == "UPLOADED_BYTES_FAILED_INDEPENDENT_DOWNLOAD"
    assert state["source_retained"] is True


def test_unknown_upload_is_reconciled_without_second_upload(fixture):
    row, api = fixture
    api.lose_upload_response = True
    assert worker.process(api, row) == "UPLOAD_OUTCOME_UNKNOWN"
    assert worker.STOP.is_set()
    worker.STOP.clear()
    assert worker.process(api, row) == "RECONCILED_JPEG_VERIFIED"
    assert api.uploads == 1


def test_unknown_upload_with_no_destination_is_not_retried(fixture):
    row, api = fixture
    api.lose_upload_response = True
    assert worker.process(api, row) == "UPLOAD_OUTCOME_UNKNOWN"
    api.output = None
    worker.STOP.clear()
    assert worker.process(api, row) == "HELD"
    assert worker.saved_state(row)["reason"] == "UNRESOLVED_UPLOAD_INTENT_NO_AUTOMATIC_RESUBMISSION"
    assert api.uploads == 1


def test_mislabelled_jpeg_is_not_recompressed(tmp_path):
    source, output = tmp_path / "image.bmp", tmp_path / "image.jpg"
    original = bitmap_bytes("JPEG")
    source.write_bytes(original)
    result = worker.encode_jpeg(source, output)
    assert output.read_bytes() == original
    assert result["source_format"] == "JPEG"


def test_optimizer_failure_preserves_maximum_quality(tmp_path, monkeypatch):
    source, output = tmp_path / "image.bmp", tmp_path / "image.jpg"
    source.write_bytes(bitmap_bytes())
    save = Image.Image.save

    def constrained_save(self, target, format=None, **options):
        if options.get("optimize"):
            raise OSError("simulated libjpeg optimization buffer failure")
        return save(self, target, format, **options)

    monkeypatch.setattr(Image.Image, "save", constrained_save)
    result = worker.encode_jpeg(source, output)
    assert result["jpeg_huffman_optimized"] is False
    with Image.open(output) as image:
        assert image.size == (37, 29)
        assert JpegImagePlugin.get_sampling(image) == 0
        assert all(v == 1 for table in image.quantization.values() for v in table)


def test_unexpected_file_format_is_held(tmp_path):
    source, output = tmp_path / "image.bmp", tmp_path / "image.jpg"
    source.write_bytes(bitmap_bytes("PNG"))
    with pytest.raises(worker.Hold, match="UNEXPECTED_FORMAT"):
        worker.encode_jpeg(source, output)
    assert not output.exists()


def test_moved_parent_is_held(fixture):
    row, api = fixture
    original = api.metadata
    def metadata(path):
        result = original(path)
        if path == row["parent_id"]:
            result.path_display = worker.ROOT_PATH + "/Different/Leaf"
        return result
    api.metadata = metadata
    assert worker.process(api, row) == "HELD"
    assert api.uploads == 0


def test_source_hash_mismatch_is_held_before_encoding(fixture):
    row, api = fixture
    api.source.content_hash = "0" * 64
    assert worker.process(api, row) == "HELD"
    assert worker.saved_state(row)["reason"] == "SOURCE_DOWNLOAD_HASH_MISMATCH"
    assert api.uploads == 0


def test_already_verified_file_is_not_uploaded_again(fixture):
    row, api = fixture
    assert worker.process(api, row) == "VERIFIED"
    assert worker.process(api, row) == "VERIFIED"
    assert api.uploads == 1


@pytest.mark.parametrize("returned_id,returned_rev,valid", [
    ("id:bmp", "0000000000001", True),
    ("id:unrelated", "0000000000001", False),
    ("id:bmp", "0000000000002", False),
])
def test_native_revision_download_checks_identity(tmp_path, returned_id, returned_rev, valid):
    api = object.__new__(worker.API)
    destination = tmp_path / "download.bmp"

    def read(method, *args, **kwargs):
        assert method == "files_download_to_file"
        assert args == (str(destination), "rev:0000000000001")
        assert not kwargs
        return meta(returned_id, "/source.bmp", bitmap_bytes(), rev=returned_rev)

    api.read = read
    if valid:
        assert api.download(destination, "id:bmp", "0000000000001").id == "id:bmp"
    else:
        with pytest.raises(worker.Hold, match="DOWNLOAD_FILE_ID_OR_REVISION_MISMATCH"):
            api.download(destination, "id:bmp", "0000000000001")


def test_transient_native_read_timeout_is_retried(monkeypatch):
    class Client:
        attempts = 0

        def files_get_metadata(self, path):
            assert path == "id:bmp"
            self.attempts += 1
            if self.attempts == 1:
                raise worker.Timeout("temporary read failure")
            return "read completed"

    api = object.__new__(worker.API)
    api.client = Client()
    monkeypatch.setattr(worker.BUDGET, "wait", lambda: None)
    monkeypatch.setattr(worker.STOP, "wait", lambda seconds: False)
    assert api.read("files_get_metadata", "id:bmp") == "read completed"
    assert api.client.attempts == 2
