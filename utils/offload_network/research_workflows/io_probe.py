"""Bounded, model-neutral JSON stream I/O probe for an isolated job runtime.

Uses the same json.dump/flush/fsync operations as the testing report writer.
It does not measure atomic publication, directory durability, model execution,
or storage capacity checks. Synthetic trial files are retained, never deleted.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import statistics
import sys
import time


def buffer_size(value):
    if value == 'default':
        return -1
    if type(value) is not int or not 8192 <= value <= 8 << 20:
        raise ValueError('buffer must be default or an integer from 8192 to 8388608')
    return value


def run(directory, *, rows, rounds, buffers, max_bytes):
    """Alternate buffer order; measure real raw writes and verify exact bytes."""
    if type(rows) is not int or not 1 <= rows <= 8192:
        raise ValueError('rows must be an integer from 1 to 8192')
    if type(rounds) is not int or not 1 <= rounds <= 8:
        raise ValueError('rounds must be an integer from 1 to 8')
    if (not isinstance(buffers, list) or not 2 <= len(buffers) <= 4
            or len(set(buffers)) != len(buffers)):
        raise ValueError('two to four distinct buffer choices required')
    sizes = {str(b): buffer_size(b) for b in buffers}
    if type(max_bytes) is not int or not 1 <= max_bytes <= 64 << 20:
        raise ValueError('an explicit byte budget up to 64 MiB is required')
    payload = {'schema': 'synthetic-json-stream-probe-v1', 'rows': [
        {'index': i, 'label': 'Unicode: \u6d4b\u91cf', 'missing': None,
         'value': ((i % 17) - 8) / 16, 'samples': list(range(16))}
        for i in range(rows)]}
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + '\n'
    # The payload is ASCII after ensure_ascii's default escaping. Account for
    # platform newline translation without silently forcing different bytes.
    expected = text.replace('\n', os.linesep).encode('ascii')
    required = len(expected) * rounds * len(buffers)
    if required > max_bytes:
        raise ValueError('synthetic trial files exceed the explicit byte budget')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    identity = hashlib.sha256(expected).hexdigest()
    trials = []
    for round_index in range(rounds):
        order = buffers if round_index % 2 == 0 else buffers[::-1]
        for choice in order:
            name = f'trial_{len(trials):02d}.json'
            path = directory / name
            raw_writes, raw_seconds = [], 0.
            started = time.perf_counter()
            with path.open('x', buffering=sizes[str(choice)]) as stream:
                raw = stream.buffer.raw
                write = raw.write

                def measured(data):
                    nonlocal raw_seconds
                    begin = time.perf_counter()
                    count = write(data)
                    raw_seconds += time.perf_counter() - begin
                    raw_writes.append({'requested': len(data), 'written': count})
                    return count

                raw.write = measured
                encoding = stream.encoding
                block_size = getattr(raw, '_blksize', None)
                dump_start = time.perf_counter()
                json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.write('\n')
                dump_end = time.perf_counter()
                stream.flush()
                os.fsync(stream.fileno())
                flush_end = time.perf_counter()
            elapsed = time.perf_counter() - started
            if (not raw_writes or any(type(r['written']) is not int for r in raw_writes)
                    or sum(r['written'] for r in raw_writes) != len(expected)):
                raise ValueError('raw write instrumentation did not account for every byte')
            observed = path.read_bytes()
            if observed != expected or hashlib.sha256(observed).hexdigest() != identity:
                raise ValueError('buffer choice changed the serialized output bytes')
            trials.append({'round': round_index, 'buffer': choice, 'path': name,
                'bytes': len(observed), 'sha256': identity, 'encoding': encoding,
                'raw_block_size': block_size, 'raw_write_calls': len(raw_writes),
                'raw_writes': raw_writes, 'raw_write_seconds': raw_seconds,
                'dump_and_stream_write_seconds': dump_end - dump_start,
                'final_flush_and_file_fsync_seconds': flush_end - dump_end,
                'open_write_flush_fsync_close_seconds': elapsed})
    summaries = {}
    for choice in buffers:
        selected = [t for t in trials if t['buffer'] == choice]
        summaries[str(choice)] = {field: statistics.median(t[field] for t in selected)
            for field in ('raw_write_calls', 'raw_write_seconds',
                          'open_write_flush_fsync_close_seconds')}
    return {'schema': 'marketmaker.json_stream_io_probe.v1', 'status': 'BYTE_IDENTICAL',
        'python': sys.version, 'platform': sys.platform, 'io_default_buffer_size': io.DEFAULT_BUFFER_SIZE,
        'rows': rows, 'rounds': rounds, 'buffers': buffers, 'max_bytes': max_bytes,
        'trial_bytes': required, 'payload_sha256': identity, 'trials': trials,
        'medians': summaries, 'trial_directory': str(directory.resolve()),
        'trial_files_retained': True, 'performance_qualification': 'NOT_ESTABLISHED',
        'boundary': 'Synthetic stream serialization and file fsync only, under observed shared load. '
            'Not atomic publication, storage preflight, market replay or a general disk speedup. '
            'Raw-write instrumentation adds common overhead. No existing worker settings changed.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rows', type=int, required=True)
    parser.add_argument('--rounds', type=int, required=True)
    parser.add_argument('--buffer-bytes', nargs='+', required=True)
    parser.add_argument('--max-bytes', type=int, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError('preserve the existing probe report')
    choices = [b if b == 'default' else int(b) for b in args.buffer_bytes]
    report = run(args.directory, rows=args.rows, rounds=args.rounds,
                 buffers=choices, max_bytes=args.max_bytes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
