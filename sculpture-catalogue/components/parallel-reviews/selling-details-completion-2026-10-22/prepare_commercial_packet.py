"""Prepare a bounded commercial overlay; never writes the shared master."""
import hashlib
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
SOURCE = BASE / 'components/reconciliation/moonphases-dune-ripple-master-refresh-2026-10-22/canonical-master-register.json'
REPORT = BASE / 'outputs/selling-details-completion-2026-10-22'
REPORT.mkdir(parents=True, exist_ok=True)
DECISION = 'ALL186:ESTIMATED-PRICES-MADE-TO-ORDER-1-2-WEEKS:2026-10-22'
OWNER_TEXT = 'Estimate a price, made to order and lead time 1-2 weeks'
TRANSCRIPT = Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-01a13fe6-495b-7253-b923-31823b4cbca8.jsonl')

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
def canonical_sha(obj): return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
def money(value): return '£' + (f'{value:,.0f}' if float(value).is_integer() else f'{value:,.2f}')

assert sha(SOURCE) == '9b92c621f3725571517b2009b4776db36f6b3cb3f881850662d59e977d2768a2'
reg = json.loads(SOURCE.read_text())
options = {o['product_id']: o for o in reg['options']}
owner = None
for n, line in enumerate(TRANSCRIPT.open(), 1):
    if OWNER_TEXT not in line: continue
    obj = json.loads(line)
    p = obj.get('payload', {})
    if obj.get('type') != 'response_item' or p.get('role') != 'user': continue
    text = '\n'.join(c.get('text', '') for c in p.get('content', []) if c.get('type') in ['input_text', 'text'])
    if text == OWNER_TEXT:
        owner = {'thread_id': '01a13fe6-495b-7253-b923-31823b4cbca8', 'path': str(TRANSCRIPT), 'line': n, 'timestamp': obj['timestamp'], 'message_id': p.get('id'), 'role': 'user', 'text': text, 'raw_line_sha256': hashlib.sha256(line.encode()).hexdigest()}
assert owner and owner['message_id'] == 'msg_01a1654f-a8e5-79c0-961a-cbf737a7a84d'
dump(HERE / 'owner-commercial-instruction.json', {'decision_id': DECISION, 'source': owner, 'interpretation': 'Use estimated individual prices, preserving accepted estimates; owner instructs made-to-order availability and lead time 1–2 weeks. Numeric estimates are assistant estimates, not owner-confirmed exact selling amounts. No physical stock or current platform offer is certified.'})

overrides = {}
def choose(ids, amount, category, basis, comparators=()):
    for pid in ids:
        assert pid in options and pid not in overrides
        overrides[pid] = {'amount': amount, 'category': category, 'basis': basis, 'comparator_option_ids': list(comparators)}

choose(['BSI-9278986A1A89'], 350, 'new_estimate_previously_quote_only', '55 × 30 cm narrow relief: positioned above Brancusi 50 × 25 cm £250 and below 55 × 55 cm Spiralfish £600. Individual comparison; no set price division.', ['BSI-923D5E50A898', 'BSI-B19E0B8602C1'])
choose(['BSI-7CDE8362BB51'], 600, 'new_estimate_previously_quote_only', '55 × 55 cm relief: use the existing £600 individual Spiralfish White working estimate as a size/form comparator. Uncosted estimate for Bone Spiral 2.', ['BSI-B19E0B8602C1'])
choose(['BSI-F95020D6821C'], 4000, 'new_estimate_previously_quote_only', 'Owner size 250 × 100 cm. Large single artwork benchmark Icarus 200 × 100 cm £3,500, with a modest scale allowance; £3,000–£5,000 Riyadh commission range provides context. This is a judgement estimate, not a Chelsea quote or a proportional cost model.', ['BSI-123AABD474C1', 'BSI-B9DA00108196'])
choose(['BSI-ADD5F3BEFCF5'], 225, 'new_estimate_previously_quote_only', '30 × 30 cm Cup Ring: same working price as the separate Spiral CRS1 panel. Historical £112 individual trade reference remains distinct; paired prices are not divided.', ['BSI-70BDE00F2855'])
choose([pid for pid,o in options.items() if o['family'] == 'Fingerprint'], 300, 'new_estimate_previously_quote_only', '40 × 40 cm face, approximately 3 cm depth: between 30 cm decorative panels around £225–£250 and 40 × 40 cm Wave/Moonshadow £350. Same uncosted estimate for Concentric 1–3 Cream/White; no unsubstantiated finish surcharge.', ['BSI-70BDE00F2855', 'BSI-B6EC1EDD319F', 'BSI-A57A49000891'])
choose(['BSI-04D6E8690F30'], 262.50, 'new_estimate_previously_quote_only', 'Conditional estimate for the owner current 70 × 15 cm White configuration, using the retained current White Frozen Fish working price. Not the obsolete 100 × 22 cm £550 source. Legacy FFL1/FFS2 identity stays deferred and this row is not made sell-ready.', ['BSI-FE10273D3655'])
choose([pid for pid,o in options.items() if o['family'] == 'Gleneagles Vine and Tendril'], 250, 'new_estimate_previously_quote_only', '35 × 35 cm individual relief: middle of the catalogue small-panel working band, compared with £225 Spiral and £350 Leaf Form. Each component priced separately; not an apportionment of a four-panel set.', ['BSI-70BDE00F2855', 'BSI-6581D83760F1'])
choose(['BSI-3BFB1137D230'], 3500, 'new_estimate_previously_quote_only', 'Owner 100 × 100 × 50 cm fountain body: large sculpture judgement estimate in the existing large-work band, using Barbados Wave £2,880 and Riyadh £3,000–£5,000 only as context. Construction and hollow-body details are uncosted. Sculpture body only; water equipment and installation are separate.', ['BSI-A76B86DA7928', 'BSI-B9DA00108196'])
choose([pid for pid,o in options.items() if o['family'] == 'Lava Moon'], 3500, 'new_estimate_previously_quote_only', 'Owner 80 × 240 cm single panel, close in face area to Icarus 200 × 100 cm at £3,500 and within the large Riyadh commission range. Same uncosted estimate for all three components and White/Sandstone appearances; no material equivalence or finish surcharge is asserted.', ['BSI-123AABD474C1', 'BSI-B9DA00108196'])
choose(['BSI-65A93033A200','BSI-4515726BBC18'], 275, 'new_estimate_previously_quote_only', '£225 standard White Moonphase working reference plus a provisional £50 border allowance. Border construction and actual outer size remain unverified; this is not a sourced border offer.', ['BSI-818D745F1357'])
choose(['BSI-161DFE20DFB0','BSI-B1DCB5B08396'], 300, 'new_estimate_previously_quote_only', '£225 White Moonphase reference plus £75 provisional decorative-finish allowance, consistent with the catalogue White/Gold Acanthus difference. Gold-coloured treatment is not certified genuine gold leaf.', ['BSI-818D745F1357', 'BSI-9C7406B46836', 'BSI-2CA935C1A57A'])
choose(['BSI-75ACAD5A9841'], 225, 'new_estimate_previously_quote_only', 'Current 30 × 30 cm target compared with Spiral CRS1 £225. The earlier £500 larger-size proposal remains superseded and is not reused.', ['BSI-70BDE00F2855'])
choose(['BSI-8DE87C63B013'], 262.50, 'source_placeholder_replaced_by_estimate', 'Owner current 70 × 15 cm FFS2 configuration: use the White individual working price as an uncosted Terracotta estimate with no assumed finish surcharge. Unsupported £44.44 review placeholder is preserved only in history, not promoted to a current price.', ['BSI-FE10273D3655'])
choose(['BSI-BFB0D3D29852'], 300, 'existing_estimate_selected_from_conflicting_sources', 'Retain the existing £300 repricing proposal as the working estimate. Historical £48.44 listing amount remains source evidence, not the new estimate.', ['BSI-612EF4DBB555', 'BSI-27967D2BD7B4'])
choose(['BSI-8C0D9152DF73','BSI-41E5370B1314','BSI-93FC0B4F78DA'], 225, 'source_conflict_resolved_for_working_estimate', 'Select the named individual retail-draft £225 benchmark, matching the existing MP4 White working proposal. Cached £58.79, prior £182.05 estimate and £112 trade remain distinct historical references. Selection is an estimated catalogue price, not a live-offer reconciliation.', ['BSI-818D745F1357'])
choose(['BSI-947F365275C5'], 200, 'source_conflict_resolved_for_working_estimate', 'New Rust commission estimate using the £175 White baseline and the £200 related coloured Dune Ripple working band. The two same-SKU £35.33/£65.33 source records remain a collision; neither is selected as a current quote.', ['BSI-98997871B7EC', 'BSI-6F3C6CD908A0'])
choose(['BSI-C3573D23A4B7','BSI-8DDEA2FEC9DA','BSI-4536FDCA0DA9','BSI-59530C6155C2'], 200, 'new_commission_estimate_prior_listing_amount_retained_in_history', 'New individual commission estimate, using the existing £175 White baseline and £200 coloured Dune Ripple working band. Prior £40.33/£60.33/£45 listing figures remain dated source amounts, not errors or confirmed new-commission prices. The accepted £200/£250 multieffect estimates are unchanged.', ['BSI-3FCC58C3B4BD','BSI-6F3C6CD908A0','BSI-6405184B86EB'])

special_units = {'BSI-123AABD474C1':'per single artwork', 'BSI-489226D6FF87':'per individual column', 'BSI-CBD8D0C8DE19':'per basin', 'BSI-21DCD11AD8C6':'for the complete work shown', 'BSI-3BFB1137D230':'for the dry sculpture body'}
water = {'BSI-3DEA4D29C4A2': 'Pump, basin and pipework priced separately.', 'BSI-D886F539DD3E': 'Pump, basin, pipework and installation quoted separately.', 'BSI-CBD8D0C8DE19': 'Separate support, pump, plumbing and installation excluded.', 'BSI-22E4E4F99696': 'Basin, pump and installation priced separately.', 'BSI-1B70A9FB1B26': 'Pump, basin and installation priced separately.', 'BSI-22B6E4FB3DD8': 'Basin, pump and installation priced separately.', 'BSI-3BFB1137D230': 'Water-system equipment, installation and delivery priced separately.'}
entries = []
for pid, option in options.items():
    old = option['master_fields']['Individual price']['display']
    selected = overrides.get(pid)
    if selected:
        amount = selected['amount']; high = None
        category = selected['category']; basis = selected['basis']; comparators = selected['comparator_option_ids']
    else:
        first = re.search(r'(?:£|GBP\s*)([\d,]+(?:\.\d+)?)', old)
        assert first, (pid, old)
        amount = float(first.group(1).replace(',', ''))
        tail = old[first.end():]
        rng = re.match(r'\s*[–-]\s*£?([\d,]+(?:\.\d+)?)', tail)
        high = float(rng.group(1).replace(',', '')) if rng else None
        category = 'existing_numeric_working_value_or_range_retained'
        basis = 'Existing headline individual amount/range retained under the owner instruction. Earlier source captures and accepted proposals retain their original status; this amount is a working estimate, not a newly verified live offer.'
        comparators = [pid]
    unit = special_units.get(pid, 'per individual panel')
    if option['family'] == 'Wall Circle': unit = 'per sculpture, including RGB lighting'
    estimate = money(amount) + ('–' + money(high) if high is not None else '')
    price_display = f'{estimate} {unit} — estimated price.'
    if pid in water: price_display += ' ' + water[pid]
    if pid == 'BSI-04D6E8690F30': price_display += ' Conditional on the 70 × 15 cm configuration; legacy identity remains deferred.'
    availability = 'Made to order; lead time 1–2 weeks — owner instruction, 22 October 2026.'
    if pid == 'BSI-04D6E8690F30': availability += ' Legacy identity unresolved; this record remains deferred.'
    if pid == 'BSI-3C849B547D50': availability = 'Made to order for new commissions; lead time 1–2 weeks — owner instruction, 22 October 2026. The reference artwork was described as a one-off original; availability of that exact piece and exact finish reproduction remain unverified.'
    if pid == 'BSI-83F1AACE15E9': availability = 'Made to order for new commissions; lead time 1–2 weeks — owner instruction, 22 October 2026. Historical source stock quantity 1 is retained as a source record, not a current physical inventory count.'
    specific_owner_policy = pid == 'BSI-46F6DB226213'
    if specific_owner_policy:
        # This exact finish already has a field-specific owner price and lead time.
        # The latest question/request concerns unresolved selling details only.
        price_display = old
        availability = option['master_fields']['Availability']['display']
        category = 'specific_owner_confirmed_price_and_lead_time_retained'
        basis = option['master_fields']['Individual price']['basis']
    prior = {f: option['master_fields'][f] for f in ['Individual price', 'Availability']}
    evidence = []
    for cpid in comparators:
        comp = options[cpid]
        evidence.append({'option_id':cpid, 'name':comp['name'], 'json_pointer':f"/options/{reg['options'].index(comp)}/master_fields/Individual price", 'current_working_price':comp['master_fields']['Individual price']['display'], 'current_working_dimensions':comp['master_fields']['Dimensions / depth']['display']})
    entries.append({'product_id':pid, 'name':option['name'], 'family':option['family'], 'canonical_component_id':option.get('canonical_component_id'), 'before_master_fields':prior, 'before_master_fields_sha256':canonical_sha(prior), 'after':{'Individual price':{'display':price_display, 'state':'Owner-authorized working price estimate; exact amount not separately owner-confirmed; not a verified live offer', 'basis':basis}, 'Availability':{'display':availability, 'state':'Owner-instructed made-to-order and 1–2 week lead-time policy', 'basis':'Direct owner instruction recorded 22 October 2026. This sets the catalogue selling policy; it does not assert a physical stock count or certify production capacity, dispatch or delivery timing.'}}, 'selling_details':{'currency':'GBP','estimated_price':amount,'estimated_price_upper':high,'price_status':'estimate','price_selection':category,'sale_unit':unit,'included_or_excluded_scope':water.get(pid, 'RGB lighting included.' if option['family']=='Wall Circle' else ''),'availability':'made_to_order','lead_time_min_weeks':1,'lead_time_max_weeks':2,'lead_time_basis':'direct_owner_instruction','lead_time_start_event':None,'delivery_time_included':None,'tax_treatment':None,'physical_stock_quantity':None,'identity_deferred':pid=='BSI-04D6E8690F30','customer_listing_readiness_changed':False,'policy_ref':DECISION}, 'comparators':evidence,'current_dimensions':option['master_fields']['Dimensions / depth']['display'],'image_url':option.get('image_url'),'folder_url':option.get('folder_url')})
    if specific_owner_policy:
        entries[-1]['after'] = {f:{k:prior[f][k] for k in ['display','state','basis']} for f in prior}
        entries[-1]['retain_current_commercial_fields_exactly'] = True
        entries[-1]['selling_details'].update({'price_status':'specific_owner_confirmed_working_price','lead_time_max_weeks':1,'lead_time_basis':'prior_specific_owner_instruction_retained','catalogue_stock_policy':'unlimited made-to-order; not a finite physical stock count','policy_ref':'PRIOR-SPECIFIC-MCP4-VERDIGRIS-RUST-PRICE-AND-AVAILABILITY'})
    if pid in ['BSI-3C849B547D50','BSI-83F1AACE15E9']:
        entries[-1]['selling_details']['made_to_order_scope'] = 'new commissions; existing photographed cast stock and exact reproduction not certified'

assert len(entries) == 186 and len({e['product_id'] for e in entries}) == 186
counts = dict(Counter(e['selling_details']['price_selection'] for e in entries))
assert counts['new_estimate_previously_quote_only'] == 27
assert sum(e['selling_details']['estimated_price_upper'] is not None for e in entries) == 7
for e in entries:
    assert e['selling_details']['estimated_price'] > 0
    if not e.get('retain_current_commercial_fields_exactly'):
        assert 'estimated price' in e['after']['Individual price']['display']
        assert '1–2 weeks' in e['after']['Availability']['display']
    else:
        assert '£175' in e['after']['Individual price']['display'] and '1 week' in e['after']['Availability']['display']
packet = {'schema':'boldstone-commercial-completion-v1','prepared_utc':datetime.now(timezone.utc).isoformat(),'status':'READY_FOR_SOLE_MASTER_WRITER','decision_id':DECISION,'owner_instruction':{'path':str(HERE/'owner-commercial-instruction.json'),'sha256':sha(HERE/'owner-commercial-instruction.json')},'source_register':{'path':str(SOURCE),'sha256':sha(SOURCE)},'summary':{'options':186,'commercial_field_groups':372,'numeric_price_ranges_retained':7,'selection_counts':counts,'individual_photo_needs':21,'legacy_identity_deferred':1,'in_situ_image_gaps':61,'series_image_gaps':18},'merge_contract':{'mutate_only_current_fields':['Individual price','Availability'],'preserve_original_specifications_and_assertions':True,'append_current_commercial_policy_and_prior_field_snapshots':True,'preserve_other_four_current_fields_and_physical_flags':True,'preserve_ids_names_families_aliases_images_and_counts':True,'preserve_platform_offer_records_and_conflicts':True,'no_live_platform_price_assertion':True,'no_platform_or_dropbox_writes':True,'no_listing_readiness_upgrade':True,'guard_each_before_master_fields_sha256':True},'entries':entries}
packet['summary'].update({'changed_commercial_field_groups':370,'estimated_price_options':185,'specific_owner_commercial_exception_retained':1,'default_1_to_2_week_options':185,'specific_1_week_options':1})
packet['merge_contract']['preserve_specific_owner_confirmed_commercial_fields'] = ['BSI-46F6DB226213']
packet['merge_contract']['separately_authorized_parallel_image_overlay_allowed'] = True
packet['merge_contract']['image_counts_in_summary_are_source_baseline_not_new_publication_assertions'] = True
dump(HERE/'price-completion-packet.json',packet)
dump(HERE/'packet-verification.json',{'status':'PASS','owner_message_verified':True,'options':186,'new_quote_only_estimates':27,'estimated_ranges_retained':7,'four_other_fields_edits':0,'master_writes':0,'remote_writes':0,'selection_counts':counts})

esc=lambda x:html.escape(str(x or ''),quote=True)
rows=[]
for e in entries:
    change=e['selling_details']['price_selection'] not in ['existing_numeric_working_value_or_range_retained','specific_owner_confirmed_price_and_lead_time_retained']
    lead = '1 week — existing owner policy' if e.get('retain_current_commercial_fields_exactly') else '1–2 weeks'
    rows.append('<tr data-new="'+str(int(change))+'"><td><strong>'+esc(e['name'])+'</strong><br><small>'+esc(e['product_id'])+'</small><br><a href="'+esc(e['image_url'])+'">Reference image</a> · <a href="'+esc(e['folder_url'])+'">Dropbox folder</a></td><td>'+esc(e['after']['Individual price']['display'])+'</td><td>Made to order<br>'+lead+('<br><strong>Identity deferred</strong>' if e['selling_details']['identity_deferred'] else '')+'</td><td>'+esc(e['after']['Individual price']['basis'])+'<details><summary>Earlier price and availability</summary><p>'+esc(e['before_master_fields']['Individual price']['display'])+'</p><p>'+esc(e['before_master_fields']['Availability']['display'])+'</p></details></td></tr>')
doc='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone — estimated prices and lead times</title><style>body{font:16px/1.5 system-ui,sans-serif;color:#202a29;background:#f8f7f3;margin:0;padding:32px}main{max-width:1350px;margin:auto}h1{font-size:30px;margin-bottom:8px}p{max-width:1000px}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;vertical-align:top;padding:14px;border-bottom:1px solid #d9dedb}th{background:#203e37;color:white;position:sticky;top:0}td:nth-child(1){width:26%}td:nth-child(2){width:23%}td:nth-child(3){width:13%}small{color:#67736f}a{color:#176049}input,button{font:inherit;padding:10px;margin:12px 10px 20px 0}input{min-width:260px}details{margin-top:10px;font-size:14px}#status{padding:12px 16px;background:#e8e3cf;border-radius:5px}@media(max-width:800px){body{padding:16px}table{font-size:13px}th,td{padding:7px}}@media print{input,button{display:none}th{position:static}}</style><main><h1>Estimated prices and lead times</h1><p>186 current working options. Prices are estimates. The owner instructs <strong>made to order, with a 1–2 week lead time</strong>. Existing numerical estimates and ranges are retained; 27 quote-only entries now have an individual estimate. Historical prices and unresolved source conflicts remain available below.</p><p id="status">Prepared for integration into the master catalogue. No website or Dropbox product records have been changed.</p><p><a href="../moonphases-dune-ripple-master-refresh-2026-10-22/individual-images.html">21 separate photographs required + 1 deferred identity</a> · <a href="../moonphases-dune-ripple-master-refresh-2026-10-22/in-situ-images.html">61 in-situ gaps</a> · <a href="../moonphases-dune-ripple-master-refresh-2026-10-22/series-images.html">18 series gaps</a></p><p>Each price covers the individual sculpture or stated unit. Existing RGB inclusions and water-system exclusions are shown. Tax treatment and delivery timing remain unspecified. The deferred Frozen Fish record remains an identity check, with a conditional estimate only.</p><input id="q" type="search" placeholder="Find a sculpture or family" aria-label="Find a sculpture"><button id="new" type="button">Show new estimates and selections</button><span id="count">186 options</span><table><thead><tr><th>Sculpture</th><th>Estimated price</th><th>Availability / lead time</th><th>Basis and history</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></main><script>let changes=false;const rows=[...document.querySelectorAll('tbody tr')],q=document.querySelector('#q');function filter(){const value=q.value.toLowerCase();let count=0;for(const row of rows){const show=row.textContent.toLowerCase().includes(value)&&(!changes||row.dataset.new==='1');row.hidden=!show;if(show)count++}document.querySelector('#count').textContent=count+' options'}q.addEventListener('input',filter);document.querySelector('#new').addEventListener('click',function(){changes=!changes;this.textContent=changes?'Show all options':'Show new estimates and selections';filter()});</script></html>'''
(REPORT/'index.html').write_text(doc)
doc = doc.replace('Prices are estimates. The owner instructs', 'Prices are estimates except the retained owner-confirmed £175 MCP4 Verdigris and Rust price. The owner instructs').replace('Existing numerical estimates and ranges are retained;', 'The existing specific 1-week MCP4 Verdigris and Rust policy is retained. Accepted numerical estimates and ranges are retained;')
(REPORT/'index.html').write_text(doc)
dump(REPORT/'publication-state.json',{'status':'PREPARED_AWAITING_MASTER_INTEGRATION','packet_sha256':sha(HERE/'price-completion-packet.json'),'options':186})
dump(HERE/'packet-seal.json',{'packet':{'path':str(HERE/'price-completion-packet.json'),'sha256':sha(HERE/'price-completion-packet.json')},'owner_instruction':{'path':str(HERE/'owner-commercial-instruction.json'),'sha256':sha(HERE/'owner-commercial-instruction.json')},'report':{'path':str(REPORT/'index.html'),'sha256':sha(REPORT/'index.html')},'summary':packet['summary']})
print(json.dumps({'packet_sha256':sha(HERE/'price-completion-packet.json'),'summary':packet['summary'],'report':str(REPORT/'index.html')},indent=2))
