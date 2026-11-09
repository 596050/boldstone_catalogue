#!/usr/bin/env python3
"""Verify organized inputs and compatibility links without changing any data."""
import csv
import hashlib
import os
from pathlib import Path


def file_stamp(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def check(root):
    root = Path(root).resolve()
    fields = ['legacy_path', 'path', 'bytes', 'sha256']
    try:
        with (root / 'data/file-manifest.csv').open(newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != fields:
                return 0, ['The data manifest header is missing or invalid.']
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        return 0, [f'The data manifest could not be read: {exc}']
    if not rows:
        return 0, ['The data manifest is empty.']
    if any(set(row) != set(fields) or any(not isinstance(row[key], str) or not row[key] for key in fields)
           for row in rows):
        return len(rows), ['The data manifest contains incomplete or malformed rows.']
    errors = []
    if len({row['path'] for row in rows}) != len(rows) or len({row['legacy_path'] for row in rows}) != len(rows):
        errors.append('The manifest contains duplicate paths.')
    categories = [root / 'data' / name for name in ('inputs', 'exports')]
    actual = set()
    for folder in categories:
        for path in [folder, *folder.rglob('*')]:
            if path.is_symlink():
                # Canonical data contains physical files; compatibility links
                # live at the old paths. rglob does not traverse directory
                # links and is_file hides dangling links, so reject both.
                errors.append(f'Canonical data contains an unexpected symbolic link: {path.relative_to(root)}')
            if path.suffix.lower() in ('.csv', '.xlsx') and (path.is_file() or path.is_symlink()):
                actual.add(str(path.relative_to(root)))
    if actual != {row['path'] for row in rows}:
        errors.append('The manifest does not match the organized data file set.')
    for row in rows:
        target = root / row['path']
        legacy = root / row['legacy_path']
        try:
            for key in ('path', 'legacy_path'):
                path = Path(row[key])
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Manifest paths must be relative to the workspace without parent traversal')
            if target.is_symlink() or not any(target.resolve().is_relative_to(folder) for folder in categories):
                raise ValueError('Target must be a regular file in data/inputs or data/exports')
            if not legacy.parent.resolve().is_relative_to(root):
                raise ValueError('Legacy path is outside the workspace')
            if (not legacy.is_symlink() or legacy.readlink().is_absolute()
                    or legacy.resolve(strict=True) != target.resolve(strict=True)):
                raise ValueError('Legacy link no longer resolves to the organized input')
            before = target.stat()
            digest = hashlib.sha256()
            with target.open('rb') as source:
                if file_stamp(os.fstat(source.fileno())) != file_stamp(before):
                    raise ValueError('Data file changed before it could be inspected')
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(block)
                after_read = os.fstat(source.fileno())
            after = target.stat()
            if file_stamp(before) != file_stamp(after_read) or file_stamp(before) != file_stamp(after):
                raise ValueError('Data file changed during verification')
            if (not legacy.is_symlink() or legacy.readlink().is_absolute()
                    or legacy.resolve(strict=True) != target.resolve(strict=True)):
                raise ValueError('Legacy link changed during verification')
            if after.st_size != int(row['bytes']) or digest.hexdigest() != row['sha256']:
                raise ValueError('Data bytes changed since organization')
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"{row['path']}: {exc}")
    return len(rows), errors


if __name__ == '__main__':
    count, errors = check(Path(__file__).resolve().parents[1])
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'PASS: {count} organized data files match their original checksums and legacy paths.')
