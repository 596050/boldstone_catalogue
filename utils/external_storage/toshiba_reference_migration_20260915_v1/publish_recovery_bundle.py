#!/usr/bin/env python3
"""Build, restore-check and publish this migration's metadata/code handoff once."""
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from utils.data_paths import ensure_external_storage

NAME = 'toshiba_reference_migration_20260915_v1'
BUNDLE_NAME = 'toshiba_reference_migration_20260915_records.tar.gz'
MANIFEST = Path('research/utility/toshiba_data_manifest_20260913_v1')
RUN = 'run_09_organized_complete_20260915'


def sha_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    config = json.loads((ROOT / 'data_paths.json').read_text())
    identity = ensure_external_storage(force=True)
    mount = Path(config['external_storage']['mount_point'])
    for name in ('marketmaker', 'marketmaker_v2'):
        assert not (mount / name).exists()
        assert (Path('/Users/tprice/Developer') / name).is_dir()
    for name in ('FINAL_DATA_PRESERVATION.json', 'FINAL_REFERENCE_RECONCILIATION.json',
                 'FINAL_REGISTRY_VALIDATION.json', 'FINAL_IMPLEMENTATION_INVENTORY.json'):
        assert json.loads((HERE / name).read_text())['status'] == 'PASS'
    registry_sha = sha_file(ROOT / 'data_paths.json')
    assert registry_sha == json.loads((HERE / 'FINAL_REGISTRY_VALIDATION.json').read_text())['registry_sha256']

    bundle = HERE / BUNDLE_NAME
    destination = mount / 'other_data/migration' / NAME
    if bundle.exists() or destination.exists() or (mount / 'DATA_LAYOUT.md').exists():
        raise FileExistsError('Publication target already exists; inspect its receipt instead of overwriting it')
    skip = {BUNDLE_NAME, BUNDLE_NAME + '.partial', 'PUBLICATION.json', 'PUBLISH_BUNDLE.log'}
    sources = set()
    for path in HERE.rglob('*'):
        if path.is_file() and path.name not in skip and '__pycache__' not in path.parts and path.suffix != '.pyc':
            sources.add(path)
    for name in ('data_paths.json', 'utils/__init__.py', 'utils/data_paths.py', 'utils/external_storage/relocated_references.py',
                 'TOSHIBA_DATA_MANIFEST.md'):
        sources.add(ROOT / name)
    for path in (ROOT / MANIFEST).glob('*.py'):
        sources.add(path)
    for name in ('README.md', 'LATEST.json'):
        sources.add(ROOT / MANIFEST / name)
    for name in (RUN, 'run_08_organized_20260915', 'run_08_organized_20260915_supplements'):
        sources.update(path for path in (ROOT / MANIFEST / name).rglob('*')
                       if path.is_file() and path.suffix != '.pyc' and '__pycache__' not in path.parts)
    prior = ROOT / 'utils/external_storage/toshiba_organization_20260915'
    for name in ('PLAN.json', 'execution/JOURNAL.jsonl', 'reconciliation/RESULT.json',
                 'reconciliation/raw_price_data.jsonl.gz', 'reconciliation/other_data.jsonl.gz',
                 'PUBLICATION.json', 'FINAL_REPORT.md', 'LIVE_READER_INCIDENT.json',
                 'INTERRUPTED_REPLAY_OUTPUTS.json', 'FROZEN_SPEC_SOURCE_BINDINGS.json'):
        sources.add(prior / name)
    for path in (ROOT / 'utils/external_storage/hetzner').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            sources.add(path)

    package_readme = f'''# Toshiba storage recovery records — 15 September 2026

This package contains metadata, path mappings, code and verification evidence. The price and macroeconomic payloads remain on the Toshiba drive.

- [Deletion and reference-migration report](utils/external_storage/{NAME}/README.md)
- [Current data census](research/utility/toshiba_data_manifest_20260913_v1/README.md)
- [Current path authority](data_paths.json)
- [Earlier Hetzner upload/recovery utility](utils/external_storage/hetzner/README.md)

`BUNDLE_CONTENTS.json` gives the SHA-256 and size of each packaged file. The publication receipt alongside the original TAR file supplies its complete archive checksum. Source ZIP archives keep their original paths as member names below `Users/`; inspect and selectively restore them to a separate directory before applying source changes.

Run an offline manifest query from this extracted directory:

```bash
python3 research/utility/toshiba_data_manifest_20260913_v1/query.py --prefix raw_price_data/ --summary
```

For historical filesystem references, `utils/external_storage/relocated_references.py resolve OLD_PATH --require-exists` uses this package's registry and verifies the mounted Toshiba. The original data files and historical receipts are not embedded here except for explicitly retained metadata snapshots. No Hetzner account credentials are included or required for offline manifest queries.
'''
    contents = []
    temporary = bundle.with_name(bundle.name + '.partial')
    with tarfile.open(temporary, 'x:gz', compresslevel=6, format=tarfile.PAX_FORMAT) as archive:
        def add(relative, raw, *, mtime=0, mode=0o644):
            member = str(PurePosixPath(NAME) / relative)
            assert not PurePosixPath(member).is_absolute() and '..' not in PurePosixPath(member).parts
            item = tarfile.TarInfo(member)
            item.size, item.mtime, item.mode = len(raw), mtime, mode
            archive.addfile(item, io.BytesIO(raw))
            contents.append({'member': member, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        add('README.md', package_readme.encode())
        for index, path in enumerate(sorted(sources)):
            if path.is_symlink():
                raise ValueError('Unexpected source symlink: ' + str(path))
            before = path.stat()
            raw = path.read_bytes()
            after = path.stat()
            assert (before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino), str(path)
            add(path.relative_to(ROOT).as_posix(), raw, mtime=int(after.st_mtime), mode=after.st_mode & 0o777)
            if index % 100 == 0:
                print(json.dumps({'packaged_sources': index + 1, 'total': len(sources)}), flush=True)
        inventory = json.dumps({'schema': 'marketmaker.storage_recovery_bundle.v1',
                                'files': contents, 'note': 'This inventory excludes itself; the whole-archive checksum binds it.'}, indent=2).encode() + b'\n'
        add('BUNDLE_CONTENTS.json', inventory)

    expected = {row['member']: row for row in contents}
    with tarfile.open(temporary, 'r:gz') as archive:
        found = set()
        for member in archive:
            assert member.isfile() and member.name in expected and member.name not in found
            body = archive.extractfile(member).read()
            assert member.size == expected[member.name]['bytes']
            assert hashlib.sha256(body).hexdigest() == expected[member.name]['sha256']
            found.add(member.name)
        assert found == set(expected)
    temporary.rename(bundle)
    bundle_sha = sha_file(bundle)
    print(json.dumps({'archive_verified': True, 'bytes': bundle.stat().st_size, 'sha256': bundle_sha,
                      'members': len(expected)}), flush=True)

    # Exercise the restored query and resolver from the package, not the workspace.
    needed = {'data_paths.json', 'utils/__init__.py', 'utils/data_paths.py', 'utils/external_storage/relocated_references.py',
              str(MANIFEST / 'query.py'), str(MANIFEST / 'storage_layout.py'), str(MANIFEST / 'LATEST.json'),
              str(MANIFEST / RUN / 'FILES.jsonl.gz'), str(MANIFEST / RUN / 'PATH_RELOCATIONS.json')}
    with tempfile.TemporaryDirectory(prefix='toshiba-records-restore-') as scratch:
        target = Path(scratch)
        with tarfile.open(bundle, 'r:gz') as archive:
            for relative in sorted(needed):
                member = archive.getmember(NAME + '/' + relative)
                out = target / NAME / relative
                out.parent.mkdir(parents=True, exist_ok=True)
                with out.open('xb') as stream:
                    shutil.copyfileobj(archive.extractfile(member), stream)
        restored = target / NAME
        child_environment = {key: value for key, value in os.environ.items() if key != 'PYTHONPATH'}
        query = subprocess.run([sys.executable, '-B', str(MANIFEST / 'query.py'),
                                '--prefix', 'macroeconomics/', '--summary'], cwd=restored,
                               env=child_environment, capture_output=True, text=True, check=True)
        result = json.loads(query.stdout)
        assert result['matches'] == 11265 and result['bytes'] == 13030821970
        resolve = subprocess.run([sys.executable, '-B', 'utils/external_storage/relocated_references.py',
                                  'resolve', str(mount / 'macroeconomics/economic_releases'), '--require-exists'],
                                 cwd=restored, env=child_environment, capture_output=True, text=True, check=True)
        assert resolve.stdout.strip() == str(mount / 'other_data/macroeconomics/economic_releases')
    restore_check = {'status': 'PASS', 'restored_offline_query': result,
                     'restored_registry_resolution': resolve.stdout.strip(),
                     'all_archive_members_read_back_and_hashed': True}
    print(json.dumps({'restore_check': restore_check}), flush=True)

    identity = ensure_external_storage(force=True)
    reserve = 32 * 1024**2
    required = bundle.stat().st_size + (ROOT / 'data_paths.json').stat().st_size + 8 * 1024**2
    free_before = shutil.disk_usage(mount).free
    if free_before < required + reserve:
        raise OSError('Insufficient Toshiba space for bundle plus 32 MiB reserve')
    destination.mkdir()
    drive_bundle = destination / BUNDLE_NAME
    partial = destination / (BUNDLE_NAME + '.partial')
    with bundle.open('rb') as source, partial.open('xb') as out:
        shutil.copyfileobj(source, out, 1024**2)
        out.flush()
        os.fsync(out.fileno())
    drive_sha = sha_file(partial)
    assert drive_sha == bundle_sha
    partial.rename(drive_bundle)
    print(json.dumps({'drive_bundle_read_back_verified': True, 'sha256': drive_sha}), flush=True)

    handoff = f'''# Toshiba current storage handoff — 15 September 2026

The old external `marketmaker` and `marketmaker_v2` folders are removed. Price data is under `/Volumes/Toshiba 2TB/raw_price_data/`; economic and other retained data is under `/Volumes/Toshiba 2TB/other_data/`. Both local Developer repositories remain intact.

All 960,167 original project files were retained with unchanged size, modification time and nonempty-file inode identity. The current census contains 960,182 files; this handoff was published afterward. Historical evidence bytes were preserved and 8,706,198 current-location references were independently checked.

- [Recovery records bundle]({BUNDLE_NAME}) — metadata, manifests, reference indexes, path helpers, current code and original code backups.
- [Current path registry](data_paths.json).
- [Publication and full archive read-back checksum](PUBLICATION.json).

Archive SHA-256: `{bundle_sha}`. Extract the archive into a new folder on a disk with sufficient space, then open its `README.md`. The extracted manifest query works without the Toshiba mounted. The package was restored to a temporary directory and its query and volume resolver were exercised successfully before publication.

The bundle contains metadata and code; the original market and macroeconomic payloads remain in the organized directories. The full census is live and non-atomic, excludes protected macOS folder interiors and does not certify all payload checksums or disk-image interiors. The preceding `../toshiba_organization_20260915/` records remain unchanged. This handoff does not provision or upload to Hetzner.
'''
    layout = f'''# Toshiba data locations — 15 September 2026

| Data | Location |
| --- | --- |
| Price sources and retained price views | [raw_price_data](raw_price_data/) |
| Economic releases, non-price providers and all other retained data | [other_data](other_data/) |
| Main IQFeed archive | [iqfeed_archive](raw_price_data/iqfeed_archive/) |
| Macroeconomic releases | [economic_releases](other_data/macroeconomics/economic_releases/) |
| FRED/EIA/SEC and other provider archives | [non_price_provider_archive](other_data/non_price_provider_archive/) |
| Former external marketmaker_v2 contents | [retained_marketmaker_v2](other_data/retained_marketmaker_v2/) |
| Current manifest, path mappings and recovery records | [storage handoff](other_data/migration/{NAME}/README.md) |

The old external `marketmaker` and `marketmaker_v2` directories were removed after relocation. The verification retained all 960,167 original project files with unchanged size/mtime/nonempty inode; it was not a full payload hash pass. Historical references remain in sealed records and have mapped current-location counterparts. Local repositories were preserved.
'''
    new_files = [(destination / 'README.md', handoff.encode()),
                 (destination / 'data_paths.json', (ROOT / 'data_paths.json').read_bytes()),
                 (mount / 'DATA_LAYOUT.md', layout.encode())]
    additions = [{'path': str(drive_bundle.relative_to(mount)), 'bytes': drive_bundle.stat().st_size, 'sha256': drive_sha}]
    for path, raw in new_files:
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        assert sha_file(path) == hashlib.sha256(raw).hexdigest()
        additions.append({'path': str(path.relative_to(mount)), 'bytes': len(raw), 'sha256': sha_file(path)})
    assert all(not (mount / name).exists() for name in ('marketmaker', 'marketmaker_v2'))
    assert all((Path('/Users/tprice/Developer') / name).is_dir() for name in ('marketmaker', 'marketmaker_v2'))
    assert sha_file(ROOT / 'data_paths.json') == registry_sha
    assert sha_file(Path('/Users/tprice/Developer/marketmaker/data_paths.json')) == registry_sha
    receipt = {'schema': 'marketmaker.storage_reference_publication.v1', 'status': 'PASS',
               'published_at_utc': now(), 'volume_uuid': config['external_storage']['volume_uuid'],
               'bundle_path': str(drive_bundle), 'bundle_sha256': drive_sha, 'bundle_bytes': drive_bundle.stat().st_size,
               'bundle_member_count': len(expected), 'all_archive_members_verified': True,
               'restore_check': restore_check, 'registry_sha256': registry_sha,
               'manifest_run': RUN, 'manifest_sha256': json.loads((ROOT / MANIFEST / 'LATEST.json').read_text())['manifest_sha256'],
               'file_manifest_cutoff_utc': '2026-09-15T15:14:23.305138+00:00',
               'files_added_after_manifest': additions,
               'publication_receipt_additional_file': str((destination / 'PUBLICATION.json').relative_to(mount)),
               'free_bytes_before_publication': free_before,
               'free_bytes_before_receipt': shutil.disk_usage(mount).free,
               'old_external_roots_absent': True, 'both_local_repositories_preserved': True,
               'note': 'The census is not rewritten to include this later publication. This receipt is outside its own archive to avoid a circular archive hash. This is a metadata/code handoff, not a second copy of data payloads or a Hetzner deployment.'}
    raw = (json.dumps(receipt, indent=2) + '\n').encode()
    for path in (HERE / 'PUBLICATION.json', destination / 'PUBLICATION.json'):
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        assert sha_file(path) == hashlib.sha256(raw).hexdigest()
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
