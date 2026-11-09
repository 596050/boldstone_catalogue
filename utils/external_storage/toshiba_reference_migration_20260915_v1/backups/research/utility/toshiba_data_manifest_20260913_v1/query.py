"""Search the retained manifest without requiring Toshiba to be connected."""
import argparse
import gzip
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prefix', default='', help='Volume-relative file or directory prefix')
    ap.add_argument('--contains', default='', help='Case-insensitive path substring')
    ap.add_argument('--limit', type=int, default=20, help='Displayed records; 0 displays all')
    ap.add_argument('--summary', action='store_true', help='Count all matches instead of displaying files')
    ap.add_argument('--directories', action='store_true', help='Search directory summaries')
    latest = Path(__file__).resolve().parent / 'LATEST.json'
    default_run = json.loads(latest.read_text())['run_id'] if latest.is_file() else 'run_03'
    ap.add_argument('--run-id', default=default_run)
    args = ap.parse_args()
    path = Path(__file__).resolve().parent / args.run_id / (
        'DIRECTORY_SUMMARY.jsonl.gz' if args.directories else 'FILES.jsonl.gz')
    matches = file_bytes = 0
    with gzip.open(path, 'rt') as source:
        for line in source:
            row = json.loads(line)
            if not row['path'].startswith(args.prefix) or args.contains.lower() not in row['path'].lower():
                continue
            matches += 1
            file_bytes += row['bytes']
            if not args.summary:
                print(json.dumps(row, ensure_ascii=False))
                if args.limit and matches >= args.limit:
                    return
    if args.summary:
        print(json.dumps({'matches': matches, 'bytes': file_bytes,
                         'note': 'Directory rows overlap; do not add parent and child sizes.' if args.directories else 'Logical file bytes.'}))


if __name__ == '__main__':
    main()
