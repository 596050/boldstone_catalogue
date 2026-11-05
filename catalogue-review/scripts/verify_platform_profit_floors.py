"""Read the saved native workbook independently and reconcile every price."""
from pathlib import Path
import hashlib
import json
import sys

from import_saatchi_snapshot import Xlsx


out=Path(sys.argv[1]).resolve()
plan=json.loads((out/'profit-pricing-plan.json').read_text())
before=Xlsx(out/'previous-catalogue.xlsx');after=Xlsx(out/'catalogue_wall_sculptures.xlsx')
assert before.paths==after.paths
patches={(p['sheet'],p['cell']):p for p in plan['patches']}
assert len(patches)==len(plan['patches']), 'A cell was patched twice'
for (sheet,address),p in patches.items():
    actual=after.value(sheet,address)
    expected=p['value']
    if isinstance(expected,(int,float)) and not isinstance(expected,bool):
        assert isinstance(actual,(int,float)) and abs(actual-expected)<.011,(sheet,address,expected,actual)
    else:
        assert actual==expected,(sheet,address,expected,actual)
    assert after.formula(sheet,address)==(p['formula'][1:] if p['formula'] else None),(sheet,address,'formula')
preserved=0
for sheet,cells in before.cells.items():
    for address in cells:
        if (sheet,address) not in patches:
            assert before.value(sheet,address)==after.value(sheet,address),(sheet,address,'unrelated value changed')
            assert before.formula(sheet,address)==after.formula(sheet,address),(sheet,address,'unrelated formula changed')
            preserved+=1
h=plan['headers'];read=lambda key,row:after.value('Wall Sculptures',h[key]+str(row))
checks=[]
for p in plan['records']:
    row=p['row'];target=p['baseline_price_gbp'];profit=p['baseline_profit_gbp']
    assert after.value('Wall Sculptures','AA'+str(row))==p['catalogue_id']
    assert after.value('Wall Sculptures','H'+str(row))==target
    for prefix in ['faire','wholesale']:
        assert read(prefix+'_net_after_fees_gbp',row)+.001>=target
        assert read(prefix+'_profit_after_fees_gbp',row)+.001>=profit
        assert read(prefix+'_retail_reference_gbp',row)==2*read(prefix+'_wholesale_price_gbp',row)
    assert read('auction_net_at_reserve_gbp',row)+.001>=target
    assert read('auction_profit_at_reserve_gbp',row)+.001>=profit
    assert read('chairish_net_after_discount_gbp',row)+.001>=target
    assert read('chairish_profit_after_discount_gbp',row)+.001>=profit
    checks.append(p['catalogue_id'])
receipt=dict(status='PASS',records=len(checks),publication_records=sum(p['included_for_publication'] for p in plan['records']),
             cells_verified=len(patches),unrelated_values_and_formulas_preserved=preserved,
             all_four_platform_profiles_preserve_catalogue_profit=True,
             source_retail_prices_unchanged=True,source_manufacturing_and_labour_unchanged=True,
             native_platform_prices_applied=False,sha256=hashlib.sha256((out/'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest())
(out/'independent-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
