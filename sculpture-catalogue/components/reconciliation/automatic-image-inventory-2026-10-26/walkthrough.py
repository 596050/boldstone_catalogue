"""Terminal navigation for one native image or option at a time."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parent
B = ROOT.parents[2]
read = lambda p: json.loads(Path(p).read_text())
arg = argparse.ArgumentParser()
arg.add_argument('--state-dir', type=Path, default=ROOT / 'post-folder-followup')
choice = arg.add_mutually_exclusive_group()
choice.add_argument('--new', type=int)
choice.add_argument('--absence', type=int)
choice.add_argument('--option', type=int)
choice.add_argument('--id')
a = arg.parse_args()
H = a.state_dir.resolve()
new = read(H / 'new-images.json')
native = read(H / 'current-native-overlay.json')
if a.new:
    assert 1 <= a.new <= len(new)
    row = new[a.new - 1]
    print('NEW IMAGE ' + str(a.new) + '/' + str(len(new)) + ': ' + Path(row['path']).parent.name)
    print('Image: ' + row['image_url'] + '\nContaining folder: ' + row['folder_url'])
    print('Stable file ID: ' + row['file_id'] + '\nFolder ID: ' + row['folder_id'])
    print('Image pixels: ' + ' x '.join(str(v) for v in row['dimensions']) + '\nBytes: ' + str(row['bytes']))
    print('Containing folder and original uploaded bytes verified; listing use, image origin and physical specifications remain separate.')
elif a.absence:
    rows = read(H / 'native-absence-register.json')['rows']
    assert 1 <= a.absence <= len(rows)
    row = rows[a.absence - 1]
    print('ABSENCE ' + str(a.absence) + '/' + str(len(rows)) + ': ' + row['name'])
    print('Stable file ID: ' + row['file_id'] + '\nState: ' + row['state'])
    print('Native NOT_FOUND observed; no deletion performed by this reconciliation.')
else:
    p = read(B / 'current-master.json')
    g = read(B / p['register'])
    options = [o for o in g['options'] if o['product_id'] in g['active_option_ids']]
    if a.id:
        row = next(o for o in options if o['product_id'] == a.id)
        number = options.index(row) + 1
    else:
        number = a.option or 1
        assert 1 <= number <= 188
        row = options[number - 1]
    source = row if row.get('file_id') else row.get('owner_confirmed_design_reference', {})
    file_id = source['file_id']
    print('OPTION ' + str(number) + '/188: ' + row['name'] + ' / ' + row['product_id'])
    if file_id in native['current_objects']:
        f = native['current_objects'][file_id]
        print('Retained source image: ' + f['image_url'] + '\nActual containing folder: ' + f['folder_url'])
    else:
        print('Historical source image currently absent. Stable ID: ' + file_id)
        print('Recorded containing folder: ' + source['folder_url'])
    values = read(B.parent / 'catalogue-review/reviews/specification-completion-20261025/all-188-readback.json')
    value = next(o for o in values if o['product_id'] == row['product_id'])
    for field, text in value['values'].items():
        print(field + ': ' + text)
    print('Saved working values; no new physical measurement is implied.')
    print('Review in app: http://127.0.0.1:8767/#' + row['product_id'])
print('Native navigation is a fixed generation ' + str(native['source_snapshot']['generation']) + ' snapshot. The app refreshes independently. Existing owner photograph holds remain unchanged.')
