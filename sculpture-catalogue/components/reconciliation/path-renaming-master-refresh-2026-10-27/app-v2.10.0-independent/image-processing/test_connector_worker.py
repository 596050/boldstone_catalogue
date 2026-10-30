from pathlib import Path

import connector_worker as connector
import convert_bmps as worker

pytest_plugins = ["test_convert_bmps"]


def provider(api, monkeypatch):
    data_by_url = {}

    def request(method, args):
        if method == "metadata":
            obj = api.metadata(args["path_or_file_id"])
            if obj is None:
                return None
            if hasattr(obj, "rev"):
                return {"metadata_type": "file", "file": {
                    "id": obj.id, "name": obj.name, "path_display": obj.path_display,
                    "rev": obj.rev, "size": obj.size,
                    "client_modified": obj.client_modified.isoformat(),
                    "server_modified": obj.server_modified.isoformat(),
                }}
            return {"metadata_type": "folder", "folder": {
                "id": obj.id, "name": obj.name, "path_display": obj.path_display,
            }}
        if method == "download_link":
            identifier = args["entries"][0]
            obj = api.source if identifier == api.source.id else api.output
            data = api.source_data if identifier == api.source.id else api.output_data
            url = "https://unit.invalid/" + identifier
            data_by_url[url] = data
            return {"entries": [{"id": identifier, "size": obj.size,
                                  "path_display": obj.path_display, "content_hash": obj.content_hash,
                                  "download_url": url}]}
        if method == "upload":
            path = args["destination_path"].split("//", 1)[1]
            obj = api.upload(Path(args["source_file"]), "/" + path, None)
            return {"status": "completed", "file": {"file_id": obj.id}}
        if method == "download":
            data = data_by_url.pop(args["download_url"])
            Path(args["destination"]).write_bytes(data)
            return {"size": len(data)}
        raise AssertionError("Unexpected connector request")

    monkeypatch.setattr(connector, "request", request)


def test_connected_round_trip_preserves_source_and_verifies_bytes(fixture, monkeypatch):
    row, api = fixture
    original = api.source_data
    provider(api, monkeypatch)
    assert worker.process(connector.ConnectorAPI(), row) == "VERIFIED"
    assert api.source_data == original
    assert api.uploads == 1


def test_connected_revision_change_is_held(fixture, monkeypatch):
    row, api = fixture
    provider(api, monkeypatch)
    api.mutate_before_upload = True
    assert worker.process(connector.ConnectorAPI(), row) == "HELD"
    assert worker.saved_state(row)["reason"] == "SOURCE_CHANGED_DURING_CONVERSION"
    assert api.uploads == 0


def test_connected_existing_jpeg_is_held(fixture, monkeypatch):
    from test_convert_bmps import meta
    row, api = fixture
    provider(api, monkeypatch)
    api.output = meta("id:jpeg", row["destination_path"], b"existing")
    api.output_data = b"existing"
    assert worker.process(connector.ConnectorAPI(), row) == "HELD"
    assert api.uploads == 0
