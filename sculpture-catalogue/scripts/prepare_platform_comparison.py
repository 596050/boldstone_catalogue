"""Reconcile the supplied Squarespace and Shopify wall-product records."""
import hashlib,html,json,re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

project=Path(__file__).resolve().parents[1];ev=project/'evidence'
source_file=project.parent/'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx'
source_sha=hashlib.sha256(source_file.read_bytes()).hexdigest()
assert source_sha=='7e6911a88ea9c9fd3214bdf860e24d6ad72ee755302efd6a9acc4db85c52c5c9'
source=json.loads((ev/'catalogue_source_tables_2026-10-15.json').read_text())
ss=source['SS Wall Products'];sh=source['SH Wall Products']
ss_by_id={p['Product ID [Non Editable]']:p for p in ss}
sh_by_handle={p['Handle']:p for p in sh}
assert len(ss_by_id)==len(ss)==80 and len(sh_by_handle)==len(sh)==38

class Plain(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
    def handle_starttag(self,tag,attrs):
        if tag in ['p','li','ul','ol','div','br']:self.parts.append(' ')
    def handle_endtag(self,tag):
        if tag in ['p','li','ul','ol','div']:self.parts.append(' ')
def plain(value):
    p=Plain();p.feed(value or '');return re.sub(r'\s+',' ',''.join(p.parts)).strip()
def norm(value):return re.sub(r'\s+',' ',html.unescape(value or '')).strip().casefold()
ss_by_sku=defaultdict(list)
for p in ss:
    if p['SKU']:ss_by_sku[p['SKU']].append(p)
sh_by_sku=defaultdict(list)
for p in sh:
    if p['Variant SKU']:sh_by_sku[p['Variant SKU']].append(p)

matches=[];pair_by_ss={};pair_by_sh={}
for s in sorted(sh,key=lambda p:p['Title'].casefold()):
    candidates=ss_by_sku.get(s['Variant SKU'],[]) if s['Variant SKU'] else []
    assert len(candidates)<=1,'Main-export SKU joins more than one Squarespace product'
    if not candidates:continue
    q=candidates[0]
    assert len(sh_by_sku[s['Variant SKU']])==1
    index=len(matches)+1;mid=f'M-{index:03d}'
    title_equal=norm(q['Title'])==norm(s['Title'])
    body_equal=norm(plain(q['Description']))==norm(plain(s['Body (HTML)']))
    price_equal=Decimal(q['Price'])==Decimal(s['Variant Price'])
    row=dict(match_id=mid,sku=q['SKU'],sq_id=q['Product ID [Non Editable]'],sq_variant_id=q['Variant ID [Non Editable]'],sq_title=q['Title'],sh_handle=s['Handle'],sh_title=s['Title'],sq_price=float(q['Price']),sh_price=float(s['Variant Price']),title_comparison='Same' if title_equal else 'Different',description_comparison='Same after HTML/whitespace normalization' if body_equal else 'Different',price_comparison='Same numeric source price' if price_equal else 'Different',basis='Unique identical nonblank SKU in both main source datasets',scope='Source product correspondence; physical sculpture and live availability not determined',sq_source_row=q['_row'],sq_csv_record=q['CSV data record'],sh_source_row=s['_row'],sh_csv_record=s['CSV record'],sq_visible=q['Visible'],sq_stock=q['Stock'],sh_status=s['Status'],sq_url='https://boldstonesculpture.com/'+q['Product Page']+'/p/'+q['Product URL'],sq_variant_rows=sum(r['Resolved parent product ID']==q['Product ID [Non Editable]'] for r in source['SS Wall Variants']),sh_source_rows=sum(r['Handle']==s['Handle'] for r in source['SH Source Rows']))
    matches.append(row);pair_by_ss[row['sq_id']]=row;pair_by_sh[row['sh_handle']]=row
assert len(matches)==len(pair_by_ss)==len(pair_by_sh)==37
assert {(r['sq_id'],r['sh_handle']) for r in matches}=={(r['Squarespace product ID'],r['Shopify handle']) for r in source['Matched Overview']}

ss_only=[]
for q in sorted(ss,key=lambda p:(p['Title'].casefold(),p['Product ID [Non Editable]'])):
    if q['Product ID [Non Editable]'] in pair_by_ss:continue
    related=[p for p in sh if norm(p['Title'])==norm(q['Title'])]
    duplicate_sku=len(ss_by_sku[q['SKU']])>1
    reason='No identical nonblank SKU in the main Shopify wall export'
    if duplicate_sku:reason+='; this SKU is also used by another distinct Squarespace product ID'
    candidate=''
    if related:candidate='Same-title Shopify record only; no confirmed offer link: '+ '; '.join(p['Handle'] for p in related)
    if 'frozen fish' in q['Title'].casefold():candidate='Shopify frozen-fish is a blank-SKU, zero-price draft with no description. Its name does not identify this finish or sale arrangement.'
    ss_only.append(dict(record_key='SQ:'+q['Product ID [Non Editable]'],sq_id=q['Product ID [Non Editable]'],title=q['Title'],sku=q['SKU'],reason=reason,candidate=candidate,source_row=q['_row'],csv_record=q['CSV data record'],variant_rows=sum(r['Resolved parent product ID']==q['Product ID [Non Editable]'] for r in source['SS Wall Variants']),plain_description=plain(q['Description']),raw=q))
sh_only=[]
for s in sorted(sh,key=lambda p:p['Title'].casefold()):
    if s['Handle'] in pair_by_sh:continue
    reason='Blank SKU and description; no confirmed Squarespace offer link'
    sh_only.append(dict(record_key='SH:'+s['Handle'],handle=s['Handle'],title=s['Title'],sku=s['Variant SKU'],reason=reason,candidate='Two Squarespace Frozen Fish finish offers exist. The Shopify draft does not establish either offer identity.',source_row=s['_row'],csv_record=s['CSV record'],raw=s))
assert len(ss_only)==43 and len(sh_only)==1
assert {r['sq_id'] for r in ss_only}=={r['Product ID [Non Editable]'] for r in source['Unmatched Squarespace']}
assert {r['handle'] for r in sh_only}=={r['Handle'] for r in source['Unmatched Shopify']}

old=[]
for sheet,version in [('SH Older Wall','Older export'),('SH Seed Wall','Seed export')]:
    for p in source[sheet]:
        sku=p['Variant SKU'];exact=ss_by_sku.get(sku,[]) if sku else []
        assert len(exact)<=1
        status='Exact SKU match to Squarespace' if exact else 'Candidate only; different SKU' if sku else 'Candidate only; blank SKU'
        sq_id=exact[0]['Product ID [Non Editable]'] if exact else p['Matched/candidate Squarespace ID']
        old.append(dict(record_key=('SH-OLDER:' if sheet=='SH Older Wall' else 'SH-SEED:')+p['Handle'],version=version,title=p['Title'],sku=sku,handle=p['Handle'],status=status,exact_match=bool(exact),related_sq=sq_id,related_sq_title=ss_by_id[sq_id]['Title'] if sq_id in ss_by_id else '',lineage=p['Lineage state'],source_sheet=sheet,source_row=p['_row'],source_fidelity=p['Source fidelity'],raw=p))
assert len(old)==9 and sum(r['exact_match'] for r in old)==1

ss_schema=list(ss[0]);ss_schema=ss_schema[ss_schema.index('Product ID [Non Editable]'):]
sh_schema=list(sh[0]);sh_schema=sh_schema[sh_schema.index('Handle'):sh_schema.index('Status')+1]
old_schema=list(source['SH Older Wall'][0]);old_schema=old_schema[old_schema.index('Handle'):old_schema.index('Status')+1]
assert (len(ss_schema),len(sh_schema),len(old_schema))==(34,95,49)
ss_rows=[]
for p in source['SS Wall Variants']:
    sq_id=p['Resolved parent product ID'];match=pair_by_ss.get(sq_id)
    ss_rows.append(dict(row_key='SQROW:'+p['CSV data record'],match_id=match['match_id'] if match else '',status='Matched' if match else 'Squarespace only',record_kind='Product / primary variant' if p['CSV data record']==ss_by_id[sq_id]['CSV data record'] else 'Additional variant',parent_id=sq_id,parent_title=p['Resolved parent title'],sh_handle=match['sh_handle'] if match else '',source_row=p['_row'],csv_record=p['CSV data record'],values={k:p[k] for k in ss_schema}))
sh_rows=[]
for p in source['SH Source Rows']:
    match=pair_by_sh.get(p['Handle'])
    sh_rows.append(dict(row_key='SHROW:'+p['CSV record'],match_id=match['match_id'] if match else '',status='Matched' if match else 'Shopify only',record_kind='Product / primary variant' if p['Title'] else 'Image continuation',sq_id=match['sq_id'] if match else '',parent_title=sh_by_handle[p['Handle']]['Title'],source_row=p['_row'],csv_record=p['CSV record'],values={k:p[k] for k in sh_schema}))
ss_rows.sort(key=lambda r:(r['status'],r['parent_title'].casefold(),int(r['csv_record'])))
sh_rows.sort(key=lambda r:(r['status'],r['parent_title'].casefold(),int(r['csv_record'])))
native=json.loads((ev/'native_records.json').read_text())
canonical={r['row_key']:r['values'] for r in native}
assert all(r['values']==canonical[r['row_key']] for r in ss_rows+sh_rows)
for r in old:
    key=('SH-OLDER:' if r['source_sheet']=='SH Older Wall' else 'SH-SEED:')+r['raw']['Subset record']
    assert {k:r['raw'][k] for k in old_schema}==canonical[key]

counts=dict(squarespace_products=len(ss),shopify_main_products=len(sh),matched_product_pairs=len(matches),squarespace_only_products=len(ss_only),shopify_only_products=len(sh_only),ss_native_rows=len(ss_rows),sh_native_rows=len(sh_rows),ss_matched_native_rows=sum(r['status']=='Matched' for r in ss_rows),ss_unmatched_native_rows=sum(r['status']!='Matched' for r in ss_rows),sh_matched_native_rows=sum(r['status']=='Matched' for r in sh_rows),sh_unmatched_native_rows=sum(r['status']!='Matched' for r in sh_rows),historical_shopify_records=len(old),historical_exact_sku_matches=sum(r['exact_match'] for r in old),historical_candidates=sum(not r['exact_match'] for r in old),all_native_rows=len(ss_rows)+len(sh_rows)+len(old),matched_title_agreements=sum(r['title_comparison']=='Same' for r in matches),matched_description_agreements=sum(r['description_comparison'].startswith('Same') for r in matches),matched_price_agreements=sum(r['price_comparison'].startswith('Same') for r in matches))
model=dict(created_utc=datetime.now(timezone.utc).isoformat(),source_workbook=source_file.name,source_sha256=source_sha,scope='Wall-sculpture records supplied in the 15 October 2026 reconciliation workbook. Other product categories and fresh live store inventory are outside this comparison.',sq_source_date='15 October 2026 supplied export',sh_source_date='Preserved historical wall export; checked 11 October 2026, original export date unspecified',rule='Unique identical nonblank SKU for confirmed cross-platform matches. Title, normalized description and numeric price are independently compared. Archive candidates stay separate from confirmed main-export matches.',counts=counts,matches=matches,squarespace_only=ss_only,shopify_only=sh_only,historical=old,ss_rows=ss_rows,sh_rows=sh_rows,ss_schema=ss_schema,sh_schema=sh_schema,old_schema=old_schema)
(ev/'platform_comparison_2026-10-16.json').write_text(json.dumps(model,ensure_ascii=False))
print(json.dumps(counts))
