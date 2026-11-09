"""Prepare scoped catalogue changes, preserving observations and genuine identifiers."""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path[:0] = [str(ROOT/'catalogue-review'), str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx, column, column_index
from channel_content import finish_retail_name

load = lambda p: json.loads(Path(p).read_text())
book = Xlsx(OUT/'previous-catalogue.xlsx')
headers = {book.value('Wall Sculptures', a): re.sub(r'\d', '', a)
           for a in book.cells['Wall Sculptures'] if re.fullmatch('[A-Z]+7', a)}
assert len(headers) == 806
app = {p['id']: p for p in load(OUT/'app-specifications.json')['products']}
google = {p['catalogue_id']: p for p in load(ROOT/'outputs/catalogue-channel-imports-20261107/google-source-reconciliation.json')['wall_sculpture_matches_detail']}
preview = {p['catalogue_id']: p for p in load(OUT/'brandboom-preview50-records.json')}
prices = {p['catalogue_id']: p for p in load(OUT/'faire-pricing-remediation.json')}
posts = {p['catalogue_id']: p for p in load(ROOT/'outputs/instagram-marketplace-next-channels-20261107-1324/instagram-five-posts.json')}
stamp = datetime.now(timezone.utc).isoformat()
stamp_serial = (datetime.now(timezone.utc)-datetime(1899,12,30,tzinfo=timezone.utc)).total_seconds()/86400
new_headers = [
 'gtin', 'gtin_assignment_status', 'gtin_allocation_source', 'gtin_licensee', 'gtin_verified_utc',
 'faire_native_net_gbp_estimate', 'faire_native_profit_gbp_estimate', 'faire_direct_profit_shortfall_gbp',
 'faire_shared_retail_increase_gbp', 'faire_required_rrp_multiplier', 'faire_price_remediation_status',
 'faire_price_remediation_action', 'faire_estimate_basis', 'faire_remediation_prepared_utc',
 'google_merchant_title_target', 'google_merchant_title_update_required', 'google_merchant_title_update_action',
 'pinterest_claimed_website_observed', 'pinterest_instagram_connection_observed', 'pinterest_tag_verification',
 'pinterest_merchant_checked_utc', 'pinterest_appeals_used_this_update',
 'brandboom_preview50_presentation_id', 'brandboom_preview50_title', 'brandboom_preview50_edit_url',
 'brandboom_preview50_position', 'brandboom_preview50_status',
 'instagram_prepared_caption', 'instagram_prepared_alt_text', 'instagram_prepared_media_sha256',
 'instagram_automation_status', 'channel_remediation_sources',
]
assert len(set(new_headers)) == len(new_headers) and not set(new_headers)&set(headers)
first = max(column_index(c) for c in headers.values()) + 1
headers.update({h: column(i) for i,h in enumerate(new_headers, first)})
patches=[]

def setcell(field, row, value='', formula=None, style='text'):
    address = headers[field]+str(row)
    patch = dict(sheet='Wall Sculptures', cell=address, header=field,
                 before=book.value('Wall Sculptures',address), value=value, style=style)
    if formula is not None: patch['formula']=formula
    if formula is not None or patch['before'] != value:
        patches.append(patch)

for field in new_headers:
    setcell(field, 7, field, style='header')

money=lambda v: float(Decimal(str(v)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
down=lambda v: float(Decimal(str(v)).quantize(Decimal('.01'), rounding=ROUND_DOWN))
changed_titles=[]
for row in range(8,189):
    pid=book.value('Wall Sculptures','AA'+str(row))
    assert pid in app
    p=app[pid]
    selected=pid in google
    assert book.value('Wall Sculptures','AL'+str(row)) == 0
    setcell('gtin', row, '')
    setcell('gtin_assignment_status', row, 'Not assigned. Genuine GS1 allocation and licence evidence required.')
    for h in ['gtin_allocation_source','gtin_licensee','gtin_verified_utc']:setcell(h,row,'')
    # Do not copy seller SKUs into GTINs or claim an allocation without evidence.
    for h in ['pinterest_gtin','faire_native_export_gtin']:
        assert not book.value('Wall Sculptures', headers[h]+str(row))
    if selected:
        v=prices[pid]
        assert v['current_retail']==book.value('Wall Sculptures','H'+str(row))
        assert v['cost']==book.value('Wall Sculptures','BA'+str(row))
        d=lambda x:Decimal(str(x))
        fee_tax=d(book.value('Wall Sculptures','QC4'))
        other_reserve=d(book.value('Wall Sculptures','QD4'))
        rate=d(book.value('Wall Sculptures','QG4'))+d(book.value('Wall Sculptures','QI4'))
        fixed=d(book.value('Wall Sculptures','QJ4'))
        v['native_net']=down(d(v['native_wholesale'])*(1-rate*(1+fee_tax))-fixed*(1+fee_tax)-other_reserve)
        v['native_profit']=money(d(v['native_net'])-d(v['cost']))
        v['profit_shortfall']=money(max(Decimal(0),d(v['current_retail'])-d(v['native_net'])))
        netcol=headers['faire_native_net_gbp_estimate']
        profitcol=headers['faire_native_profit_gbp_estimate']
        # Existing editable fees/tax-reserve controls remain the one source of assumptions.
        net=f'IF(ISNUMBER(UX{row}),ROUNDDOWN(UX{row}*(1-($QG$4+$QI$4)*(1+$QC$4))-$QJ$4*(1+$QC$4)-$QD$4,2),"")'
        setcell('faire_native_net_gbp_estimate', row, v['native_net'], net, 'money')
        setcell('faire_native_profit_gbp_estimate', row, v['native_profit'], f'IF(ISNUMBER({netcol}{row}),ROUND({netcol}{row}-BA{row},2),"")', 'money')
        setcell('faire_direct_profit_shortfall_gbp', row, v['profit_shortfall'], f'IF(ISNUMBER({profitcol}{row}),MAX(0,ROUND(H{row}-BA{row}-{profitcol}{row},2)),"")', 'money')
        increase=money(book.value('Wall Sculptures','QW'+str(row))-v['current_retail'])
        setcell('faire_shared_retail_increase_gbp', row, increase, f'ROUND(QW{row}-H{row},2)', 'money')
        multiple=money(v['rrp_multiplier'])
        setcell('faire_required_rrp_multiplier', row, multiple, f'IF(H{row}>0,ROUND(QW{row}/H{row},2),"")', 'ratio')
        setcell('faire_price_remediation_status', row, 'Prepared for review. Native Faire prices remain below protected model.')
        action='Choose genuine shared retail alignment to faire_retail_reference_gbp and wholesale to faire_wholesale_price_gbp, or accept a lower wholesale profit/discount allowance. No website or Faire price change applied.'
        setcell('faire_price_remediation_action',row,action)
        setcell('faire_estimate_basis',row,'Estimate using existing opening commission, payout allowance, fixed fees and fee-tax reserve. Current native estimate has no additional promotion. Protected target includes the configured brand promotion. Packing and delivery are separate. Total cost includes labour once.')
        setcell('faire_remediation_prepared_utc',row,stamp_serial,style='utc')
        setcell('faire_pricing_action',row,action)
        target=finish_retail_name(p)
        old=google[pid]['google_title']
        missing_finish='finish' in target.casefold() and 'finish' not in old.casefold()
        if missing_finish:changed_titles.append(pid)
        setcell('google_merchant_title_target',row,target)
        setcell('google_merchant_title_update_required',row,'Yes - Finish wording' if missing_finish else 'No Finish wording gap observed')
        setcell('google_merchant_title_update_action',row,'Update the existing website product title upstream, preserving product ID, SKU and URL, then verify the native Google feed.' if missing_finish else 'Keep the existing native record; no duplicate product.')
        setcell('pinterest_merchant_status',row,'Merchant approval blocked: minimum product and website-quality requirements. Domain claim and Instagram connection now verified. No appeal submitted.')
        setcell('pinterest_claimed_website_observed',row,'boldstonesculpture.com - claimed in Pinterest settings')
        setcell('pinterest_instagram_connection_observed',row,'@boldstonesculpture connected; existing automatic publishing to Social board enabled')
        setcell('pinterest_tag_verification',row,'Not yet verified. Check consent-aware tag and product events on the website.')
        setcell('pinterest_merchant_checked_utc',row,stamp_serial,style='utc')
        setcell('pinterest_appeals_used_this_update',row,0,style='integer')
    else:
        setcell('faire_price_remediation_status',row,'Not a current publication product; no native Faire offer matched.')
        setcell('google_merchant_title_update_required',row,'Not a current publication product')
    if pid in preview:
        pr=preview[pid]
        setcell('brandboom_preview50_presentation_id',row,'681160')
        setcell('brandboom_preview50_title',row,'Wall Sculptures - 50 Preview')
        setcell('brandboom_preview50_edit_url',row,'https://manage.brandboom.com/products/s/111089/p/681160')
        setcell('brandboom_preview50_position',row,pr['sequence'],style='integer')
        setcell('brandboom_preview50_status',row,'Saved and reloaded: 50 products, wholesale only, ordering disabled. Owner review; not submitted to Marketplace.')
    if pid in posts:
        post=posts[pid]
        assert not book.value('Wall Sculptures',headers['instagram_post_url']+str(row))
        assert hashlib.sha256(Path(post['media_path']).read_bytes()).hexdigest()==post['sha256']
        setcell('instagram_prepared_caption',row,post['caption'])
        setcell('instagram_prepared_alt_text',row,post['alt_text'])
        setcell('instagram_prepared_media_sha256',row,post['sha256'])
        setcell('instagram_automation_status',row,'Prepared, not published. macOS permission prompt and Accessibility access block live automation testing. Verify exact Commerce product tag and duplicate search before publication.')
    setcell('channel_remediation_sources',row,'https://support.google.com/manufacturers/answer/6124116?hl=en\nhttps://help.pinterest.com/en/business/article/before-you-get-started-with-catalogs\nhttps://policy.pinterest.com/en/merchant-guidelines\nhttps://www.faire.com/support/articles/360040446591')

assert len(changed_titles)==62
plan=dict(scope='Append GTIN allocation status, per-product Faire profit remediation, Google Finish title targets, Pinterest observations, exact 50-product Brandboom preview membership and five unpublished Instagram preparations. Preserve prices, all original formulas and product identities.',
          prepared_utc=stamp,source_sha256=hashlib.sha256((OUT/'previous-catalogue.xlsx').read_bytes()).hexdigest(),
          patches=patches,new_headers=new_headers,first_added_column=first,last_added_column=first+len(new_headers)-1,
          new_native_publications_recorded=0,new_native_drafts_recorded=1,
          google_finish_title_gaps=62,brandboom_preview_members=50,gtins_assigned=0,
          previews=[dict(name='faire',range=f'{headers["faire_native_net_gbp_estimate"]}7:{headers["faire_required_rrp_multiplier"]}11'),
                    dict(name='brandboom',range=f'{headers["brandboom_preview50_presentation_id"]}7:{headers["brandboom_preview50_position"]}11')])
(OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
(OUT/'faire-pricing-remediation.json').write_text(json.dumps(list(prices.values()),ensure_ascii=False,indent=2)+'\n')
(OUT/'faire-pricing-summary.json').write_text(json.dumps(dict(records=len(prices),below_direct_profit=sum(v['profit_shortfall']>0 for v in prices.values()),negative_profit=sum(v['native_profit']<0 for v in prices.values()),native_fee_estimate_includes_fixed_reserve_gbp=float(book.value('Wall Sculptures','QD4')),example=prices['BSI-59530C6155C2']),indent=2)+'\n')
print(json.dumps({k:v for k,v in plan.items() if k not in ['patches','new_headers']},indent=2))
