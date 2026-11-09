"""Freeze exact finished source files; no broker or storage network operations."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CENTRAL = Path('/Volumes/Toshiba 2TB/other_data/research/artifacts')


def identity(path):
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise RuntimeError('Expected real regular path: ' + str(path))
    before = path.stat()
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise RuntimeError('Source changed during freeze')
    return dict(path=str(path), bytes=after.st_size, sha256=digest)


def main():
    for name in ['PUBLIC_READBACK.json', 'PROBE_ROOT_READBACK.json', 'BROKER_CASH_EXTENSION.json',
                 'CASH_ROOT_READBACK.json', 'ARCHIVE_CODE_REVIEW.json', 'ARCHIVE_PRIOR_EVIDENCE.json']:
        if not (HERE / name).is_file():
            raise RuntimeError('Required terminal receipt missing: ' + name)
    selected = set()
    roots = [CENTRAL / HERE.name,
             CENTRAL / 'retained_demo_history_readback_20261005_v1/run_01',
             ROOT / 'research/utility/retained_demo_history_readback_20261005_v1',
             ROOT / 'research/utility/native_oxy_primary_clock_rights_20261005_v1',
             ROOT / 'research/utility/native_pair_common_execution_20261004_v1/crc_source_readback_01']
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            raise RuntimeError('Missing or symlinked selected root')
        selected.update(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    location = json.loads((ROOT / 'research/utility/native_pair_common_execution_20261004_v1/crc_source_readback_01/CURRENT_LOCATION.json').read_text())
    for item in location['source_locations'].values():
        expected = item['resolved_reference']
        path = Path(expected['path'])
        if identity(path) != expected:
            raise RuntimeError('Relocated CRC reference mismatch')
        selected.add(path)
    selected.add(ROOT / 'research/utility/crc_predecessor_source_identity_20260913_v1/SOURCE_INQUIRY.md')
    for path in HERE.iterdir():
        if path.is_file() and path.suffix in {'.py', '.json', '.md'}:
            if path.name in {'MANIFEST.json','QUEUE_START.json','QUEUE_DEFERRED.json','ARCHIVE_FAILURE.json','UPLOAD.json','REMOTE_READBACK.json'}:
                raise RuntimeError('Existing lifecycle receipt; do not refreeze')
            selected.add(path)
    files = [identity(p) for p in sorted(selected)]
    if len(files) > 500 or sum(r['bytes'] for r in files) > 32 * 1024 * 1024:
        raise RuntimeError('Bounded packet limit exceeded')
    command_bytes = sum(len(r['path'].encode()) + 1 for r in files)
    if command_bytes > 150000:
        raise RuntimeError('Command argument budget exceeded')
    profile = json.loads((Path.home() / '.config/marketmaker-storagebox/market-data/profile.json').read_text())
    manifest = dict(at_utc=datetime.now(timezone.utc).isoformat(),
                    group='native-evidence-retrieval-20261005-v1', repository_id=profile['repository_id'],
                    roots=list(map(str, roots)), files=files, exact_file_selection=True,
                    logical_bytes=sum(r['bytes'] for r in files), file_count=len(files),
                    source_deletion=False, historical_comparison_complete=False)
    with (HERE / 'MANIFEST.json').open('x') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({k:manifest[k] for k in ['group','file_count','logical_bytes','historical_comparison_complete']}))


if __name__ == '__main__':
    main()
