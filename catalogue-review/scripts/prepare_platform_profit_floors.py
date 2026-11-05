"""Append editable platform profit protection to the existing catalogue."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import shutil
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from platform_pricing import decimal as D, rounded, price_floor, proceeds
from import_saatchi_snapshot import Xlsx, column, column_index


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    write = lambda name, data: (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())
    source = pointer['current_app_review_workbook']
    assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() == source['sha256']
    shutil.copyfile(source['path'], out / 'previous-catalogue.xlsx')
    write('source-pointer-before.json', pointer)
    with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as response:
        app = json.load(response)
    write('app-after.json', app)
    book = Xlsx(out / 'previous-catalogue.xlsx')
    sheet = 'Wall Sculptures'
    headers = {book.value(sheet, a): re.sub(r'\d', '', a) for a in book.cells[sheet] if re.fullmatch(r'[A-Z]+7', a)}
    rows = {book.value(sheet, f'AA{r}'): r for r in range(8, 189)}
    products = {p['id']: p for p in app['products']}
    assert set(rows) == set(products) and len(rows) == 181
    publication = {r['catalogue_id'] for r in json.loads((ROOT / 'outputs/faire-gumtree-20261104/faire-upload.json').read_text())['records']}
    first = max(map(column_index, headers.values())) + 1
    patches, added, calculations = [], [], []

    def put(address, value, formula=None, fmt=None):
        patches.append(dict(sheet=sheet, cell=address, before=book.value(sheet, address),
                            value=value, formula=formula, format=fmt))

    def allocate(key):
        if key not in headers:
            headers[key] = column(max(map(column_index, headers.values())) + 1)
            added.append(key)
            put(headers[key] + '7', key, fmt='header')
        return headers[key]

    def cell(key, row):
        return allocate(key) + str(row)

    def field(key, row, value, formula=None, fmt='0.00'):
        put(cell(key, row), float(value) if isinstance(value, type(D(0))) else value, formula, fmt)

    # Explicit conservative reserves, not representations of the account's VAT or payout setup.
    settings = [
        ('pricing_fee_tax_reserve', 'Potential unrecoverable tax on seller fees', .2, '0%'),
        ('pricing_rounding_reserve_gbp', 'Fee rounding reserve per sale (GBP)', .05, '0.00'),
        ('pricing_fx_allowance', 'Planning FX and conversion allowance', .03, '0%'),
        ('faire_retailer_discount', 'Faire retailer margin', .5, '0%'),
        ('faire_opening_commission', 'Faire opening commission', .25, '0%'),
        ('faire_reorder_commission', 'Faire reorder commission', .15, '0%'),
        ('faire_payout_fee_allowance', 'Faire optional next-day payout allowance', .03, '0%'),
        ('faire_fixed_fee_gbp', 'Faire other fee allowance per unit (GBP)', 0, '0.00'),
        ('faire_brand_promotion_allowance', 'Faire total stacked brand-funded promotion allowance', .2, '0%'),
        ('wholesale_retailer_discount', 'Other wholesaler retailer margin', .5, '0%'),
        ('wholesale_commission_allowance', 'Other wholesaler commission planning ceiling', .25, '0%'),
        ('wholesale_payout_fee_allowance', 'Other wholesaler payout allowance', .03, '0%'),
        ('wholesale_fixed_fee_gbp', 'Other wholesaler other fees per unit (GBP)', 0, '0.00'),
        ('wholesale_brand_promotion_allowance', 'Other wholesaler total promotion allowance', .2, '0%'),
        ('auction_discount_allowance', 'Other auction discount allowance', .6, '0%'),
        ('auction_commission_allowance', 'Other auction commission planning ceiling', .2, '0%'),
        ('auction_fixed_fee_gbp', 'Other auction seller fees per unit (GBP)', 0, '0.00'),
        ('chairish_auction_discount_allowance', 'Chairish auction discount allowance', .6, '0%'),
        ('chairish_rounding_reserve_usd', 'Chairish fee rounding reserve (USD)', 1, '0.00'),
    ]
    controls = {}
    for key, label, value, fmt in settings:
        c = allocate(key)
        put(c + '3', label, fmt='header')
        put(c + '4', value, fmt=fmt)
        controls[key] = '$' + c + '$4'
    controls.update(chairish_sale_commission='$BH$4', chairish_auction_commission='$BI$4',
                    chairish_standard_discount='$BG$4', chairish_fixed_fee='$BJ$4', usd_per_gbp='$BB$4')
    fx = D(book.value(sheet, 'BB4'))
    assert fx > 0
    tax = controls['pricing_fee_tax_reserve']; reserve = controls['pricing_rounding_reserve_gbp']
    fx_allowance = controls['pricing_fx_allowance']
    keep = lambda c, p='0': f'(1-({c}+{p})*(1+{tax}))'

    for pid, row in rows.items():
        p = products[pid]; r = str(row); c = p['costing']
        baseline = D(c['pricing']['marked_up_price']); cost = D(c['total_cost'])
        assert abs(D(book.value(sheet, 'H' + r)) - baseline) < D('.001'), (pid, 'Master price differs from app')
        assert c['labour_cost'] == 0 and baseline > 0
        f = {x['key']: x['value'] for x in p['fields'] + p['listing_fields']}
        calc = dict(catalogue_id=pid, row=row, sku=f['Seller SKU'], title=p.get('retail_name') or p['name'],
                    included_for_publication=pid in publication, baseline_price_gbp=float(baseline),
                    cost_gbp=float(cost), baseline_profit_gbp=float(baseline-cost))
        field('pricing_net_target_gbp', row, baseline, '=H' + r)
        field('pricing_profit_target_gbp', row, baseline-cost, f'=ROUND(H{r}-AM{r},2)')
        for prefix in ['faire', 'wholesale']:
            commission = controls['faire_opening_commission' if prefix == 'faire' else 'wholesale_commission_allowance']
            payout = controls[prefix + '_payout_fee_allowance']; fixed = controls[prefix + '_fixed_fee_gbp']
            discount = controls['faire_retailer_discount' if prefix == 'faire' else 'wholesale_retailer_discount']
            promotion = controls[prefix + '_brand_promotion_allowance']
            result = price_floor(baseline, '.25', '.03', '.2', discount='.2')
            floor = cell(prefix + '_wholesale_floor_gbp', row)
            field(prefix + '_wholesale_floor_gbp', row, result['minimum_sale'],
                  f'=ROUNDUP((H{r}+{fixed}*(1+{tax})+{reserve})/{keep(commission,payout)},2)')
            w = cell(prefix + '_wholesale_price_gbp', row)
            field(prefix + '_wholesale_price_gbp', row, result['asking'],
                  f'=ROUNDUP({floor}/(1-{promotion}),2)')
            retail = rounded(result['asking'] / D('.5'))
            field(prefix + '_retail_reference_gbp', row, retail, f'=ROUNDUP({w}/(1-{discount}),2)')
            discounted = cell(prefix + '_promoted_wholesale_gbp', row)
            field(prefix + '_promoted_wholesale_gbp', row, result['discounted_sale'],
                  f'=ROUNDDOWN({w}*(1-{promotion}),2)')
            net = cell(prefix + '_net_after_fees_gbp', row)
            field(prefix + '_net_after_fees_gbp', row, result['net'],
                  f'=ROUNDDOWN({discounted}*{keep(commission,payout)}-{fixed}*(1+{tax})-{reserve},2)')
            field(prefix + '_profit_after_fees_gbp', row, result['net']-cost, f'=ROUND({net}-AM{r},2)')
            field(prefix + '_minimum_net_check', row, 'Meets catalogue target',
                  f'=IF({net}>=H{r},"Meets catalogue target","Below catalogue target")', 'text')
            calc[prefix] = {k: float(v) for k, v in result.items()}
            calc[prefix]['retail_reference'] = float(retail)
        w = cell('faire_promoted_wholesale_gbp', row)
        for label, commission in [('reorder', '.15'), ('direct', '0')]:
            rate = controls['faire_reorder_commission'] if label == 'reorder' else '0'
            net = proceeds(D(calc['faire']['discounted_sale']), commission, '.03', '.2')
            field(f'faire_{label}_net_gbp', row, net,
                  f'=ROUNDDOWN({w}*{keep(rate,controls["faire_payout_fee_allowance"])}-{controls["faire_fixed_fee_gbp"]}*(1+{tax})-{reserve},2)')
        field('faire_pricing_action', row,
              'Calculated target only. Reconcile genuine retail pricing across channels and verify fees before applying to the existing Faire record.', fmt='text')
        field('wholesale_pricing_action', row,
              'Planning profile only: 25% commission, 3% payout allowance. Enter the actual wholesaler contract; do not claim these are verified fees.', fmt='text')

        auction = price_floor(baseline, '.2', fee_tax='.2', discount='.6')
        auction_floor = cell('auction_reserve_floor_gbp', row)
        field('auction_reserve_floor_gbp', row, auction['minimum_sale'],
              f'=ROUNDUP((H{r}+{controls["auction_fixed_fee_gbp"]}*(1+{tax})+{reserve})/{keep(controls["auction_commission_allowance"])},2)')
        asking = cell('auction_asking_reference_gbp', row)
        field('auction_asking_reference_gbp', row, auction['asking'],
              f'=ROUNDUP({auction_floor}/(1-{controls["auction_discount_allowance"]}),2)')
        sale = cell('auction_discounted_reserve_gbp', row)
        field('auction_discounted_reserve_gbp', row, auction['discounted_sale'],
              f'=ROUNDDOWN({asking}*(1-{controls["auction_discount_allowance"]}),2)')
        net = cell('auction_net_at_reserve_gbp', row)
        field('auction_net_at_reserve_gbp', row, auction['net'],
              f'=ROUNDDOWN({sale}*{keep(controls["auction_commission_allowance"])}-{controls["auction_fixed_fee_gbp"]}*(1+{tax})-{reserve},2)')
        field('auction_profit_at_reserve_gbp', row, auction['net']-cost, f'=ROUND({net}-AM{r},2)')
        field('auction_pricing_action', row,
              'Reserve required. A starting bid is not a profit floor. Replace planning fees with the actual auction terms; do not use a no-reserve auction.', fmt='text')
        calc['auction'] = {k: float(v) for k, v in auction.items()}

        # Chairish has separate standard and auction fees and discount controls.
        existing = lambda key, default: book.value(sheet, cell(key, row)) if book.value(sheet, cell(key,row)) not in (None, '') else default
        reserve_discount = D(existing('chairish_reserve_discount_target', '.2'))
        trade_discount = D(existing('chairish_trade_discount_target', '.12'))
        standard_discount = max(D('.4'), 1-D('.6')*(1-trade_discount), reserve_discount)
        auction_discount = max(D('.6'), D(existing('chairish_auction_discount_target', '.4')), standard_discount)
        target = rounded(baseline * fx / D('.97'), 0)
        normal = price_floor(target, '.4', fee_tax='.2', discount=standard_discount, rounding_reserve=1, places=0)
        auc = price_floor(target, '.2', fee_tax='.2', discount=auction_discount, rounding_reserve=1, places=0)
        asking_usd = max(normal['asking'], auc['asking'])
        sale_amounts = dict(price=asking_usd, reserve=rounded(asking_usd*(1-reserve_discount),0,up=False),
                           auction_reserve=rounded(asking_usd*(1-auction_discount),0,up=False),
                           trade_price=rounded(asking_usd*(1-trade_discount),0,up=False),
                           discount_allowance=rounded(asking_usd*(1-standard_discount),0,up=False))
        target_ref = cell('chairish_net_target_usd', row)
        field('chairish_net_target_usd', row, target, f'=ROUNDUP(H{r}*$BB$4/(1-{fx_allowance}),0)', '0')
        field('chairish_commission_rate',row,.4,'=$BH$4','0%')
        field('chairish_auction_commission_rate',row,.2,'=$BI$4','0%')
        field('chairish_other_fees_usd',row,0,'=$BJ$4')
        field('chairish_discount_allowance', row, standard_discount,
              f'=MAX($BG$4,1-(1-$BG$4)*(1-{cell("chairish_trade_discount_target",row)}),{cell("chairish_reserve_discount_target",row)})','0.0%')
        field('chairish_auction_discount_target',row,auction_discount,
              f'=MAX({controls["chairish_auction_discount_allowance"]},{cell("chairish_discount_allowance",row)})','0%')
        if book.value(sheet,cell('chairish_reserve_discount_target',row)) in (None,''):
            field('chairish_reserve_discount_target',row,reserve_discount,fmt='0%')
        if book.value(sheet,cell('chairish_trade_discount_target',row)) in (None,''):
            field('chairish_trade_discount_target',row,trade_discount,fmt='0%')
        usdreserve = controls['chairish_rounding_reserve_usd']
        for key, amount, rate in [('minimum_sale_price_usd',normal['minimum_sale'],'$BH$4'),('auction_minimum_sale_price_usd',auc['minimum_sale'],'$BI$4')]:
            field('chairish_'+key,row,amount,
                  f'=ROUNDUP(({target_ref}+$BJ$4*(1+{tax})+{usdreserve})/{keep(rate)},0)','0')
        ask_ref = cell('chairish_asking_price_usd',row)
        field('chairish_asking_price_usd',row,asking_usd,
              f'=MAX(ROUNDUP({cell("chairish_minimum_sale_price_usd",row)}/(1-{cell("chairish_discount_allowance",row)}),0),ROUNDUP({cell("chairish_auction_minimum_sale_price_usd",row)}/(1-{cell("chairish_auction_discount_target",row)}),0))','0')
        price_fields = dict(price='asking_price_usd',reserve='reserve_price_usd',auction_reserve='auction_reserve_usd',trade_price='trade_price_usd',discount_allowance='discounted_sale_usd')
        discounts = dict(reserve=cell('chairish_reserve_discount_target',row),auction_reserve=cell('chairish_auction_discount_target',row),trade_price=cell('chairish_trade_discount_target',row),discount_allowance=cell('chairish_discount_allowance',row))
        nets = {}
        for name, amount in sale_amounts.items():
            rate = '.2' if name == 'auction_reserve' else '.4'
            rate_ref = '$BI$4' if name == 'auction_reserve' else '$BH$4'
            price_ref = cell('chairish_'+price_fields[name],row)
            if name != 'price':
                field('chairish_'+price_fields[name],row,amount,f'=ROUNDDOWN({ask_ref}*(1-{discounts[name]}),0)','0')
            net = proceeds(amount,rate,fee_tax='.2',rounding_reserve=1,places=0)
            nets[name]=net
            field('chairish_proceeds_at_'+name+'_usd',row,net,
                  f'=ROUNDDOWN({price_ref}*{keep(rate_ref)}-$BJ$4*(1+{tax})-{usdreserve},0)','0')
            assert net >= target
        net_gbp = rounded(min(nets.values())/fx*D('.97'),up=False)
        assert net_gbp >= baseline
        field('chairish_net_after_discount_gbp',row,net_gbp,
              '=ROUNDDOWN(MIN('+','.join(cell('chairish_proceeds_at_'+name+'_usd',row) for name in nets)+f')/$BB$4*(1-{fx_allowance}),2)')
        field('chairish_profit_after_discount_gbp',row,net_gbp-cost,
              f'=ROUND({cell("chairish_net_after_discount_gbp",row)}-AM{r},2)')
        field('chairish_pricing_basis',row,
              'Preserve catalogue net receipt at every reserve. Up to 40% markdown followed by the recorded trade discount; auction discount >=60%. Standard/auction commission 40%/20%. Provisional fee-tax reserve 20%, FX allowance 3%, rounding reserve USD1. Verify actual fees, tax and FX. Shipping, packing and product taxes separate.',fmt='text')
        field('chairish_update_state',row,'Profit-preserving catalogue targets calculated 4 November. Existing native listing updates not yet verified.',fmt='text')
        calc['chairish'] = dict(asking_usd=float(asking_usd),auction_reserve_usd=float(sale_amounts['auction_reserve']),minimum_net_gbp=float(net_gbp),profit_gbp=float(net_gbp-cost))
        field('platform_profit_pricing_status',row,
              'Calculated planning targets; verify fees/tax and retail positioning before live application. Current core price unchanged.',fmt='text')
        calculations.append(calc)

    plan = dict(patches=patches, headers=headers, added_master_columns=added, first_master_column=first,
                last_master_column=max(map(column_index,headers.values())), records=calculations, controls=controls,
                settings=[dict(key=k,label=l,value=v,format=f) for k,l,v,f in settings],
                scope='Profit-preserving Faire/custom wholesale prices include 50% retailer margin plus up to 20% stacked brand-funded wholesale promotions. Chairish covers up to 40% markdown followed by the recorded trade discount and at least 60% auction discount, with fees, FX and rounding allowances. All 181 records retained; core prices, costs, inclusion and Saatchi metadata unchanged. No native platform price changes.',
                prepared_utc=datetime.now(timezone.utc).isoformat(), app_revision=app['revision'])
    write('profit-pricing-plan.json',plan)
    print(json.dumps(dict(records=len(rows),publication_records=len(publication),new_columns=len(added),patches=len(patches),first_column=column(first),last_column=column(plan['last_master_column']))))


if __name__ == '__main__':
    prepare(Path(sys.argv[1]).resolve())
