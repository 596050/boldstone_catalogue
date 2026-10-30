from __future__ import annotations

from .errors import Blocked, IntegrityError, RemoteError
from .util import canonical, digest, native_reference, parent_path, utc_now, within_path


def binding_payload(config):
    dbx = config.dropbox
    return {
        key: dbx.get(key)
        for key in (
            "app_key",
            "expected_account_id",
            "verified_namespace_id",
            "verified_root_folder_id",
            "known_file_ids",
        )
    }


def binding_hash(config):
    return digest(binding_payload(config))


def discover(adapter, path_hint):
    native_reference(path_hint)
    account = adapter.account()
    info = account.get("root_info", {})
    candidates = []
    for namespace in dict.fromkeys([info.get("root_namespace_id"), info.get("home_namespace_id")]):
        if not namespace:
            continue
        scoped = adapter.with_namespace(namespace)
        try:
            metadata = scoped.metadata(path_hint)
            candidates.append({"namespace_id": namespace, "metadata": metadata})
        except RemoteError as exc:
            candidates.append({"namespace_id": namespace, "error": exc.public()})
    return {
        "objective_outcome": "DISCOVERY_ONLY_NOT_CONFIRMED",
        "account": account,
        "candidates": candidates,
        "historical_hint_is_not_authority": True,
    }


class RootScope:
    def __init__(self, state, run, adapter, *, config=None, confirming=False):
        self.state, self.run = state, run
        self.config = config or state.config
        dbx = self.config.dropbox
        required = [
            dbx.get(k)
            for k in ("expected_account_id", "verified_namespace_id", "verified_root_folder_id")
        ]
        if not all(required) or len(set(dbx.get("known_file_ids", []))) < 2:
            raise Blocked(
                "Confirm the account, native namespace, root ID and two known file IDs first"
            )
        self.binding = binding_hash(self.config)
        if (
            not confirming
            and not state.conn.execute(
                "SELECT 1 FROM root_bindings WHERE binding_sha256=?", (self.binding,)
            ).fetchone()
        ):
            raise Blocked("Configured scope has no matching local operator confirmation")
        account = adapter.account()
        if account.get("account_id") != dbx["expected_account_id"]:
            raise Blocked("Authorized Dropbox account does not match the confirmed account")
        self.adapter = adapter.with_namespace(dbx["verified_namespace_id"])
        run.bind(
            account["account_id"], dbx["verified_namespace_id"], dbx["verified_root_folder_id"]
        )
        self.root = self.adapter.metadata(dbx["verified_root_folder_id"])
        if self.root.get("id") != run.root_id or self.root.get(".tag") != "folder":
            raise Blocked("Confirmed root ID did not resolve as the expected folder")
        self.path = self.root.get("path_lower")
        if not self.path or not self.path.startswith("/"):
            raise Blocked("Root metadata lacks a usable native namespace-relative folder path")
        self._parents = {self.path: self.root}
        with state.conn:
            state.observe(run, account, "users/get_current_account", outcome="account_checked")
            state.observe(run, self.root, "files/get_metadata", outcome="root_checked")
        self.sentinels = [
            self.resolve(asset_id, expected_kind="file") for asset_id in dbx["known_file_ids"]
        ]

    def resolve(self, asset_id, *, expected_kind=None):
        if not native_reference(asset_id).startswith("id:"):
            raise IntegrityError("Existing objects must be resolved by stable ID")
        try:
            metadata = self.adapter.metadata(asset_id)
        except RemoteError as exc:
            with self.state.conn:
                self.state.observe(
                    self.run,
                    {"id": asset_id, "error": exc.public()},
                    "files/get_metadata",
                    outcome=exc.kind,
                )
            raise
        if metadata.get("id") != asset_id:
            raise IntegrityError("Metadata response returned a different stable ID")
        if expected_kind and metadata.get(".tag") != expected_kind:
            raise IntegrityError("Resolved object has the wrong kind")
        path = metadata.get("path_lower")
        if not within_path(path, self.path):
            with self.state.conn:
                self.state.observe(
                    self.run, metadata, "files/get_metadata", outcome="outside_confirmed_root"
                )
            raise Blocked("Object is outside the confirmed root", details={"asset_id": asset_id})
        ancestors = []
        if asset_id != self.root["id"]:
            current = parent_path(path)
            while True:
                if not within_path(current, self.path):
                    raise Blocked("Object ancestry escaped the confirmed root")
                parent = self._parents.get(current)
                if parent is None:
                    parent = self.adapter.metadata(current)
                    if (
                        parent.get(".tag") != "folder"
                        or parent.get("path_lower") != current
                        or not parent.get("id")
                    ):
                        raise IntegrityError("Parent folder metadata is inconsistent")
                    self._parents[current] = parent
                    with self.state.conn:
                        self.state.observe(
                            self.run, parent, "files/get_metadata", outcome="ancestry_checked"
                        )
                ancestors.append(parent["id"])
                if current == self.path:
                    if parent["id"] != self.root["id"]:
                        raise Blocked("Ancestry reached a different stable root ID")
                    break
                current = parent_path(current)
        metadata = {
            **metadata,
            "parent_folder_id": ancestors[0] if ancestors else None,
            "ancestor_folder_ids": ancestors,
        }
        with self.state.conn:
            self.state.observe(self.run, metadata, "files/get_metadata", outcome="in_scope")
        return metadata

    def list_all(self, folder_id, *, recursive=False):
        self.resolve(folder_id, expected_kind="folder")
        cursor, seen, entries = None, set(), []
        while True:
            page = self.adapter.list_folder(folder_id, recursive=recursive, cursor=cursor)
            evidence = self.state.evidence(page.raw, "listing")
            for entry in page.entries:
                if not within_path(entry.get("path_lower"), self.path):
                    raise IntegrityError("Listing returned an entry outside the confirmed root")
            with self.state.conn:
                self.state.event(
                    "folder",
                    folder_id,
                    "read_only_listing_page",
                    {
                        "cursor_sha256": digest(page.cursor),
                        "has_more": page.has_more,
                        "entries": len(page.entries),
                        "evidence": evidence,
                    },
                    self.run.id,
                )
            entries.extend(page.entries)
            if not page.has_more:
                return entries
            if not page.cursor or page.cursor in seen:
                raise IntegrityError("Listing pagination stalled")
            seen.add(page.cursor)
            cursor = page.cursor


def confirm_root(state, run, adapter, config, *, acknowledgement):
    if acknowledgement != config.dropbox.get("verified_root_folder_id"):
        raise Blocked("Local confirmation must match the exact root folder ID shown")
    scope = RootScope(state, run, adapter, config=config, confirming=True)
    with state.conn:
        state.conn.execute(
            "INSERT OR IGNORE INTO root_bindings VALUES (?,?,?,?,?,?,?)",
            (
                scope.binding,
                utc_now(),
                run.account_id,
                run.namespace_id,
                run.root_id,
                canonical(config.dropbox["known_file_ids"]),
                canonical(
                    {
                        "root": scope.root,
                        "known_files": scope.sentinels,
                        "confirmation": "operator_typed_exact_stable_root_id",
                    }
                ),
            ),
        )
        state.event("root", run.root_id, "root_scope_confirmed", binding_payload(config), run.id)
    config.save()
    return {
        "objective_outcome": "ROOT_CONFIRMED",
        "binding_sha256": scope.binding,
        "root": scope.root,
        "account_id": run.account_id,
        "namespace_id": run.namespace_id,
        "known_file_ids": config.dropbox["known_file_ids"],
        "content_writes": False,
    }
