"""Independent saved-report checks; does not run or import the report builder."""
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs
import hashlib
import json

L = Path(__file__).resolve().parent
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def objsha(x): return hashlib.sha256(json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
def save(n, x):
    with (L / n).open('x') as f: json.dump(x, f, ensure_ascii=False, indent=2); f.write('\n')
def target(url):
    z = urlsplit(url)
    assert z.scheme == 'https' and z.netloc == 'www.dropbox.com'
    p = unquote(z.path)
    prefix = next(s for s in ['/home', '/preview'] if p.startswith(s + '/'))
    return p[len(prefix):] + ('/' + parse_qs(z.query)['preview'][0] if 'preview' in parse_qs(z.query) else '')
def observed_path(o):
    p = o.get('display_path') or o.get('path_display') or o.get('path')
    return '/' + p.split('//', 1)[1].lstrip('/') if p.startswith('ns:') else p
def resolve(doc, pointer):
    for token in pointer.lstrip('/').split('/'):
        key = token.replace('~1', '/').replace('~0', '~')
        doc = doc[int(key)] if isinstance(doc, list) else doc[key]
    return doc
checks=[]
def check(name, ok, details=None): checks.append({'name': name, 'passed': bool(ok), 'details': details})
r=read(L/'coverage-review.json'); inputs=read(L/'input-manifest.json')
source_docs={v['path']:read(v['path']) for v in inputs.values()}
g=source_docs[inputs['register']['path']]; p=source_docs[inputs['pointer']['path']]
options={o['product_id']:o for o in g['options']}
inventory=read(L/'scoped-inventory.json')['entries']; files={x['id']:x for x in inventory}
folders={f['folder_id']:f for f in r['folders']}
check('all_saved_sources_master_workbook_and_three_controls_unchanged', all(sha(path)==h for path,h in r['source_guards'].items()))
check('same_188_active_189_retained_catalogue_and_no_new_options', len(g['active_option_ids'])==188 and len(g['options'])==189 and r['counts']['new_options']==0)
check('13_name_screen_options_19_related_options_9_families_38_folders', r['counts']['screened_named_water_or_basin_options']==13 and len(r['options'])==19 and len(r['families'])==9 and len(folders)==38)
check('all_19_complete_option_records_and_114_full_working_fields_preserved',
      all(objsha(options[o['option_id']])==o['complete_option_sha256'] and options[o['option_id']]['master_fields']==o['master_fields'] and len(o['master_fields'])==6 for o in r['options']))
check('614_unique_saved_file_IDs_and_all_folder_counts_reconcile',
      len(files)==len(inventory)==614 and sum(f['saved_inventory_file_count'] for f in r['folders'])==614 and
      Counter(f['parent_id'] for f in inventory)==Counter({fid:f['saved_inventory_file_count'] for fid,f in folders.items()}))
check('all_inventory_paths_and_exact_parent_paths_within_allowed_wall_root',
      all(f['path'].startswith(r['allowed_root']+'/') and f['path'].rsplit('/',1)[0].casefold()==folders[f['parent_id']]['folder_path'].casefold() for f in inventory))
evidence_fail=[]
for f in inventory:
    e=f['evidence'][-1]; observed=resolve(source_docs[e['path']],e['locator'])
    if (observed.get('file_id') or observed.get('id'))!=f['id'] or observed_path(observed)!=f['path']:
        evidence_fail.append(f['id'])
check('every_file_resolves_to_its_exact_saved_source_ID_and_path',not evidence_fail,evidence_fail)
check('all_19_selected_file_folder_and_URL_bindings_match_saved_inventory',
      all(o['file_id'] in files and files[o['file_id']]['parent_id']==o['folder_id'] and
          target(o['image_url'])==files[o['file_id']]['path'] and
          target(o['folder_url']).casefold()==folders[o['folder_id']]['folder_path'].casefold() and
          all(o['primary_inventory_binding'].values()) for o in r['options']))
check('all_38_folders_have_existing_qualified_associations_without_new_product_inference',
      not r['unmatched_folder_records'] and all(f['direct_option_ids'] or f['role_bindings'] or f['arrangement_refs'] or f['configuration_evidence'] for f in r['folders']) and
      all(f['missing_product_inferred'] is False and f['new_option_created'] is False for f in r['folders']))
check('retained_configuration_associations_match_source_records_exactly',
      all(any(c['configuration_id']==e['configuration_id'] and fid in c[e['association']] and
          c.get('exact_supported_target_ids',[])==e['existing_target_option_ids'] and c.get('exact_supported_target_basis','')==e['qualification']
          for c in g['source_media_configuration_coverage']) for fid,f in folders.items() for e in f['configuration_evidence']))
arr=r['Moonphase_arrangement']; original=next(x for x in g['arrangement_context_references'] if x['reference_id']==arr['reference_id'])
members=[e for e in g['confirmed_arrangement_member_edges'] if e['reference_id']==arr['reference_id']]
check('Moonphase_four_existing_owner_members_preserved_without_new_water_build',
      len(arr['members'])==len(members)==4 and
      [{k:v for k,v in e.items() if k not in ['individual_image_url','individual_folder_url']} for e in arr['members']]==members and
      arr['owner_member_confirmation']==original['owner_member_confirmation'] and
      arr['owner_member_confirmation']['water_ready_build_or_fountain_sale_unit_confirmed'] is False and
      arr['counted_as_working_product'] is False and arr['individual_count_increment']==0)
check('water_name_only_source_is_qualified_not_classified_as_operational_fountain', r['name_only_source_note']['offer_ref']=='O017' and 'not sufficient' in r['name_only_source_note']['note'])
class Page(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.ids=[]; self.text=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if 'id' in d:self.ids.append(d['id'])
        if tag=='a':self.links.append(d.get('href',''))
    def handle_data(self,s):self.text.append(s)
page=Page();page.feed((L/'review.html').read_text()); rendered=' '.join(page.text)
check('HTML_contains_each_current_option_image_folder_and_six_working_displays',
      all(o['option_id'] in page.ids and o['image_url'] in page.links and o['folder_url'] in page.links and
          all(v['display'] in rendered for v in o['master_fields'].values()) for o in r['options']))
check('HTML_contains_each_folder_example_and_all_four_Moonphase_member_links',
      all(f['folder_url'] in page.links and (not f['representative_image'] or f['representative_image']['image_url'] in page.links) for f in r['folders']) and
      all(e['individual_image_url'] in page.links and e['individual_folder_url'] in page.links for e in arr['members']))
check('all_internal_report_anchors_resolve_and_IDs_are_unique',
      len(page.ids)==len(set(page.ids)) and all(h[1:] in page.ids for h in page.links if h.startswith('#')))
check('no_outside_root_Dropbox_URLs_in_report', all(target(h).startswith(r['allowed_root']+'/') for h in page.links if not h.startswith('#')))
terminal=(L/'terminal-review.txt').read_text()
check('terminal_walkthrough_has_all_19_exact_images_and_containing_folders', all(o['name'] in terminal and o['image_url'] in terminal and o['folder_url'] in terminal for o in r['options']))
check('scope_preserves_holds_and_does_not_claim_live_inventory_or_physical_verification',
      all(r['counts'][k]==0 for k in ['native_calls','native_writes','platform_writes','shared_writes','new_image_roles','new_physical_verifications']) and
      len(g['source_offer_edges'])==81 and p['current_structure_discovery_scope']['new_outside_root_searches_listings_downloads_permitted'] is False and
      'not a fresh whole-library enumeration' in r['limitations'][0])
check('source_guards_stable_at_completion', all(sha(path)==h for path,h in r['source_guards'].items()))
result={'status':'PASS' if all(x['passed'] for x in checks) else 'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'checks_passed':sum(x['passed'] for x in checks),'checks_total':len(checks),'checks':checks,
    'source_pointer_sha256':r['source_guards'][inputs['pointer']['path']], 'source_register_sha256':r['source_guards'][inputs['register']['path']],
    'scope':'Saved coverage/navigation evidence only; no source or catalogue mutation and no live Dropbox/Shopify calls.'}
save('verification.json',result)
seal={'status':result['status'],'recorded_utc':result['recorded_utc'],
    'files':[{'path':str(L/n),'sha256':sha(L/n)} for n in ['build_review.py','verify_review.py','coverage-review.json','scoped-inventory.json','input-manifest.json','review.html','terminal-review.txt','verification.json']],
    'source_register_sha256':result['source_register_sha256'],'shared_writes':0}
save('sealed-handoff.json',seal)
print(json.dumps({'status':result['status'],'passed':result['checks_passed'],'total':result['checks_total'],
    'failed':[x for x in checks if not x['passed']],'seal_sha256':sha(L/'sealed-handoff.json')},indent=2))
