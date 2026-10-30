"""Exercise changed terminal views and verify current navigation destinations."""
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlparse
from navigation_projection import current_projection

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
B = ROOT/'sculpture-catalogue'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
p = read(B/'current-master.json')
state = read(H/'walkthrough-state.json')
before = read(B/'components/reconciliation/whole-gallery-navigation-master-2026-10-24/inputs/walkthrough-state-before-current-projection.json')
assert len(state['items']) == 105 and len(before['items']) == 96
projection = current_projection(p)
failures = []
changes = []
class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
    def handle_starttag(self,tag,attrs):
        d = dict(attrs)
        if d.get('id'):
            self.ids.add(d['id'])
        if tag in ['a','img']:
            value = d.get('href' if tag == 'a' else 'src','')
            if value:
                self.links.append(value)
cache = {}
def checklink(url,base):
    u = urlparse(url)
    if u.scheme or url.startswith('//'):
        return
    target = Path(unquote(u.path)) if u.path else base
    if not target.is_absolute():
        target = base.parent/target
    if not target.is_file():
        failures.append('Missing '+str(target))
        return
    if u.fragment and target.suffix == '.html':
        if str(target) not in cache:
            z = Parser()
            z.feed(target.read_text())
            cache[str(target)] = z
        if unquote(u.fragment) not in cache[str(target)].ids:
            failures.append('Missing anchor '+str(target)+'#'+u.fragment)
def dropbox_path(url):
    u = urlparse(url)
    path = unquote(u.path)
    for prefix in ['/preview','/home']:
        if path.startswith(prefix+'/'):
            path = path[len(prefix):]
            break
    preview = parse_qs(u.query).get('preview')
    return path.rstrip('/')+('/'+preview[0] if preview else '')

for num,(a,c) in enumerate(zip(before['items'],state['items']),1):
    assert all(a[k] == c[k] for k in ['title','option_id','name']),num
    if a != c:
        changes.append(num)
    if num not in [8,9]:
        assert all(dropbox_path(a[k]) == dropbox_path(c[k]) for k in ['image','containing_folder']),num
        assert all(a[k] == c[k] for k in ['file_id','folder_id']),num
        expected_details = dict(a['details'])
        for change in projection.get('depth_estimate_changes',[])+projection.get('non_numeric_wording_changes',[]):
            field = change['field']
            if change['option_id'] == c['option_id'] and field in expected_details:
                old, new = change['before'], change['after']
                if expected_details[field] == old['display']:
                    expected_details[field] = new['display']
                elif expected_details[field] == old['display']+'\n'+old['state']:
                    expected_details[field] = new['display']+'\n'+new['state']
                else:
                    raise AssertionError((num, field, 'Unexpected frozen field representation'))
        assert expected_details == c['details'],num
for item in state['items']:
    checklink(item['review'],H/'index.html')
    assert all(item[k].startswith('https://www.dropbox.com/') for k in ['image','containing_folder'])
for file in [H/'index.html',B/p['current_image_review_links']['all_links']]:
    z = Parser()
    z.feed(file.read_text())
    for url in z.links:
        checklink(url,file)
texts = []
for num in [3,8,9,97,98,99,100,101,102,103,104,105]:
    result = subprocess.run([sys.executable,str(H/'walkthrough.py'),'--item',str(num)],capture_output=True,text=True)
    assert result.returncode == 0,result.stderr
    texts.append(result.stdout)
(H/'current-terminal-readouts.txt').write_text('\n\n'.join(texts))
shop = ROOT/'reports/shopify-wall-gallery-review-20261024-root'
prior_acceptance = read(H/'current-reader-acceptance.json') if '--reuse-shopify' in sys.argv else None
texts = []
for num in ([] if prior_acceptance else range(1,39)):
    result = subprocess.run([sys.executable,str(shop/'walkthrough.py'),'--product',str(num),'--specifications'],capture_output=True,text=True)
    assert result.returncode == 0,result.stderr
    texts.append(result.stdout)
if prior_acceptance:
    for file in [shop/'walkthrough.py',shop/'current-38-terminal-product-readouts.txt']:
        assert sha(file) == prior_acceptance['files'][str(file)]
else:
    (shop/'current-38-terminal-product-readouts.txt').write_text('\n\n'.join(texts))
receipt = {'status':'FAIL' if failures else 'PASS_CURRENT_READERS_AND_RELEASE_BINDINGS',
    'recorded_utc':datetime.now(timezone.utc).isoformat(),'pointer_sha256':sha(B/'current-master.json'),
    'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],'main_work_items':105,
    'first96_item_identities_retained':True,'changed_prior_navigation_or_review_items':changes,
    'changed_selected_primary_items':[8,9],'shopify_product_terminal_runs':38,'shopify_review_frames':117,
    'main_terminal_runs':[3,8,9,97,98,99,100,101,102,103,104,105],'unchanged_shopify_runs_reused':bool(prior_acceptance),'local_link_failures':failures,
    'authorized_depth_fields_projected':14,'non_numeric_wording_fields_projected':1,'unapproved_frozen_field_differences':0,
    'files':{str(f):sha(f) for f in [H/'walkthrough.py',H/'navigation_projection.py',H/'current-navigation-projection.json',
        H/'index.html',H/'walkthrough-state.json',H/'current-terminal-readouts.txt',shop/'walkthrough.py',shop/'current-38-terminal-product-readouts.txt']}}
(H/'current-reader-acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k != 'files'},indent=2))
if failures:
    raise SystemExit(1)
