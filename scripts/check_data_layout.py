#!/usr/bin/env python3
"""Verify organized inputs and compatibility links without changing any data."""
import csv
import hashlib
from pathlib import Path


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
    actual = {str(p.relative_to(root)) for folder in categories for p in folder.rglob('*')
              if p.is_file() and p.suffix.lower() in ('.csv', '.xlsx')}
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
            digest = hashlib.sha256()
            with target.open('rb') as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(block)
            if target.stat().st_size != int(row['bytes']) or digest.hexdigest() != row['sha256']:
                raise ValueError('Data bytes changed since organization')
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"{row['path']}: {exc}")
    return len(rows), errors


if __name__ == '__main__':
    count, errors = check(Path(__file__).resolve().parents[1])
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'PASS: {count} organized data files match their original checksums and legacy paths.')
