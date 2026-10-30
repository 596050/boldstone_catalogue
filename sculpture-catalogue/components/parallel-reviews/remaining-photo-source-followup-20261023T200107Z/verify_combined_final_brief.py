import json, hashlib, datetime
from pathlib import Path
from html.parser import HTMLParser

J = Path(__file__).parent
B = J.parents[2]
A = J.parent / 'remaining-photo-sources-and-bordered-import-20261023T200049Z'
read = lambda p: json.loads(Path(p).read_text())
path = A / 'remaining-photograph-requests-final.json'
blob = path.read_bytes()
assert hashlib.sha256(blob).hexdigest() == '944fe77c81c5e5d75dbfb5c39943614aec92119225a3125f935d152ff91d8414'
req = {x['option_id']: x for x in json.loads(blob)['requests']}
own = {x['option_id']: x for x in read(J / 'context-photograph-requests-after-qualified-recheck.json')['requests']}
pointer = read(B / 'current-master.json')
register_path = B / pointer['register']
reg = {x['product_id']: x for x in read(register_path)['options']}
state = read(register_path.with_name('guided-owner-review-state.json'))
assert {i for i, x in req.items() if 'Display/context' in x['missing_roles']} == set(own) | {'BSI-3635E3DC3434'}
assert {i for i, x in req.items() if 'Series' in x['missing_roles']} == set(state['queues']['series'])
assert len(req) == 29 and sum(x['roles_count'] for x in req.values()) == 31
for oid, x in own.items():
    y = req[oid]
    assert x['photograph_to_supply'] == y['context_photograph_to_supply'] and x['photograph_to_supply'] in y['requested_photograph'], (oid, 'request')
    assert x['why_existing_sources_do_not_fill_role'] == y['why_existing_sources_do_not_fill_context_role'], (oid, 'finding')
    assert x['accepted_individual_reference'] == y['existing_individual_reference'], (oid, 'reference')
for oid, x in req.items():
    assert x['name'] == reg[oid]['name'] and x['existing_individual_reference']['file_id'] == reg[oid]['file_id'], oid
    assert x['native_source_creation_by_agent'] is False and x['current_status'] == 'EXACT_CURRENT_SOURCE_REQUIRED'
    assert x['display_scene_origin'] == 'UNVERIFIED_UNLESS_SOURCE_RECORDS_PROVIDED'
assert not set(req) & set(state['held_in_situ_ids'])
assert not set(req) & set(state['deferred_individual_ids'])
class Check(HTMLParser):
    def __init__(self): super().__init__(); self.links = []; self.ids = set()
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a': self.links.append(attrs.get('href', ''))
        if 'id' in attrs: self.ids.add(attrs['id'])
page = (A / 'remaining-photograph-requests-final.html').read_text()
c = Check(); c.feed(page)
native = [x for x in c.links if 'BOLDSTONE%20MASTER' in x]
anchors = [x for x in c.links if x.startswith('#')]
assert len(native) == 58 and all('https://www.dropbox.com/' in x for x in native)
assert anchors == ['#BSI-3635E3DC3434'] and all(x[1:] in c.ids for x in anchors)
assert len(c.links) == len(native) + len(anchors)
out = {'status': 'PASS_FINAL_COMBINED_PHOTOGRAPH_REQUEST_SCOPE_AND_CURRENT_REFERENCES', 'recorded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'packet': str(path), 'packet_sha256': hashlib.sha256(blob).hexdigest(), 'html_sha256': hashlib.sha256(page.encode()).hexdigest(), 'option_count': 29, 'active_context_roles': 14, 'series_roles': 17, 'role_count': 31, 'all_names_and_primary_ids_match_published_register': True, 'held_and_deferred_cases_excluded': True, 'B_13_exact_requests_findings_and_references_retained': True, 'current_Master_links_verified': 58, 'priority_anchor_target_verified': True, 'prior_attempts': ['The earlier un-enriched draft did not yet include B precise request text. No PASS was created.', 'Final-draft checks initially assumed the wrong finding field name, then omitted its valid Pewter anchor from the expected HTML link count. The actual schema and anchor target are now explicitly verified; no product, scope or reference assertion was removed.']}
(J / 'combined-photograph-brief-independent-check.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in out.items() if k != 'prior_attempts'}))
