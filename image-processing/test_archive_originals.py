"""Lossless preservation checks use local synthetic originals only."""
import json
import warnings
import zipfile

import archive_bmp_originals as archive_worker
import pytest
from PIL import Image


@pytest.fixture
def archive_fixture(tmp_path, monkeypatch):
    run = tmp_path / "conversion"
    run.mkdir()
    monkeypatch.setattr(archive_worker, "ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr(archive_worker, "ARCHIVE", tmp_path / "archive/originals.zip")
    monkeypatch.setattr(archive_worker, "CHECKS", tmp_path / "checks")
    plan = tmp_path / "plan.json"
    row = {"source_id": "id:source", "source_path": archive_worker.w.ROOT_PATH + "/Family/Leaf/image.bmp",
           "status": "ELIGIBLE"}
    plan.write_text(json.dumps({"rows": [row]}))
    monkeypatch.setattr(archive_worker.w, "PLAN_PATH", plan)
    monkeypatch.setattr(archive_worker.w, "validate_plan", lambda _: None)
    return run, row


@pytest.mark.parametrize("source_format", ["BMP", "JPEG"])
def test_converted_originals_of_both_supported_formats_can_be_restored(archive_fixture, monkeypatch, source_format):
    run, _ = archive_fixture
    original = run / "original.bmp"
    Image.new("RGB", (17, 23), "red").save(original, source_format)
    state = {"work_directory": str(run), "backup": archive_worker.w.fingerprint(original),
             "source_head": {"id": "id:source"}, "output_head": {"id": "id:jpeg"},
             "local_jpeg": {"dimensions": [17, 23], "source_format": source_format}}
    monkeypatch.setattr(archive_worker.w, "saved_state", lambda _: state)
    before = original.read_bytes()
    archive_worker.main()
    proof = json.loads((archive_worker.ARCHIVE_DIR / "RESTORE-VERIFICATION.json").read_text())
    assert proof["status"] == "PASS"
    assert proof["records"][0]["restore_and_decode_passed"]
    assert original.read_bytes() == before
    archived_bytes = archive_worker.ARCHIVE.read_bytes()
    archive_worker.main()
    assert archive_worker.ARCHIVE.read_bytes() == archived_bytes


def test_duplicate_archive_members_cannot_receive_a_passing_proof(archive_fixture, monkeypatch):
    run, _ = archive_fixture
    original = run / "original.bmp"
    Image.new("RGB", (17, 23), "red").save(original, "BMP")
    state = {"work_directory": str(run), "backup": archive_worker.w.fingerprint(original),
             "source_head": {"id": "id:source"}, "output_head": {"id": "id:jpeg"},
             "local_jpeg": {"dimensions": [17, 23], "source_format": "BMP"}}
    monkeypatch.setattr(archive_worker.w, "saved_state", lambda _: state)
    archive_worker.main()
    proof = archive_worker.ARCHIVE_DIR / "RESTORE-VERIFICATION.json"
    proof.unlink()
    (archive_worker.CHECKS / "archive-proof.json").unlink()
    with zipfile.ZipFile(archive_worker.ARCHIVE, "a") as archive, warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        archive.writestr("README.txt", "unreviewed duplicate entry")
    with pytest.raises(archive_worker.w.SetupError, match="member list"):
        archive_worker.main()
    assert not proof.exists()
