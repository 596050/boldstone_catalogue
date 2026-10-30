from pathlib import Path
import hashlib, importlib.util, json

H = Path(__file__).resolve().parent
BASE = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest = read(H / 'input-manifest.json')
CUT = Path(manifest['input_directory'])
spec = importlib.util.spec_from_file_location('native_reader', BASE / 'components/reconciliation/acanthus-native-availability-2026-10-25/verify_workbook.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
Book = native.Book
g = read(H / 'canonical-master-register.json')
options = {o['product_id']: o for o in g['options']}
active = set(g['active_option_ids'])
overlay = read(H / 'current-image-overlay.json')
files = {r['file_id']: r for r in overlay}
OUT = BASE / 'outputs/01a144ab-1a7c-7223-a403-73a4d53d70ff/post-owner-deletions-master-2026-10-27'
OUT.mkdir(parents=True, exist_ok=True)

def write(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
