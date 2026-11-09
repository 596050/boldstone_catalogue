"""A broken paginated read must stop rather than loop forever."""
from types import SimpleNamespace

import audit_conversion
import check_bmp_retirement
from dropbox.files import FolderMetadata
import pytest
import renumber_current_paths


@pytest.mark.parametrize("cursors", [["one", "one"], ["one", "two", "one"], [None], [""]])
@pytest.mark.parametrize("read_census", [audit_conversion.live_census, check_bmp_retirement.census])
def test_audits_reject_missing_and_repeated_cursors(read_census, cursors):
    class API:
        calls = 0

        def read(self, *_args, **_kwargs):
            assert self.calls < len(cursors), "Census followed an invalid cursor"
            cursor = cursors[self.calls]
            self.calls += 1
            return SimpleNamespace(entries=[], has_more=True, cursor=cursor)

    api = API()
    with pytest.raises(audit_conversion.worker.SetupError, match="pagination"):
        read_census(api)
    assert api.calls == len(cursors)


@pytest.mark.parametrize("cursors", [["one", "one"], ["one", "two", "one"], [None], [""]])
def test_filename_preflight_rejects_missing_and_repeated_cursors(cursors):
    parent = {"id": "id:parent", "name": "Leaf", "path": renumber_current_paths.WALL + "/Family/Leaf"}

    class Client:
        calls = 0

        def files_get_metadata(self, _identifier):
            return FolderMetadata(id=parent['id'], name=parent['name'], path_display=parent['path'])

        def files_list_folder(self, *_args, **_kwargs):
            assert self.calls < len(cursors), "Preflight followed an invalid cursor"
            cursor = cursors[self.calls]
            self.calls += 1
            return SimpleNamespace(entries=[], has_more=True, cursor=cursor)

        files_list_folder_continue = files_list_folder

    client = Client()
    with pytest.raises(ValueError, match="pagination"):
        renumber_current_paths.read_folder(client, parent)
    assert client.calls == len(cursors)
