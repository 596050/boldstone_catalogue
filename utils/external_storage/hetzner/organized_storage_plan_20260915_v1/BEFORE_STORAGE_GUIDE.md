# Hetzner Storage Box backup and recovery

`storage_box.py` provisions a Storage Box through Hetzner's API and uses **Restic
over SFTP on port 23** to upload files/folders and recover previous versions. It
runs on the client; no server or Restic installation inside the Box is needed.
Python 3.10+, Restic 0.17+, and OpenSSH are required. The tested environment is
macOS with Python 3.14.7 and Restic 0.19.1. Python uses only its standard library.

The Box contains an **encrypted, deduplicated Restic repository**, not browsable
copies of your original folders. Recover through this script or standard Restic.
Files recover to their original byte contents. Ordinary SFTP downloads of the
repository packs do not decrypt them.

The default is **BX21 / 5 TB in Falkenstein (`fsn1`)**. The earlier
[capacity assessment](assessment_20260914_v1/README.md) measured about 780 GB in
the three primary IQFeed/macro archives and 1.515 TB across the reachable drive.
`plans` retrieves current prices for your account; no subscription price is
hardcoded in this script. No paid Box, upload, schedule or live Hetzner restore
was created during implementation.

## Install and preview

On macOS:

```sh
brew install restic
cd /Users/tprice/Developer/marketmaker_v2
python3 utils/external_storage/hetzner/storage_box.py setup
```

The preview needs no credentials and makes no local or remote changes. On Linux,
install a current Restic release and an OpenSSH client using your package manager
or Restic's release instructions.

Global options go **before** the command. By default, configuration, SSH keys,
passwords and small operation receipts live outside Git in:

```text
~/.config/marketmaker-storagebox/market-data/
```

Use `--profile another-name` for a separate repository, or `--config-dir PATH`
to select a different parent directory. Do not put this directory inside a
folder you plan to back up. Do not run this module through the external-storage
package: invoke the standalone file as shown.

## Create the Box

Create a **read/write API token in the appropriate Hetzner Console project**,
under Security → API Tokens. Supply it in `HETZNER_API_TOKEN` (or `HCLOUD_TOKEN`)
through your secret manager or a hidden terminal prompt. The script does not
save the token. Never put the actual token into Git or shell-history commands.

For a hidden prompt in this workspace's zsh shell:

```sh
read -rs 'HETZNER_API_TOKEN?Hetzner API token: '
export HETZNER_API_TOKEN
python3 utils/external_storage/hetzner/storage_box.py plans
python3 utils/external_storage/hetzner/storage_box.py setup --apply
unset HETZNER_API_TOKEN
```

**`setup --apply` can order a paid resource.** It creates or reuses the exact
named Box, waits for provisioning, enables SSH and external access, verifies
Hetzner's published SSH host-key fingerprint, and initializes the repository.
New Boxes receive a dedicated SSH public key. Other file-sharing protocols are
disabled on newly created Boxes. Example alternatives:

```sh
python3 utils/external_storage/hetzner/storage_box.py --profile archive2 setup \
  --name archive2 --type bx21 --location hel1 --repository-path raw-v1 --apply
```

Rerun with the **same profile, name, type, location and repository path** after a
failure. The script records the Box ID before waiting. If an order response is
lost, it looks up the exact name on retry; it never automatically retries an
ambiguous order POST. A mismatched existing Box is rejected. It does not resize,
delete or replace Boxes. Boxes remain billable until you cancel them separately
in Hetzner Console.

If a pre-existing Box has the same name, its SSH key is not automatically
replaced: authorize this profile's public key using Hetzner's SSH-key
instructions, or connect using an already authorized key as below. A failed
repository/password check never resets or overwrites the repository.

## Connect an existing Box or recover on a replacement computer

Enable SSH support and external reachability in Console. Use an SSH private key
that is already authorized on that Box. The password file is the **Restic
repository password**, not the Box's SFTP login password.

```sh
python3 utils/external_storage/hetzner/storage_box.py --profile recovered connect \
  --host u123456.your-storagebox.de --username u123456 \
  --identity-file /safe/location/id_ed25519 \
  --password-file /safe/location/restic-password \
  --repository-path market-data-v1 \
  --repository-id REPLACE_WITH_SAVED_64_CHARACTER_REPOSITORY_ID
```

For a new, empty repository on an existing Box, omit `--repository-id` and add
`--initialize`; first create a strong repository password file using your secret
manager. `connect` otherwise only opens an existing repository. Repeating the
same connection is supported if networking failed; a saved profile cannot be
silently redirected to another repository or password.

After setup, **keep an encrypted offline copy of the entire profile directory**,
separate from the Mac and the Storage Box. Important contents:

| File | Purpose |
| --- | --- |
| `profile.json` | Box address, repository location and immutable repository ID |
| `restic-password` | Required to decrypt backups; losing every copy makes recovery impossible |
| `id_ed25519` and `.pub` if present | Dedicated SSH access key; Box access can also be reauthorized through Hetzner |
| `box-login-password` if present | Initial Box login password generated during setup; not the encryption password |
| `known_hosts` | Verified SSH host key |
| `receipts/` and `restores/` | Operation outcomes and identities needed to resume a restore |

The generated private key has no interactive passphrase so scheduled backups
can run unattended. Profile directories are mode 700 and generated files mode
600 on POSIX systems. Protect the machine account and offline copy accordingly.
Copied profile paths are relative, so placing the whole directory under the same
configuration parent on a replacement computer works. `status` checks the saved
repository identity. Upload, restore and checks do not need the API token.

## Upload folders and individual files

First use a small disposable folder for a live trial, then recover it to a new
directory and compare its contents. After the Toshiba organization has completed,
upload the two organized data roots as one snapshot:

```sh
python3 utils/external_storage/hetzner/storage_box.py upload \
  "/Volumes/Toshiba 2TB/raw_price_data" \
  "/Volumes/Toshiba 2TB/other_data" \
  --group organized-data --require-mount "/Volumes/Toshiba 2TB" --dry-run
```

Remove `--dry-run` for the actual upload. Any mixture of folders and individual
files is accepted. Use absolute real paths; quote paths containing spaces.
Selecting a symlinked root is rejected; symlinks **inside** selected directories
are preserved as links. These roots include the organized sources, metadata,
receipts, retained research and caches. Check the organization readiness report
first: while moves remain pending, these two roots alone are not a complete backup.

The script checks that `/Volumes/...` sources are mounted. For the registered
Toshiba volume, it also checks the identity token and actual volume UUID against
`data_paths.json`. `--require-mount` can enforce another mount on Linux or macOS.
It refuses missing roots, its own secrets, and a local backup repository as
sources. It does not create staging ZIPs or modify/delete source files.

Rerun the same upload to save changes. Each successful run has a dated snapshot;
previous versions and files deleted from the source remain in older snapshots.
Restic deduplicates existing chunks. The wrapper uses `backup --force`: it
rereads all selected bytes so a same-size change with a preserved timestamp is
still captured. This costs local I/O, even when few new bytes need uploading.
It disables Restic's persistent local cache; memory and network metadata costs
still grow with the repository. Use completed acquisition batches for frequent
updates, and keep a consistent `--group` for each source set.

A successful upload means Restic completed the requested file traversal and
stored a snapshot. It is **not an atomic filesystem or database snapshot** and
does not establish source completeness, price accuracy or point-in-time data
availability. Stop relevant writers or select finalized batches. Use SQLite's
backup mechanism for an actively written database. Restic cannot prove that a
live file remained unchanged throughout the entire acquisition and transfer.

Exit code zero marks the snapshot `storagebox.complete`. Restic exit code 3
(unreadable/incomplete files) is a failure even when Restic saved a snapshot;
that snapshot retains `storagebox.pending`. `latest` selects only completed
snapshots. All attempts retain local receipts; inspect failures rather than
treating a partially saved snapshot as a completed upload.

## Inspect and recover

```sh
python3 utils/external_storage/hetzner/storage_box.py snapshots --group primary-raw
python3 utils/external_storage/hetzner/storage_box.py snapshots --all
python3 utils/external_storage/hetzner/storage_box.py ls latest --group primary-raw
python3 utils/external_storage/hetzner/storage_box.py recover latest \
  --group primary-raw --target "/Volumes/Recovery Disk/restored-raw" --dry-run
```

Remove `--dry-run` to restore. Choose a destination with enough space, preferably
on a separate drive; the Toshiba capacity assessment found very little free
space. The destination must be new or empty and must not overlap the source-code
tree, secret profile or backup repository. Recovery refuses symlink components.

Full recovery preserves the original path below the destination. For example,
`/Volumes/Toshiba 2TB/raw_price_data/iqfeed_archive/file.csv` appears at
`TARGET/Volumes/Toshiba 2TB/raw_price_data/iqfeed_archive/file.csv`. To recover just
one folder's **contents** directly into a destination:

```sh
python3 utils/external_storage/hetzner/storage_box.py recover SNAPSHOT_ID \
  --target "/Volumes/Recovery Disk/iqfeed-restored" \
  --subtree "/Volumes/Toshiba 2TB/raw_price_data/iqfeed_archive"
```

To select a file or subset, use paths from `ls` and repeat `--include` as needed.
Patterns are interpreted by Restic and relative to the selected subtree:

```sh
python3 utils/external_storage/hetzner/storage_box.py recover SNAPSHOT_ID \
  --target "/Volumes/Recovery Disk/selected-files" \
  --subtree "/Volumes/Toshiba 2TB/raw_price_data/iqfeed_archive" \
  --include "/relative-folder/file.csv"
```

Use the dry run to confirm that the selection matches the intended files.
Include patterns that match nothing are treated as an error.
Restores always use `--verify`, which rereads restored file contents and checks
them against the repository. A failed or interrupted restore retains the
resolved full snapshot ID in the profile's restore receipt. Resume with that
**exact ID, target and selection**, adding `--resume`; do not use a moving
`latest` if another backup has since completed. Resume checks existing file
content and repairs missing/damaged chunks. It never deletes extra target files.

## Integrity, interruption and regular updates

```sh
python3 utils/external_storage/hetzner/storage_box.py verify
python3 utils/external_storage/hetzner/storage_box.py verify --read-data
python3 utils/external_storage/hetzner/storage_box.py status
```

`verify` checks repository structure and references. **`verify --read-data` also
reads every stored pack and cryptographically verifies its contents**. This
downloads the repository data through the client and can take considerable time
and transfer allowance; it is not automatically run after every upload. Keep a
periodic full check and representative restore trial, and retain the original
drive until the remote recovery trial succeeds. Restic completion tags describe
upload completion, not independent full-repository readback verification.

If an upload stops, rerun the same command. Completed chunks can be reused;
interrupted work is retained. Local kernel locks prevent overlapping runs of
one profile. Restic also coordinates repository locks. If Restic reports a stale
remote lock, first confirm that no process on any client still uses the
repository, then follow Restic's manual unlock procedure. The wrapper never
automatically unlocks, prunes, forgets, mirror-deletes or cancels resources.

Run the same `upload` command from your existing scheduler after each finalized
collector batch. A daily macOS `launchd` job or Linux `systemd` timer can invoke
the standalone command with an absolute Python/script path and a PATH containing
Restic and OpenSSH. The machine and source drive must be available; use
`caffeinate -i` around a long initial upload on macOS if needed. Check the exit
code and receipts before reporting a batch as backed up. No schedule is installed
by this script, and no API token is needed in the scheduled job.

This updates **stored files**. It does not fetch new IQFeed prices or macro
releases, advance existing collectors' sealed cutoffs, or supply publication and
vintage clocks that were absent from the source. Those collectors and their
existing provenance records remain separate. Restic snapshots share the same
Box; they are not an independent off-provider backup.

## Validation and authoritative references

```sh
python3 -m unittest discover -s utils/external_storage/hetzner/tests -v
```

Tests use real local Restic repositories for backup/version recovery, hidden and
binary files, symlinks, deduplication, unchanged timestamps, dry runs, incomplete
backups, corruption, secret isolation and destination guards. A separate test
uses a real local OpenSSH SFTP server over pipes, including a repository home
with spaces. Hetzner HTTP and SSH host-key tests use isolated fixtures. Passing
them is not a configured-host
SFTP trial or evidence of live Hetzner upload speed, quota or recoverability.

Implementation references checked 14 September 2026:

- [Hetzner API reference](https://docs.hetzner.cloud/reference/hetzner) and
  [OpenAPI specification](https://docs.hetzner.cloud/hetzner.spec.json). The API
  base is `https://api.hetzner.com/v1`; create requires a Box login password and
  accepts public SSH key **strings**. Box creation is asynchronous.
- [Storage Box creation](https://docs.hetzner.com/storage/storage-box/getting-started/creating-a-storage-box/),
  [SSH/SFTP access](https://docs.hetzner.com/storage/storage-box/access/access-ssh-rsync-borg/),
  and [published host fingerprints](https://docs.hetzner.com/storage/storage-box/general/).
- [Restic repository preparation](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html),
  [backup behaviour](https://restic.readthedocs.io/en/stable/040_backup.html),
  [integrity checks](https://restic.readthedocs.io/en/stable/045_working_with_repos.html),
  and [restoring files](https://restic.readthedocs.io/en/stable/050_restore.html).
