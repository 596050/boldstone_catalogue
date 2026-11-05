"""Create a local, searchable review of proposed platform prices."""
from pathlib import Path
import html
import json
import sys

out = Path(sys.argv[1]).resolve()
plan = json.loads((out/'profit-pricing-plan.json').read_text())
app = json.loads((out/'app-after.json').read_text())
names = {p['id']: p.get('retail_name') or p['name'] for p in app['products']}
body = ["""<!doctype html><html lang="en"><meta charset="utf-8"><title>Boldstone platform pricing</title>
<style>body{font:16px/1.5 system-ui;color:#25362a;margin:32px}h1{font:32px Georgia}input{font:inherit;padding:9px;width:420px;max-width:90%}table{border-collapse:collapse;width:100%;font-size:14px;margin-top:24px}th,td{border-bottom:1px solid #d5dfd1;padding:10px;text-align:right;vertical-align:top}th{background:#edf1e9;position:sticky;top:0}th:first-child,td:first-child{text-align:left;min-width:260px}small{display:block;color:#687660}.notes{max-width:1100px}.hold{color:#8b5e20}</style>
<h1>Platform prices that preserve catalogue profit</h1><div class="notes">
<p><strong>181 catalogue records, including 176 products in publication scope.</strong> These prices aim to leave at least the current catalogue selling price after the modelled platform fees and allowed discounts. Subtracting unchanged manufacturing cost therefore preserves current recorded profit. Core retail prices and labour remain unchanged.</p>
<p>Faire and custom-wholesaler planning: 50% retailer margin plus up to 20% total stacked brand-funded wholesale promotions, 25% commission ceiling, optional 3% payout allowance, 20% reserve for potentially unrecoverable tax on those fees, and £0.05 fee-rounding reserve. The tax reserve is an assumption, not a determination of VAT status. Generic wholesaler rates are planning ceilings to replace with its actual contract. Faire-funded incentives do not reduce the seller payout and are not charged again here.</p>
<p>Chairish: up to 40% markdown followed by the recorded trade discount, at least 60% auction discount, 40% standard and 20% auction commission, with the same fee-tax reserve, 3% FX/conversion allowance and $1 fee-rounding reserve. The USD per GBP reference remains 1.3419478344101459, dated 2 November. Verify the native seller plan and conversion fees before application. An auction starting bid is not a reserve; never use a no-reserve sale below the calculated floor.</p>
<p>These are catalogue targets, not live-platform prices. A Faire retail reference must represent genuine retail pricing across channels. It must not be used to fabricate an original price or a discount. Shipping, packing and product transaction taxes are separate.</p>
<p><a href="https://www.faire.com/support/articles/360040446591">Faire fees</a> · <a href="https://www.faire.com/support/articles/8223664793883">Faire UK pricing guidance</a> · <a href="https://support.chairish.com/hc/en-us/articles/44165603442321-Chairish-Selling-Plans-Commission-Rate-Overview">Chairish commissions</a> · <a href="https://support.chairish.com/hc/en-us/articles/44170634648721-Auction-Reserve-Prices">Chairish auction reserves</a></p></div>
<label>Find sculpture or SKU <input id="q" type="search" placeholder="Type a name, finish or SKU"></label>
<table><thead><tr><th>Sculpture / SKU</th><th>Current retail GBP</th><th>Current profit GBP</th><th>Faire wholesale GBP</th><th>Faire retail reference GBP</th><th>Chairish asking USD</th><th>Chairish auction reserve USD</th><th>Minimum Chairish net GBP</th><th>Other auction reserve GBP</th></tr></thead><tbody>"""]
for record in plan['records']:
    title = names[record['catalogue_id']]
    label = html.escape(title) + '<small>' + html.escape(record['sku']) + '</small>'
    if not record['included_for_publication']:
        label += '<small class="hold">Outside the 176-product publication scope</small>'
    amounts = [record['baseline_price_gbp'], record['baseline_profit_gbp'],
               record['faire']['asking'], record['faire']['retail_reference'],
               record['chairish']['asking_usd'], record['chairish']['auction_reserve_usd'],
               record['chairish']['minimum_net_gbp'], record['auction']['minimum_sale']]
    key = html.escape((title+' '+record['sku']).lower(), quote=True)
    body.append('<tr data-search="'+key+'"><td>'+label+'</td>'+''.join('<td>'+format(n,',.2f')+'</td>' for n in amounts)+'</tr>')
body.append("""</tbody></table><script>document.getElementById('q').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.dataset.search.includes(q))})</script></html>""")
(out/'platform-price-review.html').write_text(''.join(body))
print('Pricing review saved for', len(plan['records']), 'records')
