"""Surgical storage-expression migration for ordinary, non-frozen utilities.

Original source bytes are retained in a single ZIP before any replacement.
Algorithms, frozen models, candidates and historical result records are excluded.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def transform(data, name):
    source = data.decode()
    tree = ast.parse(source, name)
    offsets = [0]
    for line in data.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    aliases = {'CONFIGURED_DATA_ROOT': []}
    def split(node):
        if isinstance(node, ast.Name) and node.id in aliases:
            return list(aliases[node.id])
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left = split(node.left)
            if left is not None:
                return left + [node.right]
        return None
    # Follow only immutable-looking, module-level constant aliases. Local
    # variables and dynamically reassigned names are not inferred as roots.
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
            parts = split(node.value)
            if target.isupper() and parts is not None and all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in parts):
                aliases[target] = parts
    replacements = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp):
            continue
        parts = split(node)
        if not parts:
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.BinOp) and split(parent) is not None:
            continue
        if all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in parts):
            logical = Path(*(x.value for x in parts))
            if logical.is_absolute() or '..' in logical.parts:
                raise ValueError('Unsafe logical expression: ' + ast.unparse(node))
            value = repr(logical.as_posix())
        else:
            value = 'Path(' + ast.unparse(parts[0]) + ')'
            value += ''.join(' / (' + ast.unparse(x) + ')' for x in parts[1:])
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[node.end_lineno - 1] + node.end_col_offset
        replacements.append((start, end, ('resolve_data_path(' + value + ')').encode()))
    if not replacements:
        return data, 0
    imported = any(isinstance(n, ast.ImportFrom) and n.module == 'utils.data_paths'
                   and any(a.name == 'resolve_data_path' for a in n.names) for n in tree.body)
    if not imported:
        imports = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == 'utils.data_paths']
        if not imports:
            raise ValueError('No module-level central registry import: ' + name)
        at = offsets[imports[-1].end_lineno]
        replacements.append((at, at, b'from utils.data_paths import resolve_data_path\n'))
    output = data
    for start, end, value in sorted(replacements, reverse=True):
        output = output[:start] + value + output[end:]
    ast.parse(output.decode(), name)
    return output, len(replacements) - int(not imported)


def main():
    existing = HERE / 'OPERATIONAL_SOURCE_PLAN.json'
    backup = HERE / 'OPERATIONAL_SOURCE_BEFORE.zip'
    if existing.exists():
        plan = json.loads(existing.read_text())['files']
        applied = 0
        with zipfile.ZipFile(backup) as archive, (HERE / 'OPERATIONAL_SOURCE_EDITS.jsonl').open('a') as journal:
            for row in plan:
                path = Path(row['path']); current = path.read_bytes()
                if '/runtime/' in str(path):
                    assert sha(current) == row['before_sha256']
                    continue
                if sha(current) == row['after_sha256']:
                    continue
                if sha(current) != row['before_sha256']:
                    raise RuntimeError('Concurrent source change: ' + str(path))
                before = archive.read(str(path).lstrip('/'))
                assert sha(before) == row['before_sha256']
                after, _ = transform(before, str(path))
                assert sha(after) == row['after_sha256']
                temp = path.parent / ('.storage-migration-' + str(os.getpid()) + '-' + sha(str(path).encode())[:12])
                with temp.open('xb') as stream:
                    stream.write(after); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), row['original_mode'])
                assert path.read_bytes() == before
                os.replace(temp, path)
                assert sha(path.read_bytes()) == row['after_sha256']
                journal.write(json.dumps(row) + '\n'); journal.flush(); applied += 1
        print(json.dumps({'resumed_files_updated': applied, 'total_files': len(plan),
                          'storage_expressions': sum(x['storage_expressions'] for x in plan),
                          'backup_sha256': sha(backup.read_bytes())}, indent=2))
        return
    paths = {Path(p) for suffix in ('marketmaker', 'marketmaker_v2')
             for p in Path('/tmp/toshiba_configured_' + suffix + '.txt').read_text().splitlines() if p}
    prepared = []; skipped = []
    for path in sorted(paths):
        if path.name in {'data_paths.py', 'manifest.py', 'external_data_storage.py'}:
            continue
        if any(part in {'research', 'frozen_models_running', 'tests', 'validation', '.source-state', 'archive', 'legacy', 'runtime'} for part in path.parts):
            skipped.append(str(path)); continue
        before = path.read_bytes()
        after, count = transform(before, str(path))
        if after != before:
            prepared.append((path, before, after, count, stat.S_IMODE(path.stat().st_mode)))
    backup = HERE / 'OPERATIONAL_SOURCE_BEFORE.zip'
    with zipfile.ZipFile(backup, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path, before, _, _, _ in prepared:
            archive.writestr(str(path).lstrip('/'), before)
    # Read every backup member back before changing any original file.
    with zipfile.ZipFile(backup) as archive:
        for path, before, _, _, _ in prepared:
            assert archive.read(str(path).lstrip('/')) == before
    plan = [{'path': str(path), 'before_sha256': sha(before), 'after_sha256': sha(after),
             'storage_expressions': count, 'original_mode': mode}
            for path, before, after, count, mode in prepared]
    (HERE / 'OPERATIONAL_SOURCE_PLAN.json').write_text(json.dumps({'files': plan, 'excluded': skipped}, indent=2) + '\n')
    with (HERE / 'OPERATIONAL_SOURCE_EDITS.jsonl').open('x') as journal:
        for row, (path, before, after, _, mode) in zip(plan, prepared, strict=True):
            if path.read_bytes() != before:
                raise RuntimeError('Concurrent edit; stopped before changing: ' + str(path))
            temp = path.parent / ('.storage-migration-' + str(os.getpid()) + '-' + sha(str(path).encode())[:12])
            with temp.open('xb') as stream:
                stream.write(after); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), mode)
            os.replace(temp, path)
            assert sha(path.read_bytes()) == row['after_sha256']
            journal.write(json.dumps(row) + '\n'); journal.flush()
    print(json.dumps({'files_updated': len(plan), 'storage_expressions': sum(x['storage_expressions'] for x in plan),
                      'backup': str(backup), 'backup_sha256': sha(backup.read_bytes()), 'excluded': len(skipped)}, indent=2))


if __name__ == '__main__':
    main()
