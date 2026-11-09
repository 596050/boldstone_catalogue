#!/usr/bin/env python3
"""Provision Hetzner Storage Boxes and preserve/recover files using Restic.

Standalone Python 3.10+; requires Restic >= 0.17 and OpenSSH for remote use.
No import of the repository's external-storage package (or mounted-drive side effects).
See README.md next to this script for credentials, recovery and scheduling.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

API_URL = "https://api.hetzner.com/v1"
# Published by Hetzner, checked 2026-09-14. Fail closed if the key changes.
HOST_FINGERPRINT = "SHA256:XqONwb1S0zuj5A1CDxpOSuD2hnAArV1A3wKY7Z3sdgM"
COMPLETE = "storagebox.complete"
PENDING = "storagebox.pending"
DEFAULT_ROOT = Path.home() / ".config" / "marketmaker-storagebox"
REPO_ROOT = Path(__file__).resolve().parents[3]


class Error(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def emit(value):
    print(json.dumps(value, indent=2, ensure_ascii=False), flush=True)


def absolute(path):
    return Path(os.path.abspath(Path(path).expanduser()))


def no_symlinks(path):
    for part in (path, *path.parents):
        if part.is_symlink():
            raise Error(f"Symlink is not allowed in this destination/configuration path: {part}")


def private_dir(path):
    no_symlinks(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def private_write(path, content):
    """Atomic, owner-only local state; never expose a partially written secret."""
    private_dir(path.parent)
    no_symlinks(path)
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.chmod(tmp, 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_json(path, data):
    private_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def require_program(name):
    program = shutil.which(name)
    if not program:
        raise Error(f"Install {name} and put it on PATH; see README.md.")
    return program


@contextlib.contextmanager
def locked(directory):
    """Kernel lock is released on exit/crash; no automatic stale-lock deletion."""
    private_dir(directory)
    path = directory / "operation.lock"
    no_symlinks(path)
    with path.open("a+b") as stream:
        path.chmod(0o600)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                stream.seek(0)
                stream.write(b"0")
                stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise Error("Another operation is using this profile.") from exc
        try:
            yield
        finally:
            if acquired:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an API bearer credential to a redirected destination.
        return None


class Hetzner:
    def __init__(self, token=None):
        self.token = token or os.environ.get("HETZNER_API_TOKEN") or os.environ.get("HCLOUD_TOKEN")
        if not self.token:
            raise Error("Set HETZNER_API_TOKEN to a Console project read/write API token.")
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, body=None):
        if not path.startswith("/") or path.startswith("//"):
            raise Error("Invalid API path.")
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(API_URL + path, data=data, method=method, headers={
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json", "User-Agent": "marketmaker-storagebox/1",
        })
        # Mutations are NEVER automatically retried: a timed-out order may exist.
        for attempt in range(3 if method == "GET" else 1):
            try:
                with self.opener.open(req, timeout=45) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if method == "GET" and (exc.code == 429 or exc.code >= 500) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise Error(f"Hetzner {method} {path}: HTTP {exc.code}. Check Console; secrets/body omitted.") from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if method == "GET" and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                suffix = " Check Console or rerun the same setup name before ordering again." if method != "GET" else ""
                raise Error(f"Hetzner {method} {path}: connection failed ({type(exc).__name__}).{suffix}") from None
            except ValueError:
                raise Error("Hetzner returned invalid JSON; check Console before repeating any order.") from None

    def all(self, resource, **query):
        rows, page = [], 1
        while page is not None:
            result = self.request("GET", "/" + resource + "?" + urllib.parse.urlencode(
                {**query, "page": page, "per_page": 50}))
            rows.extend(result[resource])
            next_page = result.get("meta", {}).get("pagination", {}).get("next_page")
            if next_page is not None and next_page <= page:
                raise Error("Invalid API pagination.")
            page = next_page
        return rows

    def wait(self, action, timeout=900):
        deadline = time.monotonic() + timeout
        while action.get("status") == "running":
            if time.monotonic() >= deadline:
                raise Error("Hetzner action still running. Rerun setup with the SAME profile/name.")
            time.sleep(2)
            action = self.request("GET", f"/storage_boxes/actions/{int(action['id'])}")["action"]
        if action.get("status") != "success":
            raise Error(f"Hetzner action {action.get('id')} did not succeed. Inspect Console.")


class Profile:
    def __init__(self, directory):
        self.directory = absolute(directory)
        self.file = self.directory / "profile.json"
        no_symlinks(self.file)
        self.data = json.loads(self.file.read_text()) if self.file.exists() else {}
        if self.data and self.data.get("schema") != 1:
            raise Error("Unsupported profile schema.")

    def save(self):
        write_json(self.file, self.data)

    def path(self, field):
        p = Path(self.data[field]).expanduser()
        return p if p.is_absolute() else self.directory / p

    def receipt(self, name, data):
        write_json(self.directory / "receipts" / f"{name}.json", data)


def check_restic():
    binary = require_program("restic")
    result = subprocess.run([binary, "version"], capture_output=True, text=True, check=True)
    match = re.search(r"restic (\d+)\.(\d+)\.(\d+)", result.stdout)
    if not match or tuple(map(int, match.groups())) < (0, 17, 0):
        raise Error("Restic 0.17 or newer is required.")
    return binary


class Repository:
    def __init__(self, profile):
        self.profile = profile
        self.binary = check_restic()
        data = profile.data
        if not data.get("repository") or not profile.path("password_file").is_file():
            raise Error("Run setup or connect first; the repository password file is required.")
        # Reject inherited RESTIC_PASSWORD_COMMAND, RESTIC_REPOSITORY_FILE, filters, etc.
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("RESTIC_")}
        self.env.update(RESTIC_REPOSITORY=data["repository"],
                        RESTIC_PASSWORD_FILE=str(profile.path("password_file")))
        self.base = [self.binary, "--no-cache"]
        if data.get("host"):
            known_hosts = str(profile.path("known_hosts_file"))
            if any(c in known_hosts for c in ('\n', '\r', '\x00')):
                raise Error("Invalid known-hosts path.")
            # ssh parses -o values as config syntax after argv parsing; quote again
            # so a directory with spaces is one filename, and escape SSH % tokens.
            known_hosts = '"' + known_hosts.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
            ssh = [require_program("ssh"), "-F", "none", "-p", "23", "-i", str(profile.path("identity_file")),
                   "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                   "-o", "StrictHostKeyChecking=yes", "-o", "GlobalKnownHostsFile=" + os.devnull,
                   "-o", "UserKnownHostsFile=" + known_hosts,
                   "-o", "HostKeyAlgorithms=ssh-ed25519", "-o", "ConnectTimeout=20",
                   "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
                   data["username"] + "@" + data["host"], "-s", "sftp"]
            self.base += ["-o", "sftp.command=" + shlex.join(ssh), "-o", "sftp.connections=2"]

    def run(self, args, capture=False):
        return subprocess.run(self.base + args, env=self.env, text=True, encoding="utf-8",
                              stdout=subprocess.PIPE if capture else None,
                              stderr=subprocess.PIPE if capture else None)

    def successful(self, args, capture=False):
        result = self.run(args, capture=capture)
        if result.returncode:
            if capture and result.stderr:
                print(result.stderr, file=sys.stderr, end="")
            raise Error(f"Restic {args[0]} failed (exit {result.returncode}).")
        return result.stdout

    def restore(self, args, require_match=False):
        # Stream progress instead of buffering a multi-hour restore in memory.
        summary = None
        with subprocess.Popen(self.base + args + ["--json"], env=self.env, text=True,
                              encoding="utf-8", stdout=subprocess.PIPE) as process:
            for line in process.stdout:
                print(line, end="", flush=True)
                event = json.loads(line)
                if event.get("message_type") == "summary":
                    summary = event
            code = process.wait()
        if code:
            raise Error(f"Restic restore failed (exit {code}).")
        if summary is None:
            raise Error("Restic restore returned no completion summary.")
        if require_match and not summary.get("total_files", 0):
            raise Error("Recovery include patterns matched no files or directories. Check ls and the subtree.")
        return summary

    def bind(self, initialize=False):
        result = self.run(["cat", "config"], capture=True)
        if result.returncode == 10 and initialize and not self.profile.data.get("repository_id"):
            self.successful(["init", "--repository-version", "2"])
            result = self.run(["cat", "config"], capture=True)
        if result.returncode:
            if result.stderr:
                print(result.stderr, file=sys.stderr, end="")
            raise Error(f"Cannot open repository (exit {result.returncode}); it was not replaced or reset.")
        repo_id = json.loads(result.stdout)["id"]
        expected = self.profile.data.get("repository_id")
        if expected and repo_id != expected:
            raise Error("Repository identity differs from the saved profile; refusing operation.")
        if not expected:
            self.profile.data["repository_id"] = repo_id
            self.profile.save()
        return repo_id

    def snapshots(self, tag=None):
        args = ["snapshots", "--json"]
        if tag:
            args += ["--tag", tag]
        return json.loads(self.successful(args, capture=True)) or []

    def resolve(self, selector, group=None):
        tags = COMPLETE + (",group:" + group if group else "")
        rows = self.snapshots(tags)
        if selector != "latest":
            if not re.fullmatch(r"[0-9a-f]{8,64}", selector):
                raise Error("Use 'latest' or a snapshot ID (at least eight hex characters).")
            rows = [row for row in rows if row["id"].startswith(selector)]
            if len(rows) != 1:
                raise Error("Snapshot is missing, ambiguous or not marked complete by this script.")
        if not rows:
            raise Error("No completed snapshot matches. Run snapshots --all to inspect incomplete attempts.")
        return max(rows, key=lambda row: (row["time"], row["id"]))["id"]


def validate_remote(host, username, repository_path):
    if not re.fullmatch(r"u\d+(?:-sub\d+)?", username):
        raise Error("Expected a Hetzner Storage Box username such as u123456.")
    if not re.fullmatch(r"u\d+\.your-storagebox\.de", host):
        raise Error("Expected an official u123456.your-storagebox.de hostname.")
    # A single top-level folder also avoids SFTP missing-parent initialization failures.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", repository_path):
        raise Error("Repository path must be one folder name, e.g. market-data-v1.")


def pin_host(profile):
    host = profile.data["host"]
    result = subprocess.run([require_program("ssh-keyscan"), "-T", "20", "-p", "23", "-t", "ed25519", host],
                            capture_output=True, text=True)
    keys = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3 or fields[1] != "ssh-ed25519":
            continue
        digest = hashlib.sha256(base64.b64decode(fields[2], validate=True)).digest()
        fingerprint = "SHA256:" + base64.b64encode(digest).decode().rstrip("=")
        if fingerprint != HOST_FINGERPRINT:
            raise Error("SSH host key differs from Hetzner's published fingerprint. No key was accepted.")
        keys.append(f"[{host}]:23 {fields[1]} {fields[2]}")
    if not keys:
        raise Error("No verified SSH host key. Check port 23/SSH support and external reachability in Console.")
    private_write(profile.path("known_hosts_file"), "\n".join(sorted(set(keys))) + "\n")


def setup(profile, args, api=None):
    intended = {"name": args.name, "storage_box_type": args.type, "location": args.location,
                "repository_path": args.repository_path}
    if not args.apply:
        emit({"preview": True, **intended, "action": "Create or reuse this named Storage Box; initialize an encrypted Restic repository.",
              "paid_resource": True, "profile_directory": str(profile.directory),
              "next": "Run plans for account prices; add --apply to execute. No purchase or transfer performed."})
        return
    check_restic()
    require_program("ssh")
    require_program("ssh-keygen")
    require_program("ssh-keyscan")
    api = api or Hetzner()
    if profile.data and "name" not in profile.data:
        raise Error("This profile was connected manually. Use connect again or a new setup profile.")
    for key, value in intended.items():
        if profile.data.get(key, value) != value:
            raise Error(f"Existing profile has a different {key}. Use its original arguments or a different profile.")
    validate_remote("u0.your-storagebox.de", "u0", args.repository_path)
    if not profile.data:
        profile.data = {"schema": 1, **intended, "password_file": "restic-password",
                        "identity_file": "id_ed25519", "known_hosts_file": "known_hosts",
                        "created_at": now()}
        profile.save()
    password = profile.path("password_file")
    if not password.exists():
        if profile.data.get("repository_id"):
            raise Error("Repository password is missing. Recover it from your offline copy; it cannot be reset.")
        private_write(password, secrets.token_urlsafe(48) + "\n")
    login_password = profile.directory / "box-login-password"
    if not login_password.exists():
        private_write(login_password, "aA1!" + secrets.token_urlsafe(32) + "\n")
    identity = profile.path("identity_file")
    if not identity.exists():
        if profile.data.get("box_id"):
            raise Error("Saved SSH key is missing. Recover it or explicitly connect using an authorized replacement key.")
        subprocess.run([require_program("ssh-keygen"), "-q", "-t", "ed25519", "-N", "", "-C",
                        "marketmaker-storagebox", "-f", str(identity)], check=True)
        identity.chmod(0o600)
    if profile.data.get("box_id"):
        box = api.request("GET", f"/storage_boxes/{int(profile.data['box_id'])}")["storage_box"]
    else:
        matches = [b for b in api.all("storage_boxes", name=args.name) if b["name"] == args.name]
        if len(matches) > 1:
            raise Error("Multiple boxes have the requested name; inspect Console.")
        box = matches[0] if matches else None
        if box is None:
            plans = [p for p in api.all("storage_box_types") if p["name"] == args.type]
            if len(plans) != 1:
                raise Error("Unknown Storage Box type. Run plans for available types.")
            plan = plans[0]
            prices = [p for p in plan.get("prices", []) if p["location"] == args.location]
            if not prices:
                raise Error("Selected type is unavailable at this location.")
            emit({"ordering": args.name, "type": args.type, "size_bytes": plan["size"], "account_price": prices})
            result = api.request("POST", "/storage_boxes", {
                "name": args.name, "storage_box_type": args.type, "location": args.location,
                "password": login_password.read_text().strip(),
                "ssh_keys": [Path(str(identity) + ".pub").read_text().strip()],
                "labels": {"managed-by": "marketmaker-storagebox"},
                "access_settings": {"reachable_externally": True, "ssh_enabled": True,
                                    "samba_enabled": False, "webdav_enabled": False, "zfs_enabled": False},
            })
            box = result["storage_box"]
            profile.data["box_id"] = box["id"]
            profile.save()  # Persist identity BEFORE waiting for the asynchronous action.
            api.wait(result["action"])
    if (box["name"] != args.name or box["storage_box_type"]["name"] != args.type
            or box["location"]["name"] != args.location):
        raise Error("Existing Box name, type or location differs; no second Box was ordered.")
    profile.data["box_id"] = box["id"]
    profile.save()
    deadline = time.monotonic() + 900
    while True:
        box = api.request("GET", f"/storage_boxes/{int(box['id'])}")["storage_box"]
        if box["status"] == "active":
            break
        if box["status"] != "initializing" or time.monotonic() >= deadline:
            raise Error("Storage Box is not active; inspect Console and rerun the same setup.")
        time.sleep(2)
    settings = box.get("access_settings", {})
    if not settings.get("ssh_enabled") or not settings.get("reachable_externally"):
        result = api.request("POST", f"/storage_boxes/{int(box['id'])}/actions/update_access_settings",
                             {"ssh_enabled": True, "reachable_externally": True})
        api.wait(result["action"])
    validate_remote(box["server"], box["username"], args.repository_path)
    profile.data.update(host=box["server"], username=box["username"],
                        repository=f"sftp://{box['username']}@{box['server']}:23/{args.repository_path}")
    profile.save()
    pin_host(profile)
    Repository(profile).bind(initialize=True)
    emit({"setup": "complete", "box_id": box["id"], "repository": profile.data["repository"],
          "repository_id": profile.data["repository_id"], "recovery_files": str(profile.directory),
          "next": "Keep an encrypted offline copy of this entire profile directory before uploading valuable data."})


def connect(profile, args):
    validate_remote(args.host, args.username, args.repository_path)
    identity, password = absolute(args.identity_file), absolute(args.password_file)
    if not identity.is_file() or not password.is_file() or not password.read_text().strip():
        raise Error("An existing authorized SSH private key and nonempty Restic password file are required.")
    intended = {"schema": 1, "host": args.host, "username": args.username,
                    "repository_path": args.repository_path,
                    "repository": f"sftp://{args.username}@{args.host}:23/{args.repository_path}",
                    "identity_file": "id_ed25519", "password_file": "restic-password",
                    "known_hosts_file": "known_hosts", "repository_id": args.repository_id,
                    "created_at": now()}
    if profile.data:
        for key in ("host", "username", "repository", "repository_path"):
            if profile.data.get(key) != intended[key]:
                raise Error("Existing profile points elsewhere. Use a new profile for this connection.")
        if args.repository_id and profile.data.get("repository_id") not in (None, args.repository_id):
            raise Error("Repository identity differs from this profile.")
        if profile.path("password_file").read_text().strip() != password.read_text().strip():
            raise Error("Refusing to replace an existing profile's repository password.")
        if args.repository_id:
            profile.data["repository_id"] = args.repository_id
    else:
        profile.data = intended
    private_write(profile.path("identity_file"), identity.read_text())
    private_write(profile.path("password_file"), password.read_text())
    # Save a usable recovery profile even if networking is temporarily unavailable.
    profile.save()
    pin_host(profile)
    Repository(profile).bind(initialize=args.initialize)
    emit({"connected": True, "repository_id": profile.data["repository_id"],
          "recovery_files": str(profile.directory)})


def check_sources(paths, profile, required_mount=None):
    sources = [absolute(p) for p in paths]
    if required_mount and not os.path.ismount(absolute(required_mount)):
        raise Error(f"Required source mount is absent: {required_mount}")
    registry = REPO_ROOT / "data_paths.json"
    storage = json.loads(registry.read_text()).get("external_storage", {}) if registry.exists() else {}
    verified_mounts = set()
    for path in sources:
        if not path.exists():
            raise Error(f"Source is missing: {path}")
        # Resolve selected roots once. Restic preserves interior symlinks without following them.
        if path.is_symlink() or path.resolve() != path:
            raise Error(f"Select the real source path, without symlink components: {path}")
        if profile.directory.is_relative_to(path) or path.is_relative_to(profile.directory):
            raise Error("Backup source would include the secret profile directory.")
        local_repo = profile.data.get("repository", "")
        if local_repo.startswith("/"):
            repo = Path(local_repo)
            if repo.is_relative_to(path) or path.is_relative_to(repo):
                raise Error("Backup source overlaps the backup repository.")
        if sys.platform == "darwin" and len(path.parts) > 2 and path.parts[1] == "Volumes":
            mount = Path(*path.parts[:3])
            if not os.path.ismount(mount):
                raise Error(f"External drive is not mounted: {mount}")
            if str(mount) == storage.get("mount_point") and mount not in verified_mounts:
                identity = json.loads((mount / storage["identity_file"]).read_text())
                if identity.get("identity_token") != storage["identity_token"]:
                    raise Error("External-drive identity token differs from data_paths.json.")
                result = subprocess.run(["diskutil", "info", "-plist", str(mount)], capture_output=True, check=True)
                info = plistlib.loads(result.stdout)
                if info.get("VolumeUUID", "").upper() != storage["volume_uuid"].upper():
                    raise Error("External-drive volume UUID differs from data_paths.json.")
                verified_mounts.add(mount)
    return sorted(set(sources))


def upload(repo, args):
    profile = repo.profile
    sources = check_sources(args.paths, profile, args.require_mount)
    run = "upload-" + uuid.uuid4().hex
    run_tag = "run:" + run
    tags = [PENDING, run_tag, "group:" + args.group]
    command = ["backup", "--force", "--host", "storagebox-" + profile.directory.name]
    for tag in tags:
        command += ["--tag", tag]
    if args.dry_run:
        command += ["--dry-run"]
    command += ["--", *map(str, sources)]
    receipt = {"operation": "upload", "run": run, "started_at": now(),
               "repository_id": profile.data["repository_id"], "sources": list(map(str, sources)),
               "group": args.group, "dry_run": args.dry_run, "status": "running"}
    profile.receipt(run, receipt)
    try:
        result = repo.run(command)
        receipt["restic_exit_code"] = result.returncode
        if result.returncode:
            raise Error(f"Upload failed/incomplete (Restic exit {result.returncode}). Rerun the same upload; no snapshot was marked complete.")
        if args.dry_run:
            receipt["status"] = "preview"
        else:
            snapshots = repo.snapshots(run_tag)
            if len(snapshots) != 1:
                raise Error("Upload did not yield exactly one identifiable snapshot; no completion published.")
            pending_id = snapshots[0]["id"]
            receipt["pending_snapshot_id"] = pending_id
            repo.successful(["tag", "--add", COMPLETE, "--remove", PENDING, pending_id])
            completed = repo.snapshots(run_tag + "," + COMPLETE)
            if len(completed) != 1:
                raise Error("Could not confirm completed snapshot identity.")
            receipt.update(status="complete", snapshot_id=completed[0]["id"],
                           verification="Upload completed; run verify --read-data for independent stored-data verification.")
    except BaseException:
        receipt["status"] = "incomplete"
        raise
    finally:
        receipt["finished_at"] = now()
        profile.receipt(run, receipt)
    emit(receipt)


def recover(repo, args):
    snapshot = repo.resolve(args.snapshot, args.group)
    target = absolute(args.target)
    no_symlinks(target)
    protected = [repo.profile.directory, REPO_ROOT]
    if repo.profile.data["repository"].startswith("/"):
        protected.append(Path(repo.profile.data["repository"]))
    if any(target.is_relative_to(p) or p.is_relative_to(target) for p in protected):
        raise Error("Recovery destination overlaps the repository, source-code tree or secret profile.")
    subtree = args.subtree
    if subtree:
        p = PurePosixPath(subtree)
        if not p.is_absolute() or ".." in p.parts or ":" in subtree:
            raise Error("Subtree must be an absolute path from ls, with no '..' or ':'.")
    binding = {"repository_id": repo.profile.data["repository_id"], "snapshot_id": snapshot,
               "target": str(target), "subtree": subtree, "include": sorted(args.include)}
    key = hashlib.sha256(str(target).encode()).hexdigest()
    state_path = repo.profile.directory / "restores" / (key + ".json")
    previous = json.loads(state_path.read_text()) if state_path.exists() else None
    if args.resume:
        if not previous or previous.get("binding") != binding:
            raise Error("Resume requires the same snapshot ID, target and selection as the saved restore receipt.")
    elif target.exists() and (not target.is_dir() or next(target.iterdir(), None) is not None):
        raise Error("Recovery target must be new or empty. Use --resume only for a previously recorded restore.")
    command = ["restore", snapshot + (":" + subtree if subtree else ""),
               "--target", str(target), "--overwrite", "always"]
    for pattern in args.include:
        command += ["--include", pattern]
    if args.dry_run:
        command += ["--dry-run"]
        repo.restore(command, require_match=bool(args.include))
        emit({"status": "preview", **binding})
        return
    command += ["--verify"]  # Restic rejects --verify together with --dry-run.
    receipt = {"operation": "recover", "binding": binding, "started_at": now(), "status": "running"}
    write_json(state_path, receipt)  # Persist identity BEFORE writing recovered bytes.
    try:
        receipt["restic_summary"] = repo.restore(command, require_match=bool(args.include))
        receipt["status"] = "complete"
        receipt["verification"] = "Restic restore --verify reread restored file contents."
    except BaseException:
        receipt["status"] = "incomplete"
        raise
    finally:
        receipt["finished_at"] = now()
        write_json(state_path, receipt)
        repo.profile.receipt("recover-" + uuid.uuid4().hex, receipt)
    emit(receipt)


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--profile", default="market-data", help="Separate profile name (default: market-data)")
    p.add_argument("--config-dir", type=Path, default=DEFAULT_ROOT, help="Parent of profile directories")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("plans", help="List available Box types and current account prices (API token required)")
    s = sub.add_parser("setup", help="Preview or create/reuse a PAID Storage Box and initialize Restic")
    s.add_argument("--name", default="market-data")
    s.add_argument("--type", default="bx21", help="Storage Box type; bx21 is 5 TB")
    s.add_argument("--location", choices=["fsn1", "hel1"], default="fsn1")
    s.add_argument("--repository-path", default="market-data-v1")
    s.add_argument("--apply", action="store_true", help="Execute setup; a new Box incurs Hetzner charges")
    c = sub.add_parser("connect", help="Connect to an existing Box using an already authorized SSH key")
    for flag in ("host", "username", "identity-file", "password-file"):
        c.add_argument("--" + flag, required=True)
    c.add_argument("--repository-path", default="market-data-v1")
    c.add_argument("--repository-id", help="Known immutable Restic repository ID for disaster recovery")
    c.add_argument("--initialize", action="store_true", help="Initialize only if repository is absent")
    u = sub.add_parser("upload", aliases=["backup"], help="Incremental encrypted backup of files and/or folders")
    u.add_argument("paths", nargs="+")
    u.add_argument("--group", default="market-data", help="Snapshot group; use different groups for different source sets")
    u.add_argument("--require-mount", help="Fail if this source mount is absent")
    u.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("snapshots", help="List completed backups (use --all to inspect partial attempts)")
    s.add_argument("--all", action="store_true")
    s.add_argument("--group")
    ls = sub.add_parser("ls", help="List files in one completed snapshot")
    ls.add_argument("snapshot", nargs="?", default="latest")
    ls.add_argument("--group")
    ls.add_argument("--path", help="Optional absolute subtree from the snapshot")
    r = sub.add_parser("recover", aliases=["restore"], help="Restore to a separate directory and verify contents")
    r.add_argument("snapshot", nargs="?", default="latest")
    r.add_argument("--target", required=True)
    r.add_argument("--group")
    r.add_argument("--subtree", help="Restore the contents of this directory from the snapshot")
    r.add_argument("--include", action="append", default=[], help="Restic include pattern; repeat as needed")
    r.add_argument("--resume", action="store_true", help="Resume the identical recorded restore into a nonempty target")
    r.add_argument("--dry-run", action="store_true")
    v = sub.add_parser("verify", help="Check repository integrity; --read-data also downloads/verifies every pack")
    v.add_argument("--read-data", action="store_true")
    sub.add_parser("status", help="Show repository identity and local recovery-file location")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", args.profile):
            raise Error("Invalid profile name.")
        if getattr(args, "group", None) and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", args.group):
            raise Error("Group must contain only letters, numbers, dots, hyphens or underscores.")
        profile = Profile(args.config_dir / args.profile)
        if args.command == "plans":
            emit(Hetzner().all("storage_box_types"))
            return 0
        if args.command == "setup" and not args.apply:
            setup(profile, args)
            return 0
        with locked(profile.directory):
            # Re-read under the lock in case another setup completed just before us.
            profile = Profile(profile.directory)
            if args.command == "setup":
                setup(profile, args)
                return 0
            if args.command == "connect":
                connect(profile, args)
                return 0
            if not profile.data:
                raise Error("No configured profile. Start with setup or connect.")
            repo = Repository(profile)
            repo.bind()
            if args.command in ("upload", "backup"):
                upload(repo, args)
            elif args.command == "snapshots":
                tags = [] if args.all else [COMPLETE]
                if args.group:
                    tags.append("group:" + args.group)
                emit(repo.snapshots(",".join(tags) or None))
            elif args.command == "ls":
                command = ["ls", repo.resolve(args.snapshot, args.group)]
                if args.path:
                    command += ["--", args.path]
                repo.successful(command)
            elif args.command in ("recover", "restore"):
                recover(repo, args)
            elif args.command == "verify":
                run = "verify-" + uuid.uuid4().hex
                receipt = {"operation": "verify", "repository_id": profile.data["repository_id"],
                           "read_data": args.read_data, "started_at": now(), "status": "running"}
                profile.receipt(run, receipt)
                try:
                    repo.successful(["check"] + (["--read-data"] if args.read_data else []))
                    receipt["status"] = "complete"
                except BaseException:
                    receipt["status"] = "failed"
                    raise
                finally:
                    receipt["finished_at"] = now()
                    profile.receipt(run, receipt)
                emit(receipt)
            elif args.command == "status":
                emit({"repository": profile.data["repository"], "repository_id": profile.data["repository_id"],
                      "box_id": profile.data.get("box_id"), "recovery_files": str(profile.directory)})
        return 0
    except KeyboardInterrupt:
        print("Interrupted. Retain the profile/receipts and rerun the same operation; see README.md.", file=sys.stderr)
        return 130
    except (Error, OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
