import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from dropbox.files import FileMetadata, FolderMetadata

spec = importlib.util.spec_from_file_location("image_auth", Path(__file__).with_name("authorize.py"))
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


def identity():
    account = SimpleNamespace(
        account_id="dbid:test",
        email=auth.EXPECTED_EMAIL,
        email_verified=True,
        root_info=SimpleNamespace(root_namespace_id=auth.NAMESPACE_ID),
    )
    root = FolderMetadata(name="01 Wall Sculptures", id=auth.ROOT_ID, path_display=auth.ROOT_PATH)
    return account, root


def test_wrong_account_namespace_or_root_fails():
    for field, value in [("email", "different@example.com"), ("email_verified", False)]:
        account, root = identity()
        setattr(account, field, value)
        with pytest.raises(auth.SetupError):
            auth.verify_identity(account, root, account.account_id)
    account, root = identity()
    account.root_info.root_namespace_id = "different"
    with pytest.raises(auth.SetupError):
        auth.verify_identity(account, root, account.account_id)
    for changes in [dict(id="id:other"), dict(path_display="/different")]:
        account, root = identity()
        for k, v in changes.items():
            setattr(root, k, v)
        with pytest.raises(auth.SetupError):
            auth.verify_identity(account, root, account.account_id)


def test_exact_scopes_required():
    auth.verify_scopes(" ".join(auth.SCOPES))
    for scopes in [auth.SCOPES[:-1], (*auth.SCOPES, "sharing.write"), None]:
        with pytest.raises(auth.SetupError):
            auth.verify_scopes(scopes)


def test_keychain_denial_is_sanitized():
    class Denied:
        def set_password(self, *args):
            raise RuntimeError("sensitive-detail-that-must-not-be-logged")

    with pytest.raises(auth.SetupError) as caught:
        auth.check_storage(Denied())
    assert "sensitive-detail" not in str(caught.value)
    assert "authorization has not started" in str(caught.value)


def test_readback_failure_cleans_probe():
    class Corrupt:
        removed = False

        def set_password(self, *args):
            pass

        def get_password(self, *args):
            return "incorrect"

        def delete_password(self, *args):
            self.removed = True

    backend = Corrupt()
    with pytest.raises(auth.SetupError):
        auth.check_storage(backend)
    assert backend.removed


def test_runtime_artifact_permissions_and_symlink_rejection(tmp_path):
    destination = tmp_path / "runtime" / "state.json"
    auth.private_json(destination, {"status": "pending"})
    assert destination.stat().st_mode & 0o777 == 0o600
    assert destination.parent.stat().st_mode & 0o777 == 0o700
    link = tmp_path / "link.json"
    link.symlink_to(destination)
    with pytest.raises(auth.SetupError):
        auth.private_json(link, {})


def test_account_binding_and_folder_type():
    account, root = identity()
    with pytest.raises(auth.SetupError):
        auth.verify_identity(account, root, "dbid:unrelated")
    file = FileMetadata(name="01 Wall Sculptures", id=auth.ROOT_ID, path_display=auth.ROOT_PATH)
    with pytest.raises(auth.SetupError):
        auth.verify_identity(account, file, account.account_id)
    assert auth.verify_identity(account, root, account.account_id)["credential_storage"] == "macOS Keychain"
