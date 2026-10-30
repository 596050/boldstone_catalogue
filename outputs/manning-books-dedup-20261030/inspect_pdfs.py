import concurrent.futures, json, os, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

manifest = Path(sys.argv[1])
destination = Path(sys.argv[2])
rows = json.loads(manifest.read_text())
results = json.loads(destination.read_text()) if destination.exists() else []
done = {r['id'] for r in results if r.get('success')}
rows = [r for r in rows if r['id'] not in done]
results = [r for r in results if r.get('success')]

def inspect(row):
    result = {k:v for k,v in row.items() if k != 'download_url'}
    local_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix='manning-dedup-', suffix='.pdf', delete=False) as tmp:
            local_path = tmp.name
            with urllib.request.urlopen(row['download_url'], timeout=90) as response:
                while chunk := response.read(1024*1024):
                    tmp.write(chunk)
        result['downloaded_size'] = os.path.getsize(local_path)
        if result['downloaded_size'] != row['size']:
            raise ValueError('Downloaded size differs from Dropbox metadata')
        info = subprocess.run(['pdfinfo', local_path], capture_output=True, text=True, timeout=45)
        result['pdfinfo'] = info.stdout
        result['pdfinfo_error'] = info.stderr[:2000]
        text = subprocess.run(['pdftotext', '-f', '1', '-l', '8', '-layout', local_path, '-'], capture_output=True, text=True, timeout=45)
        result['opening_text'] = text.stdout
        result['text_error'] = text.stderr[:2000]
        result['success'] = info.returncode == 0 and text.returncode == 0 and bool(text.stdout.strip())
    except Exception as exc:
        result['success'] = False
        result['error'] = str(exc)
    finally:
        if local_path:
            Path(local_path).unlink(missing_ok=True)
    return result

with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    futures = [pool.submit(inspect, row) for row in rows]
    for future in concurrent.futures.as_completed(futures):
        result = future.result()
        results.append(result)
        destination.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        if len(results) % 20 == 0:
            print(json.dumps({'inspected':len(results), 'total':len(rows), 'failures':sum(not r['success'] for r in results)}), flush=True)
print(json.dumps({'inspected':len(results), 'failures':sum(not r['success'] for r in results)}), flush=True)
manifest.unlink(missing_ok=True)
