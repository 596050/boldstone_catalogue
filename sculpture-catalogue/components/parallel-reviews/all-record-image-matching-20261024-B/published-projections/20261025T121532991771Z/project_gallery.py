"""Read back the saved master and prepare an isolated, append-only gallery."""
from datetime import datetime, timezone
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
from xml.etree import ElementTree as E
import hashlib, html, json, posixpath, shutil, sqlite3, zipfile

Q = Path(__file__).resolve().parent
B = Q.parents[2]
H = B / 'components/reconciliation/matched-listing-master-2026-10-25'
W = B / 'components/parallel-reviews/matched-listing-finalization-20261025-B'
source = B / 'components/parallel-reviews/all-record-image-matching-20261024-B/published-projections/20261025T014714043538Z'
rp, wp = H / 'canonical-master-register.json', H / 'master-workbook.pending'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
register_sha = '9b4b15ca857bea027637b3dd1474bfb98c87746bb842b49003b526da6770e748'
workbook_sha = '178d00ee841c1035a923904dcabc0b7a85264803ff5351bbb3c42c48a327528a'
assert sha(rp) == register_sha and sha(wp) == workbook_sha
pointer_before = sha(B / 'current-master.json')
qa = read(Q / 'candidate-register-readback.json')
assert qa['candidate_register_sha256'] == register_sha
plan = read(H / 'workbook-edit-plan.json')
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

def saved_book(path):
    result = {'values': {}, 'formulas': {}, 'links': {}}
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))]
        rels = {x.get('Id'): x.get('Target') for x in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for s in E.fromstring(z.read('xl/workbook.xml')).find(NS + 'sheets'):
            sn = s.get('name'); target = rels[s.get(R + 'id')]
            part = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            root = E.fromstring(z.read(part)); values = {}; formulas = {}
            for c in root.iter(NS + 'c'):
                value = c.findtext(NS + 'v', '')
                if c.get('t') == 's': value = strings[int(value)]
                elif c.get('t') == 'inlineStr': value = ''.join(c.find(NS + 'is').itertext())
                elif value and c.get('t') not in ('str', 'e'): value = float(value)
                values[c.get('r')] = value
                if c.find(NS + 'f') is not None: formulas[c.get('r')] = c.findtext(NS + 'f')
            result['values'][sn] = values; result['formulas'][sn] = formulas
            relpart = posixpath.dirname(part) + '/_rels/' + posixpath.basename(part) + '.rels'
            links = {x.get('Id'): x.get('Target') for x in E.fromstring(z.read(relpart))} if relpart in z.namelist() else {}
            for a in root.iter(NS + 'hyperlink'):
                result['links'][(sn, a.get('ref'))] = '#' + a.get('location') if a.get('location') else links[a.get(R + 'id')]
    return result

book = saved_book(wp); old_book = saved_book(H / 'inputs/master_workbook.before')
assert list(book['values']) == list(old_book['values']) and len(book['values']) == 28
assert book['formulas'] == old_book['formulas'] and sum(map(len, book['formulas'].values())) == 3407
for edit in plan['cell_changes'] + plan['calculated_value_changes']:
    assert old_book['values'][edit['sheet']][edit['cell']] == edit['before']
    assert book['values'][edit['sheet']][edit['cell']] == edit['value'], edit
assert book['links'] == old_book['links'] and len(book['links']) == 12206
qa.update(status='PASS_INDEPENDENT_MASTER_CANDIDATE_READBACK', register_sha256=register_sha,
          workbook_sha256=workbook_sha, authored_cell_edits_verified=106,
          derived_cell_edits_verified=30, original_formulas_preserved=3407,
          original_native_hyperlinks_preserved=12206, original_sheets_preserved=28)
write(Q / 'independent-candidate-readback.json', qa)

register = read(rp); active = set(register['active_option_ids'])
products = {x['product_id']: x for x in register['options'] if x['product_id'] in active}
packet = read(W / 'specification-completion-packet.json')
source_seal = source / 'sealed-handoff.json'; frozen = read(source_seal)
for rel, digest in frozen['files'].items(): assert sha(source / rel) == digest, rel
old_db = sqlite3.connect('file:' + str(source / 'complete-image-platform-register.sqlite') + '?mode=ro', uri=True)
old_products = {pid: json.loads(blob) for pid, blob in old_db.execute('SELECT product_id,record_json FROM products')}
assert set(products) == set(old_products) and len(products) == 188
changes = {(x['product_id'], x['field']): x for x in packet['changes']}
for pid, p in products.items():
    old = old_products[pid]
    assert {k: v for k, v in p.items() if k != 'master_fields'} == {k: v for k, v in old.items() if k != 'master_fields'}
    for field, mf in p['master_fields'].items():
        expected = changes.get((pid, field), {}).get('after', old['master_fields'][field])
        assert mf == expected

out = source.parent / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out.mkdir(exist_ok=False)
proofs = ['source-gallery-review.json', 'source-photo-correspondences.json', 'local-shopify-gallery-review.json', 'local-shopify-gallery-import-readback.json', 'current-file-visual-roles.json']
unchanged = proofs + ['owner-identity-projection.json', 'per-product-image-lists.json', 'product-family-navigation.json', 'product-image-association-review.json', 'current-images-without-option-scope.json', 'source-gallery-reader-index.json', 'family-image-reader-index.json', 'product-reader-index.json']
for name in unchanged + ['index.html', 'product-images.html', 'source-galleries.html', 'family-images.html']:
    shutil.copyfile(source / name, out / name)
for folder in ['products', 'families', 'source-galleries', 'source-association-review']:
    shutil.copytree(source / folder, out / folder)
old_report = B / 'outputs/coral-depth-wording-master-2026-10-25/index.html'
new_report = B / 'outputs/matched-listing-master-2026-10-25/index.html'
listing = read(W / 'sealed-handoff.json')['review']['path']
assert new_report.is_file() and Path(listing).is_file()
for page in out.rglob('*.html'):
    text = page.read_text().replace(str(source), str(out)).replace(str(old_report), str(new_report))
    page.write_text(text)
dimension_displays_updated = 0
for pid in products:
    page = out / 'products' / (pid + '.html'); text = page.read_text()
    for (cpid, field), change in changes.items():
        if cpid != pid: continue
        old_text, new_text = html.escape(change['before']['display']), html.escape(change['after']['display'])
        if old_text in text:
            text = text.replace(old_text, new_text)
            if field == 'Dimensions / depth': dimension_displays_updated += 1
    note = '<p class="notice"><a href="' + html.escape(listing + '#' + pid) + '">Checked listing treatment and complete working specifications</a>. New material and face-size entries remain labelled proposals or estimates.</p>'
    text = text.replace('</h1>', '</h1>' + note, 1); page.write_text(text)
assert dimension_displays_updated == 3
notice = '<p class="notice"><a href="' + html.escape(listing) + '">Current 188-option listing review and exports</a>: 47 existing individual records, four qualified Wall Circle pattern mappings, 135 proposed new or additional options, and two explicit native-listing exceptions. Historical source edges below remain preserved; a proposed new listing is not a newly verified source match.</p>'
for page in [out / 'index.html', out / 'source-association-review/index.html']:
    page.write_text(page.read_text().replace('</h1>', '</h1>' + notice, 1))

def rebase(v):
    if isinstance(v, str): return v.replace(str(source), str(out))
    if isinstance(v, list): return [rebase(x) for x in v]
    if isinstance(v, dict): return {k: rebase(x) for k, x in v.items()}
    return v

gap = out / 'source-association-review/all-65-case-dispositions.json'; write(gap, rebase(read(gap)))
summary = read(source / 'summary.json')
summary.update(status='PREPARED_COMPLETED_WORKING_SPECIFICATIONS_AND_LISTING_PLAN_GALLERY',
               recorded_utc=datetime.now(timezone.utc).isoformat(), target_register_sha256=register_sha,
               target_workbook_sha256=workbook_sha, material_proposals_added=27, face_size_estimates_added=3,
               new_physical_measurements=0, current_listing_treatment_plan=register['current_listing_treatment_plan'])
summary['next_work'] = ['Bind to the checked master publication.', 'Retain explicit native-listing exceptions and owner-held photography.']
write(out / 'summary.json', summary)
db = sqlite3.connect(out / 'complete-image-platform-register.sqlite'); old_db.backup(db)
for pid, product in products.items(): db.execute('UPDATE products SET record_json=? WHERE product_id=?', (json.dumps(product, ensure_ascii=False), pid))
db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)', ('integration_summary', json.dumps(summary, ensure_ascii=False)))
db.commit(); assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
counts = {}
for table, in old_db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    quoted = '"' + table.replace('"', '""') + '"'
    before = list(old_db.execute('SELECT * FROM ' + quoted)); after = list(db.execute('SELECT * FROM ' + quoted)); counts[table] = len(after)
    if table not in {'products', 'metadata'}: assert sorted(before, key=repr) == sorted(after, key=repr), table
    elif table == 'metadata': assert sorted((x for x in before if x[0] != 'integration_summary'), key=repr) == sorted((x for x in after if x[0] != 'integration_summary'), key=repr)
assert {pid: json.loads(blob) for pid, blob in db.execute('SELECT product_id,record_json FROM products')} == products
db.close(); old_db.close()
validation = rebase(read(source / 'product-reader-validation.json'))
validation.update(material_proposals_added=27, face_size_estimates_added=3, all188_products_equal_candidate_register=True)
write(out / 'product-reader-validation.json', validation)
remaining = read(source / 'remaining-work.json')
remaining['canonical_release'] = {'owner_thread': '01a144ab-1a7c-7223-a403-73a4d53d70ff', 'status': 'EXACT_MATCHED_LISTING_CANDIDATE_PREPARED', 'candidate_register_path': str(rp), 'candidate_register_sha256': register_sha, 'candidate_workbook_path': str(wp), 'candidate_workbook_sha256': workbook_sha}
remaining['current_listing_treatment_plan'] = register['current_listing_treatment_plan']
write(out / 'remaining-work.json', remaining)
binding = {'status': 'PREPARED_FOR_MAIN_PUBLICATION', 'register': str(rp), 'register_sha256': register_sha, 'workbook': str(wp), 'workbook_sha256': workbook_sha, 'previous_gallery_seal': str(source_seal), 'previous_gallery_seal_sha256': sha(source_seal), 'changed_working_field_objects': 30, 'physical_measurements_added': 0}
write(out / 'candidate-release-binding.json', binding)
write(out / 'publication-rebase.json', {**binding, 'unchanged_source_proof_files': {name: sha(out / name) for name in proofs}, 'this_increment_selected_reference_changes': 0, 'new_exact_variant_assignments': 0})
write(out / 'listing-plan-reference.json', register['current_listing_treatment_plan'])

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs): self.links.extend(v for k, v in attrs if k in {'src', 'href'} and v)

link_count = 0
for page in out.rglob('*.html'):
    parser = Links(); parser.feed(page.read_text())
    for link in parser.links:
        url = urlsplit(link)
        if url.scheme or url.netloc or not url.path: continue
        path = Path(unquote(url.path)); path = path if path.is_absolute() else page.parent / path
        assert path.exists(), (page, link); link_count += 1
for name in unchanged: assert sha(source / name) == sha(out / name), name
assert sha(B / 'current-master.json') == pointer_before
assert sha(rp) == register_sha and sha(wp) == workbook_sha
gallery_qa = {'status': 'PASS_MATCHED_LISTING_GALLERY_PROJECTION', 'register_sha256': register_sha, 'workbook_sha256': workbook_sha, 'product_records_equal_candidate': 188, 'changed_working_field_objects': 30, 'other1104retained_fields_preserved': True, 'all_photo_and_source_tables_unchanged': True, 'table_counts': counts, 'all65_historical_source_dispositions_preserved': True, 'current188_listing_treatments_linked_separately': True, 'updated_face_size_displays': dimension_displays_updated, 'local_links_checked': link_count, 'selected_references_changed': 0, 'canonical_or_platform_writes': 0}
write(out / 'matched-listing-projection-readback.json', gallery_qa)
shutil.copyfile(__file__, out / 'project_gallery.py')
seal = {'status': 'VERIFIED_COMPLETED_WORKING_SPECIFICATIONS_AND_LISTING_PLAN_GALLERY_CANDIDATE', 'sealed_utc': datetime.now(timezone.utc).isoformat(), 'reviewer_thread': '01a13fe6-495b-7253-b923-31823b4cbca8', 'canonical_publisher_thread': '01a144ab-1a7c-7223-a403-73a4d53d70ff', 'target_register_sha256': register_sha, 'target_workbook_sha256': workbook_sha, 'run': str(out), 'readers': {name: str(out / name) for name in ['index.html', 'product-images.html', 'source-galleries.html', 'family-images.html', 'source-association-review/index.html']}, 'counts': validation, 'all188_products_equal_candidate_register': True, 'owner_questions_remaining': 0, 'source_proof_files_byte_identical_to_frozen_review': {name: sha(out / name) for name in proofs}, 'source_product_link_rows_unchanged': 260, 'deferred_installation_gaps': 22, 'deferred_series_gaps': 1, 'new_physical_measurements': 0, 'selected_primary_references_changed': 0, 'new_exact_variant_assignments': 0, 'native_or_canonical_or_platform_writes_by_reviewer': 0, 'files': {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}}
sealpath = out / 'sealed-handoff.json'; write(sealpath, seal)
location = {'seal': str(sealpath), 'sha256': sha(sealpath), 'run': str(out), 'register_sha256': register_sha, 'workbook_sha256': workbook_sha}
write(Q / 'gallery-location.json', location); print(json.dumps({**location, 'qa': gallery_qa}, indent=2))
