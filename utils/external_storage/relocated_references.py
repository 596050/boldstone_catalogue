#!/usr/bin/env python3
"""Current-location views of retained Toshiba metadata, without editing evidence.

``resolve`` translates a complete old path. ``view`` creates a derived JSON
document with current paths and an explicit original-content binding. ``audit``
indexes every reference in supplied text/metadata files, recording original
hashes and JSON pointers (or text offsets). No source file is written.
"""
from __future__ import annotations

import argparse
import codecs
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# A relative storage path must begin at a token boundary. In particular, never
# rewrite /Users/.../marketmaker or /Users/.../marketmaker_v2 repository paths.
PATTERN = re.compile(
    r'/Volumes/Toshiba 2TB/(?:marketmaker_v2|marketmaker|macroeconomics)(?:/[^\s\"\x27`<>\[\]{}(),;\\]*)?'
    r'|(?<![\w/])(?:marketmaker/(?:data|iqfeed_archive|macro_archive|research|research_runtime_offload)|marketmaker_v2|macroeconomics)'
    r'/[^\s\"\x27`<>\[\]{}(),;\\]*'
)
OLD_ROOTS = ('marketmaker', 'marketmaker_v2', 'macroeconomics')
TOKENS = ('/Volumes/Toshiba 2TB/', 'marketmaker/', 'marketmaker_v2/', 'macroeconomics/')


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Locations:
    def __init__(self, config):
        self.mount = config['external_storage']['mount_point'].rstrip('/')
        self.mapping = {**config.get('container_relocations', {}), **config.get('path_relocations', {})}

    def exact(self, value):
        absolute = value.startswith(self.mount + '/')
        relative = value[len(self.mount) + 1:] if absolute else value
        p = PurePosixPath(relative)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] not in OLD_ROOTS:
            return value, None
        for parent in (p, *p.parents):
            destination = self.mapping.get(str(parent))
            if destination is not None:
                q = PurePosixPath(destination) / p.relative_to(parent)
                return (self.mount + '/' if absolute else '') + str(q), str(parent)
        return value, None

    def text(self, value):
        references = []
        # JSON path fields may contain spaces in filenames; resolve the full
        # value first. Prose and shell commands are indexed token by token.
        if value.startswith((self.mount + '/', 'marketmaker/', 'marketmaker_v2/', 'macroeconomics/')) and '\n' not in value:
            current, prefix = self.exact(value)
            if prefix:
                return current, [{'original': value, 'current': current, 'mapping_prefix': prefix}]
        def replace(match):
            original = match.group()
            current, prefix = self.exact(original)
            if prefix and current != original:
                references.append({'original': original, 'current': current,
                                   'mapping_prefix': prefix, 'text_offset': match.start()})
            return current
        return PATTERN.sub(replace, value), references

    def document(self, value, pointer=''):
        if isinstance(value, str):
            updated, refs = self.text(value)
            return updated, [{**r, 'pointer': pointer} for r in refs]
        if isinstance(value, list):
            out, refs = [], []
            for i, child in enumerate(value):
                new, found = self.document(child, pointer + '/' + str(i)); out.append(new); refs.extend(found)
            return out, refs
        if isinstance(value, dict):
            out, refs = {}, []
            for key, child in value.items():
                escaped = key.replace('~', '~0').replace('/', '~1')
                new_key, found_keys = self.text(key)
                if new_key in out:
                    raise ValueError('Relocation would collide dictionary keys: ' + pointer)
                new, found = self.document(child, pointer + '/' + escaped)
                refs.extend({**r, 'pointer': pointer + '/' + escaped, 'dictionary_key': True} for r in found_keys)
                out[new_key] = new; refs.extend(found)
            return out, refs
        return value, []


def read_document(path, locations, *, materialize=True):
    before = path.stat()
    if before.st_size > 16 * 1024**2 and path.suffix != '.gz' and not materialize:
        # Large ledgers can contain payload arrays or millions of events. Index
        # embedded path tokens in a bounded stream instead of constructing a
        # second giant JSON object merely to find its filesystem references.
        digest = hashlib.sha256(); references = []; buffer = ''; offset = 0
        decoder = codecs.getincrementaldecoder('utf-8-sig')()
        with path.open('rb') as stream:
            while True:
                chunk = stream.read(1024**2)
                digest.update(chunk)
                buffer += decoder.decode(chunk, final=not chunk)
                stop = len(buffer) if not chunk else max(0, len(buffer) - 8192)
                for match in PATTERN.finditer(buffer):
                    if match.start() >= stop:
                        break
                    if match.end() > stop and chunk:
                        stop = match.start(); break
                    original = match.group(); current, prefix = locations.exact(original)
                    if prefix and current != original:
                        references.append({'original': original, 'current': current,
                            'mapping_prefix': prefix, 'text_offset': offset + match.start(),
                            'method': 'streamed_text_token'})
                buffer = buffer[stop:]; offset += stop
                if not chunk:
                    break
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('Metadata changed during read')
        return {'path': str(path), 'bytes': before.st_size, 'sha256': digest.hexdigest(),
                'mtime_ns': before.st_mtime_ns, 'method': 'bounded_text_stream'}, None, references
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError('Metadata changed during read')
    body = gzip.decompress(raw) if path.suffix == '.gz' else raw
    if b'\0' in body:
        raise ValueError('Binary payload is not a text reference document')
    text = body.decode('utf-8-sig')
    if not materialize and not any(token in text for token in TOKENS):
        return {'path': str(path), 'bytes': len(raw), 'sha256': sha(raw),
                'mtime_ns': before.st_mtime_ns, 'method': 'no_storage_reference_tokens'}, None, []
    logical_suffix = Path(path.stem).suffix if path.suffix == '.gz' else path.suffix
    parse_warning = None
    try:
        if logical_suffix == '.json':
            original = json.loads(text)
            updated, references = locations.document(original)
        elif logical_suffix == '.jsonl':
            updated, references = [], []
            for i, line in enumerate(text.splitlines()):
                if not line.strip():
                    continue
                new, refs = locations.document(json.loads(line), '/line/' + str(i + 1))
                updated.append(new); references.extend(refs)
        else:
            updated, references = locations.text(text)
    except json.JSONDecodeError as error:
        # A partial historical record still has useful source locations. Keep
        # its bytes and label the text fallback; never silently repair its JSON.
        parse_warning = 'Malformed historical JSON retained and indexed as text: ' + str(error)
        updated, references = locations.text(text)
    return {'path': str(path), 'bytes': len(raw), 'sha256': sha(raw),
            'mtime_ns': before.st_mtime_ns, **({'parse_warning': parse_warning} if parse_warning else {})}, updated, references


def index_compressed_jsonl(path, locations, output):
    """Index million-row historical censuses with bounded memory and staging."""
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
    identity = {'path': str(path), 'bytes': before.st_size, 'sha256': digest.hexdigest(),
                'mtime_ns': before.st_mtime_ns, 'method': 'streamed_compressed_jsonl'}
    count = chunks = warnings = 0; pending = []
    with tempfile.TemporaryFile() as temporary:
        with gzip.GzipFile(fileobj=temporary, mode='wb', mtime=0) as staged:
            def emit():
                nonlocal chunks
                if not pending:
                    return
                staged.write((json.dumps({'document': identity, 'references': pending,
                    'original_bytes_preserved': True, 'reference_chunk': chunks,
                    'chunked_document': True}, separators=(',', ':')) + '\n').encode())
                pending.clear(); chunks += 1
            with gzip.open(path, 'rt', encoding='utf-8-sig') as source:
                for line_number, line in enumerate(source, 1):
                    if not line.strip() or not any(token in line for token in TOKENS):
                        continue
                    try:
                        _, refs = locations.document(json.loads(line), '/line/' + str(line_number))
                    except json.JSONDecodeError:
                        _, refs = locations.text(line); warnings += 1
                        refs = [{**r, 'line': line_number, 'parse_warning': 'Malformed historical JSONL line retained'} for r in refs]
                    count += len(refs); pending.extend(refs)
                    if len(pending) >= 1000:
                        emit()
            emit()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('Compressed metadata changed during read')
        temporary.seek(0)
        with gzip.open(temporary, 'rt') as staged:
            for line in staged:
                output.write(line)
    if warnings:
        identity['malformed_jsonl_lines_retained'] = warnings
    return identity, count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    resolve = sub.add_parser('resolve'); resolve.add_argument('path'); resolve.add_argument('--require-exists', action='store_true')
    view = sub.add_parser('view'); view.add_argument('path', type=Path); view.add_argument('--output', type=Path, required=True)
    audit = sub.add_parser('audit'); audit.add_argument('--paths-file', type=Path, action='append', required=True)
    audit.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from utils.data_paths import load_data_paths, resolve_storage_reference
    if args.command == 'resolve':
        print(resolve_storage_reference(args.path, require_exists=args.require_exists)); return
    config = load_data_paths()
    locations = Locations(config)
    if args.command == 'view':
        source = resolve_storage_reference(args.path, require_exists=True)
        original, current, refs = read_document(source, locations)
        result = {'schema': 'marketmaker.relocated_metadata_view.v1', 'original': original,
                  'qualification': 'Derived location view. Original hashes, clocks and evidence identities refer to the retained original bytes.',
                  'references': refs, 'current_document': current}
        with args.output.open('x') as f: json.dump(result, f, indent=2); f.write('\n')
        return
    args.output.mkdir(parents=True, exist_ok=False)
    config_bytes = json.dumps(config, sort_keys=True).encode()
    (args.output / 'PATH_RELOCATIONS.json').write_text(json.dumps({
        'mount': locations.mount, 'path_relocations': locations.mapping,
        'registry_sha256': sha((ROOT / 'data_paths.json').read_bytes())}, indent=2) + '\n')
    paths = sorted({line for source in args.paths_file for line in source.read_text().splitlines() if line})
    counts = Counter(); start = datetime.now(timezone.utc).isoformat()
    with gzip.open(args.output / 'CURRENT_REFERENCES.jsonl.gz', 'wt', compresslevel=6) as out, \
         gzip.open(args.output / 'DOCUMENTS.jsonl.gz', 'wt', compresslevel=6) as documents, \
         (args.output / 'ERRORS.jsonl').open('x') as errors:
        for i, name in enumerate(paths):
            path = Path(name)
            try:
                if path.name.endswith('.jsonl.gz'):
                    original, reference_count = index_compressed_jsonl(path, locations, out)
                    refs = None
                else:
                    original, _, refs = read_document(path, locations, materialize=False)
                    reference_count = len(refs)
                counts['documents_read'] += 1; counts['bytes_read'] += original['bytes']
                counts['documents_with_references'] += bool(reference_count); counts['references'] += reference_count
                documents.write(json.dumps({**original, 'references': reference_count}, separators=(',', ':')) + '\n')
                if refs:
                    out.write(json.dumps({'document': original, 'references': refs,
                        'original_bytes_preserved': True}, separators=(',', ':')) + '\n')
            except (OSError, ValueError, UnicodeError, EOFError) as error:
                counts['errors'] += 1
                errors.write(json.dumps({'path': str(path), 'error': type(error).__name__ + ': ' + str(error)}) + '\n')
            if i % 200 == 0:
                out.flush(); documents.flush(); errors.flush()
                print(json.dumps({'processed': i + 1, 'total': len(paths), **counts}), flush=True)
    result = {'schema': 'marketmaker.storage_reference_audit.v1', 'started_at_utc': start,
              'finished_at_utc': datetime.now(timezone.utc).isoformat(), 'candidates': len(paths), **counts,
              'status': 'COMPLETE' if not counts['errors'] else 'REQUIRES_RECONCILIATION',
              'source_mutations': 0, 'config_content_sha256': sha(config_bytes),
              'scope': 'Supplied source, configuration and metadata file list. Source payload bodies and opaque archive/image interiors are not rewritten.'}
    (args.output / 'SUMMARY.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
